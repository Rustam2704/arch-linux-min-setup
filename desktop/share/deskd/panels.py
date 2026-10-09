"""Panels per screen for xfce4-panel, driven through xfconf.

The laptop panel (panel-1) is the user's own. Every other connected screen gets a copy
of it made here, plugin by plugin with all their settings: the workspace strip is told
its screen, the dock lists only that screen's windows, and the tray is left out (X has
one tray per display; a second one would steal it). A copy that no longer matches the
main panel (a plugin added or removed there) is rebuilt; panels of screens that went
away are removed again.

xfce4-panel rewrites its settings when it exits, so changes are made with the panel
stopped, and it is started again through i3 (so it lives in the session, not in
deskd's service).
"""
import os
import subprocess
import time

STRIP = os.path.expanduser("~/.local/bin/panel-workspaces")
MAIN_PANEL = 1
# The whole X screen is drawn at 1.5x, so a 1920-px monitor cannot hold the 2560-px laptop
# panel. On a screen narrower than the laptop's the copy leaves out the two widest
# number readouts (ping, CPU/RAM/SWAP: ~460 px; the laptop panel still shows them) and
# keeps everything else, with room for the dock to grow.
SKIP_ON_NARROW = ("panel-net", "panel-sys")


def q(*args):
    return subprocess.run(["xfconf-query", "-c", "xfce4-panel", *args],
                          capture_output=True, text=True).stdout


def read_all():
    """{property: value-string} of the whole channel."""
    props = {}
    for line in q("-l", "-v").splitlines():
        if line.startswith("/"):
            key, _, val = line.partition(" ")
            props[key] = val.strip()
    return props


def int_list(val):
    val = val.strip().strip("[]")
    return [int(x) for x in val.split(",") if x.strip().lstrip("-").isdigit()]


def set_prop(prop, typ, value):
    q("-p", prop, "-n", "-t", typ, "-s", str(value))


def set_array(prop, typ, values):
    args = ["-p", prop, "-n", "-a"]
    for v in values:
        args += ["-t", typ, "-s", str(v)]
    q(*args)


def remove(prop):
    q("-p", prop, "-r", "-R")


def strips(props=None):
    """[(plugin_id, output or None for the primary screen)] of every workspace strip."""
    props = props or read_all()
    out = []
    for key, val in props.items():
        if key.startswith("/plugins/plugin-") and key.endswith("/command") and val.startswith(STRIP):
            pid = int(key.split("/")[2].split("-")[1])
            arg = val[len(STRIP):].strip()
            out.append((pid, arg or None))
    return out


def screen_panels(props):
    """{output: panel_id} for the per-screen panels made here."""
    found = {}
    strip_ids = dict(strips(props))
    for pid in int_list(props.get("/panels", "")):
        if pid == MAIN_PANEL:
            continue
        plugins = int_list(props.get(f"/panels/panel-{pid}/plugin-ids", ""))
        outs = [strip_ids.get(p) for p in plugins if strip_ids.get(p)]
        if outs:
            found[outs[0]] = pid
    return found


XML = os.path.expanduser("~/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml")


def _xml_node(*path):
    import xml.etree.ElementTree as ET
    try:
        node = ET.parse(XML).getroot()
    except (OSError, ET.ParseError):
        return None
    for name in path:
        node = next((c for c in node if c.get("name") == name), None)
        if node is None:
            return None
    return node


def copy_props(props, src_base, dst_base, node, skip=()):
    """Copy every property under an XML node with its exact type, arrays included
    (live values from xfconf-query win over the file for plain ones)."""
    if node is None:
        return
    for child in node:
        name, typ = child.get("name"), child.get("type")
        if not name or name in skip or typ == "empty":
            continue
        if typ == "array":
            values = [v for v in child if v.tag == "value"]
            if values:
                args = ["-p", f"{dst_base}/{name}", "-n", "-a"]
                for v in values:
                    args += ["-t", v.get("type"), "-s", v.get("value")]
                q(*args)
            continue
        val = props.get(f"{src_base}/{name}", child.get("value"))
        set_prop(f"{dst_base}/{name}", typ, val)


def copy_plugin(props, src, dst):
    copy_props(props, f"/plugins/plugin-{src}", f"/plugins/plugin-{dst}", _xml_node("plugins", f"plugin-{src}"))


def skipped(props, plugin, narrow):
    """Plugins of the main panel that a screen copy leaves out."""
    kind = props.get(f"/plugins/plugin-{plugin}", "")
    if kind == "systray":
        return True
    cmd = os.path.basename(props.get(f"/plugins/plugin-{plugin}/command", "").split(" ")[0])
    return narrow and cmd in SKIP_ON_NARROW


def signature(props, pid, narrow=False):
    """What a panel is made of: the plugin types and scripts, in order, without the ones a
    copy leaves out (narrow: as a copy for a narrower screen should be). A copy as it is
    must equal the main panel's narrow-or-not signature, or it is rebuilt."""
    sig = []
    for p in int_list(props.get(f"/panels/panel-{pid}/plugin-ids", "")):
        if skipped(props, p, narrow):
            continue
        kind = props.get(f"/plugins/plugin-{p}", "")
        cmd = os.path.basename(props.get(f"/plugins/plugin-{p}/command", "").split(" ")[0])
        sig.append(f"{kind}:{cmd}" if cmd else kind)
    return ",".join(sig)


def plan(outputs, primary, narrow=()):
    """What should change: ([outputs needing a panel], [panel ids to drop]).
    narrow: the outputs narrower than the primary one."""
    props = read_all()
    have = screen_panels(props)
    want = [o for o in outputs if o != primary]
    stale = [o for o, pid in have.items()
             if o in want and signature(props, pid) != signature(props, MAIN_PANEL, o in narrow)]
    add = [o for o in want if o not in have or o in stale]
    drop = [pid for o, pid in have.items() if o not in want or o in stale]
    return add, drop, props


PANEL_DIR = os.path.expanduser("~/.config/xfce4/panel")


def _copy_rc(src, dst, only_this_screen=False):
    """A plugin's rc file for its copy, through the lab journal like every desktop file."""
    from pathlib import Path
    path = Path(PANEL_DIR) / src
    if not path.exists():
        return
    text = path.read_text()
    if only_this_screen:
        import configparser
        import io
        cp = configparser.ConfigParser()
        cp.optionxform = str
        cp.read_string(text)
        if "user" not in cp:
            cp["user"] = {}
        cp["user"]["onlyDisplayScreen"] = "true"
        stream = io.StringIO()
        cp.write(stream)
        text = stream.getvalue()
    subprocess.run([os.environ["SKY_LAB"], "write", "deskd-monitor-panel", str(Path(PANEL_DIR) / dst)],
                   input=text, text=True, check=True)


def _copy_dir(src, dst):
    from pathlib import Path
    target = Path(PANEL_DIR) / dst
    if not target.exists():
        target.mkdir(parents=True)
        subprocess.run([os.environ["SKY_LAB"], "undo", "deskd-monitor-panel", f"rmdir -- {target}"], check=False)
    for f in sorted((Path(PANEL_DIR) / src).glob("*")):
        if f.is_file():
            subprocess.run([os.environ["SKY_LAB"], "write", "deskd-monitor-panel",
                            str(Path(PANEL_DIR) / dst / f.name)], input=f.read_text(), text=True, check=True)


def _remove_files(kind, pid):
    """The rc file or launcher folder a dropped copy left behind."""
    from pathlib import Path
    lab = os.environ["SKY_LAB"]
    for name in (f"{kind}-{pid}.rc",):
        path = Path(PANEL_DIR) / name
        if path.exists():
            subprocess.run([lab, "remove", "deskd-monitor-panel", str(path)], check=False)
    folder = Path(PANEL_DIR) / f"{kind}-{pid}"
    if folder.is_dir():
        for f in folder.glob("*"):
            subprocess.run([lab, "remove", "deskd-monitor-panel", str(f)], check=False)
        try:
            folder.rmdir()
        except OSError:
            pass


def apply(add, drop, props, restart, narrow=()):
    """Stop the panel, rewrite xfconf, start it again with restart()."""
    subprocess.run(["xfce4-panel", "-q"], capture_output=True)
    for _ in range(30):
        if subprocess.run(["pgrep", "-x", "xfce4-panel"], capture_output=True).returncode:
            break
        time.sleep(0.1)
    panels = int_list(props.get("/panels", ""))
    plugin_ids = [int(k.split("/")[2].split("-")[1]) for k in props
                  if k.count("/") == 2 and k.startswith("/plugins/plugin-")]
    next_plugin = max(plugin_ids + [0]) + 1
    main_plugins = int_list(props.get(f"/panels/panel-{MAIN_PANEL}/plugin-ids", ""))
    tasklist = next((p for p in main_plugins if props.get(f"/plugins/plugin-{p}") in ("tasklist", "docklike")), None)
    task_kind = props.get(f"/plugins/plugin-{tasklist}", "tasklist")
    if tasklist and task_kind == "tasklist":       # every panel lists only its own screen
        set_prop(f"/plugins/plugin-{tasklist}/include-all-monitors", "bool", "false")

    for pid in drop:
        for p in int_list(props.get(f"/panels/panel-{pid}/plugin-ids", "")):
            remove(f"/plugins/plugin-{p}")
            _remove_files(props.get(f"/plugins/plugin-{p}", ""), p)
        remove(f"/panels/panel-{pid}")
        panels.remove(pid)

    main_node = _xml_node("panels", f"panel-{MAIN_PANEL}")
    for out in add:
        pid = max(panels + [0]) + 1
        panels.append(pid)
        base = f"/panels/panel-{pid}"
        copy_props(props, f"/panels/panel-{MAIN_PANEL}", base, main_node, skip=("output-name", "plugin-ids"))
        set_prop(base + "/output-name", "string", out)
        set_prop(base + "/span-monitors", "bool", "false")
        ids = []
        for src in main_plugins:
            kind = props.get(f"/plugins/plugin-{src}", "")
            if not kind or skipped(props, src, out in narrow):
                continue
            nid = next_plugin
            next_plugin += 1
            set_prop(f"/plugins/plugin-{nid}", "string", kind)
            copy_plugin(props, src, nid)
            command = props.get(f"/plugins/plugin-{src}/command", "")
            if kind == "genmon" and command.startswith(STRIP):
                set_prop(f"/plugins/plugin-{nid}/command", "string", f"{STRIP} {out}")
            elif kind == "docklike":
                _copy_rc(f"docklike-{src}.rc", f"docklike-{nid}.rc", only_this_screen=True)
            elif kind == "tasklist":
                set_prop(f"/plugins/plugin-{nid}/include-all-monitors", "bool", "false")
            elif kind == "launcher":
                _copy_dir(f"launcher-{src}", f"launcher-{nid}")
            elif kind == "whiskermenu":
                _copy_rc(f"whiskermenu-{src}.rc", f"whiskermenu-{nid}.rc")
            ids.append(nid)
        set_array(base + "/plugin-ids", "int", ids)
    set_array("/panels", "int", panels)
    restart()
