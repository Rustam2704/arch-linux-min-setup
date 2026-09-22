#!/usr/bin/env python3
"""Run a desktop command with the active i3 session's display environment."""
import os
from pathlib import Path
import subprocess
import sys


def environment():
    env = os.environ.copy()
    pid = subprocess.check_output(["pgrep", "-u", str(os.getuid()), "-x", "i3"], text=True).splitlines()[0]
    for pair in Path(f"/proc/{pid}/environ").read_bytes().split(b"\0"):
        key, _, value = pair.partition(b"=")
        if key in (b"DISPLAY", b"XAUTHORITY", b"DBUS_SESSION_BUS_ADDRESS", b"XDG_RUNTIME_DIR"):
            env[key.decode()] = value.decode()
    return env


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["--"]:
        args = args[1:]
    os.execvpe(args[0], args, environment())
