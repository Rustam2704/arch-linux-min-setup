#!/usr/bin/env python3
"""Build, compare and install the versioned desktop through the lab journal."""
import ast
import difflib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "desktop"
BUILD = ROOT / ".build/desktop"
EXPERIMENT = "29-desktop-polish"
THEME = json.loads((SOURCE / "share/sky-desktop/theme.json").read_text())
PALETTE = {"#000000": "background", "#0a0e11": "background", "#12171a": "surface",
           "#dfe8ee": "foreground", "#5b6b76": "muted", "#1e262c": "border",
           "#48daf9": "light", "#0d8ecb": "accent", "#e05561": "danger"}


def sources():
    return sorted(p for p in SOURCE.rglob("*") if p.is_file() and "__pycache__" not in p.parts
                  and p.relative_to(SOURCE).parts[0] in ("bin", "share", "config"))


def target(relative):
    kind, *parts = relative.parts
    return Path.home() / {"bin": ".local/bin", "share": ".local/share", "config": ".config"}[kind] / Path(*parts)


def render(path):
    data = path.read_text().replace("@HOME@", str(Path.home())).replace("@PROJECT@", str(ROOT))
    # Shared tokens also drive native consumers which cannot import Python.
    if path.suffix in (".conf", ".rasi", ".css", ".svg") or path.name == "config":
        for colour, key in PALETTE.items():
            data = data.replace(colour, "@COLOUR_" + key.upper() + "@")
        for key, value in THEME.items():
            if isinstance(value, str):
                data = data.replace("@COLOUR_" + key.upper() + "@", value)
    return data


def build():
    for source in sources():
        dest = BUILD / source.relative_to(SOURCE)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(render(source))


def check():
    count = 0
    for path in sources():
        text = render(path)
        if path.suffix == ".py" or text.startswith("#!/usr/bin/env python"):
            ast.parse(text, filename=str(path))
        elif text.startswith(("#!/bin/sh", "#!/bin/bash")):
            subprocess.run(["bash", "-n"], input=text, text=True, check=True)
        if "/home/fanatic" in text and str(Path.home()) != "/home/fanatic":
            raise ValueError("Unexpanded personal path in " + str(path))
        count += 1
    subprocess.run(["bash", "-n", str(ROOT / "lab/lab")], check=True)
    print(f"Checked {count} source files")


def differences(show_diff=False):
    changed = []
    for source in sources():
        dest = target(source.relative_to(SOURCE))
        old = dest.read_text() if dest.exists() else ""
        new = render(source)
        if old == new:
            continue
        changed.append((source, dest, new))
        if show_diff:
            print("".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True),
                                            fromfile=str(dest), tofile=str(source))), end="")
    return changed


def apply():
    changes = differences()
    for source, dest, content in changes:
        if not dest.parent.exists():
            # Parent directories are recorded too, so rollback leaves no empty junk.
            missing, parent = [], dest.parent
            while not parent.exists():
                missing.append(parent)
                parent = parent.parent
            import shlex
            for parent in reversed(missing):
                subprocess.run([str(ROOT / "lab/lab"), "undo", EXPERIMENT,
                                "rmdir -- " + shlex.quote(str(parent))], check=True)
                parent.mkdir()
        subprocess.run([str(ROOT / "lab/lab"), "write", EXPERIMENT, str(dest)],
                       input=content, text=True, check=True)
        if source.relative_to(SOURCE).parts[0] == "bin":
            dest.chmod(0o755)
    print(f"Installed {len(changes)} changed files; recorded in lab/journal.tsv")


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
    elif action == "status":
        changes = differences()
        for _, path, _ in changes:
            print("Differs:", path)
        print(f"{len(changes)} files differ from the declared desktop")
    else:
        sys.exit("Use check, build, diff, apply or status")
