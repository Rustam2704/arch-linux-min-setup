#!/usr/bin/env python3
"""Idempotent migration: give Wi-Fi and latency independent genmon widgets."""
import os
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "desktop/share/deskd"))
import panels


def apply():
    props = panels.read_all()
    command = str(Path.home() / ".local/bin/panel-wifi")
    if any(v == command for v in props.values()):
        return False
    net = next((int(k.split("/")[2].split("-")[1]) for k, v in props.items()
                if k.endswith("/command") and os.path.basename(v) == "panel-net"), None)
    if net is None:
        raise RuntimeError("No panel-net widget found")
    panel_key = next(k for k, v in props.items() if k.endswith("/plugin-ids") and net in panels.int_list(v))
    old_ids = panels.int_list(props[panel_key])
    pid = max(int(k.split("/")[2].split("-")[1]) for k in props if k.startswith("/plugins/plugin-")) + 1
    new_ids = list(old_ids)
    new_ids.insert(new_ids.index(net), pid)
    restore = ["xfconf-query", "-c", "xfce4-panel", "-p", panel_key, "-a"]
    for value in old_ids:
        restore += ["-t", "int", "-s", str(value)]
    remove = ["xfconf-query", "-c", "xfce4-panel", "-p", f"/plugins/plugin-{pid}", "-r", "-R"]
    undo = shlex.join(restore) + " && " + shlex.join(remove) + " && xfce4-panel -r"
    subprocess.run([str(ROOT / "lab/lab"), "undo", "29-desktop-polish", undo], check=True)
    panels.set_prop(f"/plugins/plugin-{pid}", "string", "genmon")
    for key, typ, value in (("command", "string", command), ("update-period", "int", "1000"),
                            ("font", "string", "Inter 15"), ("use-label", "bool", "false"),
                            ("text", "string", ""), ("enable-single-row", "bool", "true")):
        panels.set_prop(f"/plugins/plugin-{pid}/{key}", typ, value)
    panels.set_array(panel_key, "int", new_ids)
    if panels.read_all().get(f"/plugins/plugin-{pid}/command") != command:
        raise RuntimeError("Panel migration did not persist")
    return True


if __name__ == "__main__":
    print("Wi-Fi widget added" if apply() else "Panel already configured")
