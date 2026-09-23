"""Minimal i3 IPC client: commands, queries and event subscriptions - either as a
raw socket for a select() loop (sky-stars) or plugged into a GLib main loop
(deskd). No third-party dependencies; GLib is imported only by Subscription."""
import json
import os
import socket
import struct
import subprocess

MAGIC = b"i3-ipc"
HEADER = struct.Struct("=6sII")
RUN_COMMAND, GET_WORKSPACES, SUBSCRIBE, GET_OUTPUTS, GET_TREE, SEND_TICK = 0, 1, 2, 3, 4, 10
EVENT_NAMES = {0: "workspace", 1: "output", 2: "mode", 3: "window", 5: "binding", 6: "shutdown", 7: "tick"}


def socket_path():
    path = os.environ.get("I3SOCK")
    if path and os.path.exists(path):
        return path
    return subprocess.run(["i3", "--get-socketpath"], capture_output=True, text=True).stdout.strip()


def _connect(path):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect(path)
    return s


def _recv_exact(sock, n):
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("i3 closed the connection")
        buf += chunk
    return buf


class I3:
    def __init__(self, path=None):
        self.path = path or socket_path()
        self.sock = _connect(self.path)

    def _ask(self, kind, payload=b""):
        if isinstance(payload, str):
            payload = payload.encode()
        self.sock.sendall(HEADER.pack(MAGIC, len(payload), kind) + payload)
        while True:
            _, length, rtype = HEADER.unpack(_recv_exact(self.sock, HEADER.size))
            data = json.loads(_recv_exact(self.sock, length))
            if not rtype & 0x80000000:          # skip stray events (never subscribed here)
                return data

    def command(self, cmd):
        return self._ask(RUN_COMMAND, cmd)

    def tree(self):
        return self._ask(GET_TREE)

    def workspaces(self):
        return self._ask(GET_WORKSPACES)

    def outputs(self):
        return self._ask(GET_OUTPUTS)

    def tick(self, payload):
        """A tick event every subscriber sees - how our processes nudge each other."""
        return self._ask(SEND_TICK, payload)


def subscribe(events, path=None):
    """A socket on which i3 delivers the named events; feed its bytes to decode()."""
    sock = _connect(path or socket_path())
    payload = json.dumps(events).encode()
    sock.sendall(HEADER.pack(MAGIC, len(payload), SUBSCRIBE) + payload)
    return sock


def decode(buf):
    """Split buffered bytes into complete (name, payload) events; returns the events
    and whatever partial message is left over."""
    events = []
    while len(buf) >= HEADER.size:
        _, length, rtype = HEADER.unpack(buf[:HEADER.size])
        if len(buf) < HEADER.size + length:
            break
        body = buf[HEADER.size:HEADER.size + length]
        buf = buf[HEADER.size + length:]
        if rtype & 0x80000000:
            events.append((EVENT_NAMES.get(rtype & 0x7fffffff, str(rtype)), json.loads(body)))
    return events, buf


class Subscription:
    """Delivers (event_name, payload) to callback from the GLib main loop."""
    def __init__(self, events, callback, path=None):
        from gi.repository import GLib
        self.callback = callback
        self.sock = subscribe(events, path)
        self.buf = b""
        self.sock.setblocking(False)
        GLib.io_add_watch(self.sock.fileno(), GLib.PRIORITY_DEFAULT,
                          GLib.IO_IN | GLib.IO_HUP | GLib.IO_ERR, self._readable)

    def _readable(self, fd, cond):
        from gi.repository import GLib
        if cond & (GLib.IO_HUP | GLib.IO_ERR):
            self.callback("shutdown", {"change": "lost"})
            return False
        try:
            while True:
                chunk = self.sock.recv(65536)
                if not chunk:
                    self.callback("shutdown", {"change": "lost"})
                    return False
                self.buf += chunk
        except BlockingIOError:
            pass
        events, self.buf = decode(self.buf)
        for name, payload in events:
            try:
                self.callback(name, payload)
            except Exception as e:          # one bad handler must not kill the loop
                import traceback
                traceback.print_exc()
                print("i3ipc: handler error:", e, flush=True)
        return True


# ------------------------------------------------------------------ tree helpers
def walk(node, parent=None):
    """Yield (node, parent) for every container, tiling children first."""
    yield node, parent
    for child in node.get("nodes", []) + node.get("floating_nodes", []):
        yield from walk(child, node)


def find(tree, con_id):
    for node, parent in walk(tree):
        if node["id"] == con_id:
            return node, parent
    return None, None


def focused(tree):
    for node, parent in walk(tree):
        if node.get("focused"):
            return node, parent
    return None, None


def workspace_of(tree, con_id):
    """The workspace node that contains con_id."""
    def rec(node, ws):
        if node.get("type") == "workspace":
            ws = node
        if node["id"] == con_id:
            return ws
        for child in node.get("nodes", []) + node.get("floating_nodes", []):
            r = rec(child, ws)
            if r:
                return r
        return None
    return rec(tree, None)


def leaves(node):
    return [n for n, _ in walk(node) if n.get("window") and n.get("type") == "con"]


def is_floating(node, parent):
    return parent is not None and parent.get("type") == "floating_con"
