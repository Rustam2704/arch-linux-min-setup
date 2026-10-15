#!/usr/bin/env python3
"""Build, compare and install the declared desktop through the lab journal.

The tree under desktop/ is the whole installed desktop:

    desktop/bin/...      -> ~/.local/bin/...
    desktop/share/...    -> ~/.local/share/...
    desktop/config/...   -> ~/.config/...
    desktop/home/...     -> ~/...                (dotfiles such as .Xresources)
    desktop/system/...   -> /...                 (session script, xsession entry; via sudo)
    desktop/xfconf/<channel>.xml                 xfconf properties (the panel layout), set live
                                                 with xfconf-query, one undo per changed property

Every change goes through lab/lab and is journaled. lab/installed.manifest lists the sources the
last apply installed: a source deleted from the tree has its installed file removed (also
journaled, so rollback brings it back), and `status` reports it until then. Scripts are
installed 0755 and the mode is part of the comparison.

Text files are rendered: @HOME@, @USER@, @PROJECT@ and the style tokens from
desktop/share/sky-desktop/theme.json (@COLOUR_ACCENT@, @RGB_LIGHT@, @HEX_ACCENT@,
@FONT@ ...). Binary files (icons) are copied as they are. `check` refuses a
source that spells a theme colour as a literal instead of a token, so the theme
stays the single place where colours live.
"""
import ast
import difflib
import json
import os
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "desktop"
XFCONF = SOURCE / "xfconf"
BUILD = ROOT / ".build/desktop"
# Where the files go and where the journal lives. The defaults are the real machine; the
# environment variables let a rehearsal (and tests/test_installer.py) run in a temp tree.
HOME = Path(os.environ.get("DESKTOP_HOME") or Path.home())
SYSTEM_ROOT = Path(os.environ.get("DESKTOP_SYSTEM_ROOT") or "/")
STATE = Path(os.environ.get("LAB_STATE_DIR") or ROOT / "lab")
MANIFEST = STATE / "installed.manifest"
KINDS = {"bin": ".local/bin", "share": ".local/share", "config": ".config", "home": "", "system": None}
# The files that define the tokens must not have them filled in.
RAW = ("share/sky-desktop/sky_theme.py", "share/sky-desktop/theme.json")
# Each round of changes gets its own journal id: LAB_EXPERIMENT=32-something make apply
EXPERIMENT = os.environ.get("LAB_EXPERIMENT", "desktop-apply")

sys.path.insert(0, str(SOURCE / "share/sky-desktop"))
import sky_theme  # noqa: E402

TOKENS = sky_theme.tokens()
COLOURS = {v for k, v in TOKENS.items() if k.startswith("@COLOUR_")}


def sources():
    return sorted(p for p in SOURCE.rglob("*") if p.is_file() and "__pycache__" not in p.parts
                  and p.relative_to(SOURCE).parts[0] in KINDS)


def target(relative):
    kind, *parts = relative.parts
    if kind == "system":
        return SYSTEM_ROOT.joinpath(*parts)
    return HOME / KINDS[kind] / Path(*parts)


def render(path):
    """Rendered bytes of a source: text with tokens filled, binaries untouched."""
    raw = path.read_bytes()
    try:
        data = raw.decode()
    except UnicodeDecodeError:
        return raw
    if str(path.relative_to(SOURCE)) in RAW:
        return raw
    data = (data.replace("@HOME@", str(HOME)).replace("@PROJECT@", str(ROOT))
            .replace("@USER@", HOME.name))
    for token, value in TOKENS.items():
        data = data.replace(token, value)
    return data.encode()


# ------------------------------------------------------------------ xfconf
def xfconf_channels():
    """{channel: {property path: (type, value)}} declared under desktop/xfconf/."""
    return {path.stem: xfconf_parse(render(path).decode()) for path in sorted(XFCONF.glob("*.xml"))}


def xfconf_parse(text):
    """Flatten xfconf's per-channel XML: arrays become (type, [(item type, value), ...])."""
    out = {}

    def walk(node, prefix):
        for prop in node.findall("property"):
            path = f"{prefix}/{prop.get('name')}"
            kind = prop.get("type")
            if kind == "array":
                out[path] = (kind, [(v.get("type"), v.get("value")) for v in prop.findall("value")])
            elif kind != "empty":
                out[path] = (kind, prop.get("value"))
            walk(prop, path)
    walk(ET.fromstring(text), "")
    return out


# GVariant type letter -> xfconf type name
XFCONF_TYPES = {"b": "bool", "i": "int", "u": "uint", "d": "double", "s": "string",
                "x": "int64", "t": "uint64", "y": "uchar", "n": "int16", "q": "uint16"}


def xfconf_value(variant):
    """(type, value) of one property as the daemon returns it, in the form xfconf_parse gives."""
    kind = variant.get_type_string()
    if kind == "av":
        return "array", [xfconf_value(variant.get_child_value(i).get_variant()) for i in range(variant.n_children())]
    value = variant.unpack()
    return XFCONF_TYPES.get(kind, kind), str(value).lower() if kind == "b" else str(value)


def xfconf_live(channel):
    """{property path: (type, value)} of a channel as the running xfconf daemon holds it now.
    The perchannel XML on disk lags behind the daemon's memory (the panel flushes it on exit),
    so comparing against it - and recording undo values from it - can use stale state."""
    from gi.repository import Gio, GLib
    try:
        bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        reply = bus.call_sync("org.xfce.Xfconf", "/org/xfce/Xfconf", "org.xfce.Xfconf", "GetAllProperties",
                              GLib.Variant("(ss)", (channel, "/")), GLib.VariantType("(a{sv})"),
                              Gio.DBusCallFlags.NONE, 5000, None)
    except GLib.Error as error:
        sys.exit(f"xfconf is not reachable ({error.message}): run this inside the desktop session")
    entries = reply.get_child_value(0)
    return {entries.get_child_value(i).get_child_value(0).get_string():
            xfconf_value(entries.get_child_value(i).get_child_value(1).get_variant())
            for i in range(entries.n_children())}


# Arrays the session extends at run time: deskd appends a panel for every extra screen to
# xfce4-panel's /panels. The declared items must lead the live list; more after them is fine.
XFCONF_GROWING = {("xfce4-panel", "/panels")}


def xfconf_same(a, b, growing=False):
    if a is None or b is None or a[0] != b[0]:
        return False
    if growing and a[0] == "array":
        return b[1][:len(a[1])] == a[1]
    if a[0] == "double":
        return float(a[1]) == float(b[1])
    return a[1] == b[1]


def xfconf_differences():
    """[(channel, path, wanted, live)] - declared properties the live channel lacks or has otherwise."""
    out = []
    for channel, wanted in xfconf_channels().items():
        live = xfconf_live(channel)
        for path, value in wanted.items():
            if not xfconf_same(value, live.get(path), (channel, path) in XFCONF_GROWING):
                out.append((channel, path, value, live.get(path)))
    return out


def xfconf_args(value):
    kind, data = value
    if kind == "array":
        args = ["-a"]
        for item_kind, item in data:
            args += ["-t", item_kind, "-s", item]
        return args
    return ["-t", kind, "-s", data]


def xfconf_apply():
    changes = xfconf_differences()
    for channel, path, wanted, live in changes:
        # lab sets the property and journals the undo (xfconf-query arguments that restore the
        # value the daemon held a moment ago) only after the set worked.
        undo = ["-r"] if live is None else ["-n", *xfconf_args(live)]
        lab("xfconf", EXPERIMENT, channel, path, json.dumps(undo), "--", "-n", *xfconf_args(wanted))
    return changes


def build():
    if not MANIFEST.exists():
        manifest_write(manifest_read())     # remember what the old build tree knew before it is pruned
    kept = set()
    for source in sources():
        dest = BUILD / source.relative_to(SOURCE)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(render(source))
        kept.add(dest)
    # Sources deleted from the tree must not linger in the build output.
    for path in sorted(BUILD.rglob("*"), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
        elif path.is_file() and path not in kept:
            path.unlink()


def check():
    count = 0
    for path in sources():
        raw = path.read_bytes()
        try:
            text = raw.decode()
        except UnicodeDecodeError:
            count += 1
            continue
        rendered = render(path).decode()
        if path.suffix == ".py" or rendered.startswith("#!/usr/bin/env python"):
            ast.parse(rendered, filename=str(path))
        elif rendered.startswith(("#!/bin/sh", "#!/bin/bash")):
            subprocess.run(["bash", "-n"], input=rendered, text=True, check=True)
        if "/home/fanatic" in text:
            raise ValueError(f"{path}: personal path - use @HOME@")
        if path.name not in ("theme.json", "sky_theme.py"):
            for literal in COLOURS:
                if literal in text.lower():
                    key = next(k for k, v in TOKENS.items() if v == literal and k.startswith("@COLOUR_"))
                    raise ValueError(f"{path}: theme colour {literal} spelled out - use {key} or THEME")
        count += 1
    for path in sorted(XFCONF.glob("*.xml")):
        if "/home/fanatic" in path.read_text():
            raise ValueError(f"{path}: personal path - use @HOME@")
        xfconf_parse(render(path).decode())
        count += 1
    subprocess.run(["bash", "-n", str(ROOT / "lab/lab")], check=True)
    print(f"Checked {count} source files")


def wanted_mode(source, dest):
    """0o755 for a script - everything under bin, a system file in a bin directory or whose
    source is executable (e.g. a systemd system-sleep hook) - else None: any other file keeps the
    mode it has (lab gives a new one 644)."""
    parts = source.relative_to(SOURCE).parts
    if parts[0] == "bin" or (parts[0] == "system" and ("bin" in parts[:-1] or source.stat().st_mode & 0o111)):
        return 0o755
    return None


def differences(show_diff=False):
    changed = []
    for source in sources():
        dest = target(source.relative_to(SOURCE))
        old = dest.read_bytes() if dest.exists() else b""
        new = render(source)
        if old == new and dest.exists():
            continue
        changed.append((source, dest, new))
        if show_diff:
            try:
                print("".join(difflib.unified_diff(old.decode().splitlines(True), new.decode().splitlines(True),
                                                fromfile=str(dest), tofile=str(source))), end="")
            except UnicodeDecodeError:
                print(f"Binary differs: {dest}")
    return changed


def mode_differences(changed=()):
    """[(source, dest, wanted, actual)] - installed scripts with the wrong mode. A file whose
    content differs too is skipped: writing it sets the mode."""
    skip = {dest for _, dest, _ in changed}
    out = []
    for source in sources():
        dest = target(source.relative_to(SOURCE))
        wanted = wanted_mode(source, dest)
        if wanted is not None and dest not in skip and dest.is_file():
            actual = dest.stat().st_mode & 0o7777
            if actual != wanted:
                out.append((source, dest, wanted, actual))
    return out


# ------------------------------------------------------------------ install manifest
def manifest_read():
    """Relative paths (bin/foo, config/x/y) of the sources the last apply installed.
    With no manifest yet, the files of the last build stand in: .build/desktop holds a copy
    of every source that was ever built here, deleted ones included."""
    if MANIFEST.exists():
        return {line for line in MANIFEST.read_text().splitlines() if line}
    if not BUILD.is_dir():
        return set()
    return {str(p.relative_to(BUILD)) for p in BUILD.rglob("*") if p.is_file()}


def manifest_write(relatives):
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    temp = MANIFEST.with_suffix(".tmp")
    temp.write_text("".join(f"{relative}\n" for relative in sorted(relatives)))
    temp.replace(MANIFEST)


def removed():
    """[(relative path, installed file)] - installed earlier, source deleted since, file still there.
    A file that a source still in the tree installs under the same name is not stale."""
    current = {str(source.relative_to(SOURCE)) for source in sources()}
    wanted = {target(Path(relative)) for relative in current}
    out = []
    for relative in sorted(manifest_read() - current):
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts or path.parts[0] not in KINDS:
            continue
        dest = target(path)
        if dest not in wanted and (dest.is_file() or dest.is_symlink()):
            out.append((path, dest))
    return out


def lab(*args, **kw):
    return subprocess.run([str(ROOT / "lab/lab"), *args], check=True, **kw)


def forget_empty_parents(relative, dest):
    """After a removal: the directories it left empty go too - but only below the kind's root, never
    under /, and only where the tree no longer declares that directory."""
    kind = relative.parts[0]
    if kind == "system":
        return
    top = target(Path(kind))
    parent, declared = dest.parent, (SOURCE / relative).parent
    while parent != top and top in parent.parents and not declared.exists() and parent.is_dir() and not any(parent.iterdir()):
        lab("rmdir", EXPERIMENT, str(parent))
        parent, declared = parent.parent, declared.parent


def apply():
    changes = differences()
    modes = mode_differences(changes)
    stale = removed()
    # Until the run is over the manifest is a superset, so an interrupted run forgets nothing.
    installed = {str(source.relative_to(SOURCE)) for source in sources()}
    if manifest_read() != installed:
        manifest_write(manifest_read() | installed)
    for source, dest, content in changes:
        # lab creates the missing directories (each recorded) and elevates only where it must.
        if not dest.parent.is_dir():
            lab("mkdir", EXPERIMENT, str(dest.parent))
        mode = wanted_mode(source, dest)
        lab("write", EXPERIMENT, str(dest), *([f"{mode:o}"] if mode else []), input=content)
    for _, dest, wanted, _ in modes:
        lab("chmod", EXPERIMENT, f"{wanted:o}", str(dest))
    for relative, dest in stale:
        lab("remove", EXPERIMENT, str(dest))
        forget_empty_parents(relative, dest)
    manifest_write(installed)
    settings = xfconf_apply()
    print(f"Installed {len(changes)} changed files, fixed {len(modes)} modes, removed {len(stale)} files of deleted "
          f"sources and set {len(settings)} xfconf properties; recorded in the lab journal")


def packages():
    """Packages from packages.txt that pacman does not know about."""
    wanted = [line.split("#")[0].strip() for line in (ROOT / "packages.txt").read_text().splitlines()]
    wanted = [w for w in wanted if w]
    have = set(subprocess.run(["pacman", "-Qq"], capture_output=True, text=True).stdout.split())
    missing = [w for w in wanted if w not in have]
    for name in missing:
        print("Missing:", name)
    print(f"{len(wanted) - len(missing)} of {len(wanted)} packages installed")
    return missing


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"
    if action == "build":
        build()
    elif action == "check":
        check()
    elif action == "diff":
        changes = differences(True)
        for _, path, wanted, actual in mode_differences(changes):
            print(f"mode {path}: {actual:o} -> {wanted:o}")
        for _, path in removed():
            print(f"stale {path}: its source was deleted, apply removes it")
        for channel, path, wanted, live in xfconf_differences():
            print(f"xfconf {channel}{path}: {live} -> {wanted}")
    elif action == "apply":
        apply()
    elif action == "packages":
        sys.exit(1 if packages() else 0)
    elif action == "status":
        changes = differences()
        modes = mode_differences(changes)
        stale = removed()
        for _, path, _ in changes:
            print("Differs:", path)
        for _, path, wanted, actual in modes:
            print(f"Differs: mode {actual:o}, wanted {wanted:o}: {path}")
        for _, path in stale:
            print("Stale (source deleted):", path)
        settings = xfconf_differences()
        for channel, path, _, _ in settings:
            print(f"Differs: xfconf {channel}{path}")
        print(f"{len(changes) + len(modes) + len(stale)} files and {len(settings)} xfconf properties "
              "differ from the declared desktop")
    else:
        sys.exit("Use check, build, diff, apply, packages or status")
