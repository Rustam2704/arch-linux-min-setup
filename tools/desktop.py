#!/usr/bin/env python3
"""Build, compare and install the declared desktop through the lab journal.

The tree under desktop/ is the whole installed desktop:

    desktop/bin/...      -> ~/.local/bin/...
    desktop/share/...    -> ~/.local/share/...
    desktop/config/...   -> ~/.config/...
    desktop/home/...     -> ~/...                (dotfiles such as .Xresources)
    desktop/system/...   -> /...                 (session script, xsession entry; via sudo)

Text files are rendered: @HOME@, @PROJECT@ and the style tokens from
desktop/share/sky-desktop/theme.json (@COLOUR_ACCENT@, @RGB_LIGHT@, @HEX_ACCENT@,
@FONT@ ...). Binary files (icons) are copied as they are. `check` refuses a
source that spells a theme colour as a literal instead of a token, so the theme
stays the single place where colours live.
"""
import ast
import difflib
import os
from pathlib import Path
import shlex
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "desktop"
BUILD = ROOT / ".build/desktop"
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
        return Path("/", *parts)
    return Path.home() / KINDS[kind] / Path(*parts)


def render(path):
    """Rendered bytes of a source: text with tokens filled, binaries untouched."""
    raw = path.read_bytes()
    try:
        data = raw.decode()
    except UnicodeDecodeError:
        return raw
    if str(path.relative_to(SOURCE)) in RAW:
        return raw
    data = data.replace("@HOME@", str(Path.home())).replace("@PROJECT@", str(ROOT))
    for token, value in TOKENS.items():
        data = data.replace(token, value)
    return data.encode()


def build():
    for source in sources():
        dest = BUILD / source.relative_to(SOURCE)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(render(source))


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
    subprocess.run(["bash", "-n", str(ROOT / "lab/lab")], check=True)
    print(f"Checked {count} source files")


def differences(show_diff=False):
    changed = []
    for source in sources():
        dest = target(source.relative_to(SOURCE))
        old = dest.read_bytes() if dest.exists() else b""
        new = render(source)
        if old == new:
            continue
        changed.append((source, dest, new))
        if show_diff:
            try:
                print("".join(difflib.unified_diff(old.decode().splitlines(True), new.decode().splitlines(True),
                                                fromfile=str(dest), tofile=str(source))), end="")
            except UnicodeDecodeError:
                print(f"Binary differs: {dest}")
    return changed


def lab(*args, **kw):
    return subprocess.run([str(ROOT / "lab/lab"), *args], check=True, **kw)


def apply():
    changes = differences()
    for source, dest, content in changes:
        if not dest.parent.exists():
            # Parent directories are recorded too, so rollback leaves no empty junk.
            missing, parent = [], dest.parent
            while not parent.exists():
                missing.append(parent)
                parent = parent.parent
            for parent in reversed(missing):
                lab("undo", EXPERIMENT, "rmdir -- " + shlex.quote(str(parent)))
                if os.access(parent.parent, os.W_OK):
                    parent.mkdir()
                else:
                    subprocess.run(["sudo", "mkdir", str(parent)], check=True)
        lab("write", EXPERIMENT, str(dest), input=content)
        kind = source.relative_to(SOURCE).parts[0]
        if kind == "bin" or (kind == "system" and "bin" in dest.parts):
            if os.access(dest, os.W_OK):
                dest.chmod(0o755)
            else:
                subprocess.run(["sudo", "chmod", "755", str(dest)], check=True)
    print(f"Installed {len(changes)} changed files; recorded in lab/journal.tsv")


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
        differences(True)
    elif action == "apply":
        apply()
    elif action == "packages":
        sys.exit(1 if packages() else 0)
    elif action == "status":
        changes = differences()
        for _, path, _ in changes:
            print("Differs:", path)
        print(f"{len(changes)} files differ from the declared desktop")
    else:
        sys.exit("Use check, build, diff, apply, packages or status")
