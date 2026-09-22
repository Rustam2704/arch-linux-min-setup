"""Panels per screen for xfce4-panel, driven through xfconf.

The laptop panel (panel-1) is the user's own. Every other connected screen gets a
panel made here: its workspace strip, its windows (tasklist limited to that screen)
and the clock. Panels of screens that went away are removed again.

xfce4-panel rewrites its settings when it exits, so changes are made with the panel
stopped, and it is started again through i3 (so it lives in the session, not in
deskd's service).
"""
import os
import subprocess
import time

STRIP = os.path.expanduser("~/.local/bin/panel-workspaces")
MAIN_PANEL = 1


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


def copy_plugin(props, src, dst):
    """Copy a plugin's settings with their exact xfconf types (read from the channel XML;
    the live values come from xfconf-query)."""
    import xml.etree.ElementTree as ET
    try:
        root = ET.parse(XML).getroot()
    except (OSError, ET.ParseError):
        return
    plugins = next((p for p in root if p.get("name") == "plugins"), None)
    node = next((p for p in (plugins if plugins is not None else []) if p.get("name") == f"plugin-{src}"), None)
    if node is None:
        return
    for child in node:
        name, typ = child.get("name"), child.get("type")
        if typ in ("array", "empty") or not name:
            continue
        val = props.get(f"/plugins/plugin-{src}/{name}", child.get("value"))
        set_prop(f"/plugins/plugin-{dst}/{name}", typ, val)


def plan(outputs, primary):
    """What should change: ([outputs needing a panel], [panel ids to drop])."""
    props = read_all()
    have = screen_panels(props)
    want = [o for o in outputs if o != primary]
    return [o for o in want if o not in have], [pid for o, pid in have.items() if o not in want], props


def apply(add, drop, props, restart):
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
    clock = next((p for p in main_plugins if props.get(f"/plugins/plugin-{p}") == "clock"), None)
    task_kind = props.get(f"/plugins/plugin-{tasklist}", "tasklist")
    if tasklist and task_kind == "tasklist":       # every panel lists only its own screen
        set_prop(f"/plugins/plugin-{tasklist}/include-all-monitors", "bool", "false")

    for pid in drop:
        for p in int_list(props.get(f"/panels/panel-{pid}/plugin-ids", "")):
            remove(f"/plugins/plugin-{p}")
        remove(f"/panels/panel-{pid}")
        panels.remove(pid)

    main = f"/panels/panel-{MAIN_PANEL}"
    for out in add:
        pid = max(panels + [0]) + 1
        panels.append(pid)
        base = f"/panels/panel-{pid}"
        set_prop(base + "/output-name", "string", out)
        set_prop(base + "/position", "string", "p=6;x=0;y=0")
        set_prop(base + "/position-locked", "bool", "true")
        set_prop(base + "/length", "double", "100")
        set_prop(base + "/length-adjust", "bool", "true")
        set_prop(base + "/size", "uint", props.get(main + "/size", "44"))
        set_prop(base + "/icon-size", "uint", props.get(main + "/icon-size", "32"))
        set_prop(base + "/nrows", "uint", "1")
        set_prop(base + "/mode", "uint", "0")
        set_prop(base + "/enable-struts", "bool", "true")
        set_prop(base + "/span-monitors", "bool", "false")
        set_prop(base + "/enter-opacity", "uint", "100")
        set_prop(base + "/leave-opacity", "uint", "100")
        ids = []
        strip = next_plugin
        set_prop(f"/plugins/plugin-{strip}", "string", "genmon")
        for k, t, v in (("command", "string", f"{STRIP} {out}"), ("update-period", "int", "5000"),
                        ("use-label", "bool", "false"), ("text", "string", ""),
                        ("font", "string", "Inter 15"), ("enable-single-row", "bool", "true")):
            set_prop(f"/plugins/plugin-{strip}/{k}", t, v)
        ids.append(strip)
        sep = strip + 1
        set_prop(f"/plugins/plugin-{sep}", "string", "separator")
        set_prop(f"/plugins/plugin-{sep}/style", "uint", "0")
        ids.append(sep)
        nid = sep + 1
        if tasklist:
            set_prop(f"/plugins/plugin-{nid}", "string", task_kind)
            copy_plugin(props, tasklist, nid)
            if task_kind == "tasklist":
                set_prop(f"/plugins/plugin-{nid}/include-all-monitors", "bool", "false")
            else:
                # Docklike uses an rc file rather than xfconf properties.
                import configparser
                from pathlib import Path
                cp = configparser.ConfigParser()
                cp.optionxform = str
                cp.read(Path.home() / f".config/xfce4/panel/docklike-{tasklist}.rc")
                if "user" not in cp:
                    cp["user"] = {}
                cp["user"]["onlyDisplayScreen"] = "true"
                import io
                stream = io.StringIO()
                cp.write(stream)
                subprocess.run([os.environ["SKY_LAB"], "write", "deskd-monitor-panel",
                                str(Path.home() / f".config/xfce4/panel/docklike-{nid}.rc")],
                               input=stream.getvalue(), text=True, check=True)
            ids.append(nid)
            nid += 1
        set_prop(f"/plugins/plugin-{nid}", "string", "separator")
        set_prop(f"/plugins/plugin-{nid}/style", "uint", "0")
        set_prop(f"/plugins/plugin-{nid}/expand", "bool", "true")
        ids.append(nid)
        nid += 1
        if clock:
            set_prop(f"/plugins/plugin-{nid}", "string", "clock")
            copy_plugin(props, clock, nid)
            ids.append(nid)
            nid += 1
        set_array(base + "/plugin-ids", "int", ids)
        next_plugin = nid
    set_array("/panels", "int", panels)
    restart()
