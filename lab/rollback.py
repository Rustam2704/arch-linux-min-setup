#!/usr/bin/env python3
"""Rollback with conflict detection and durable failure records."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

# Records that change one path: an older one must not undo what a newer one did.
PATH_ACTIONS = ("backup", "file", "mode")


def legacy_xfconf(command):
    """[(channel, property)] touched by an old `cmd` record made of xfconf-query calls."""
    try:
        words = shlex.split(command)
    except ValueError:
        return []
    out, channel = [], None
    for word, following in zip(words, words[1:]):
        if word == "-c":
            channel = following
        elif word == "-p" and channel:
            out.append((channel, following))
    return out


def legacy_rmdir(command):
    """The directory of an old `cmd` record that is exactly `rmdir -- <dir>`, else None."""
    try:
        words = shlex.split(command)
    except ValueError:
        return None
    return words[2] if len(words) == 3 and words[:2] == ["rmdir", "--"] else None


def keys(row):
    """What a record changes; two records with a common key cannot be undone out of order."""
    action, target = row[2], row[3]
    if action in PATH_ACTIONS:
        return {("path", target)}
    if action == "xfconf":
        return {("xfconf", target)}
    if action == "cmd":
        return {("xfconf", f"{channel}:{prop}") for channel, prop in legacy_xfconf(target)}
    return set()


def blocked(path):
    """True when the directory holding `path` is not ours to change, so only root can."""
    if os.geteuid() == 0:
        return False
    parent = Path(path).parent
    while not parent.exists():
        parent = parent.parent
    return not os.access(parent, os.W_OK | os.X_OK)


def as_root(needed):
    return ["sudo"] if needed and os.geteuid() != 0 else []


def command_for(action, target, arg):
    """(command, note) for one record: the command to run, or None with a note when there is
    nothing left to undo. Raises ValueError for a record that cannot be undone."""
    if action == "cmd" and legacy_rmdir(target):
        action, target = "dir", legacy_rmdir(target)
    if action == "backup":
        if not arg or not (Path(arg).is_file() or Path(arg).is_symlink()):
            raise ValueError("Missing backup; journal retained: " + target)
        # Not --preserve ownership: a system file restored through sudo must stay root's.
        return as_root(blocked(target)) + ["cp", "-a", "--no-preserve=ownership", "--remove-destination", arg, target], None
    if action == "file":
        return as_root(blocked(target)) + ["rm", "-f", "--", target], None
    if action == "dir":
        path = Path(target)
        if not path.is_dir():
            return None, "already gone"
        try:
            if any(path.iterdir()):
                return None, "kept, not empty"
        except OSError:
            pass            # unreadable for us: let rmdir decide
        return as_root(blocked(target)) + ["rmdir", "--", target], None
    if action == "rmdir":
        if Path(target).is_dir():
            return None, "already there"
        return as_root(blocked(target)) + ["mkdir", "--", target], None
    if action == "mode":
        path = Path(target)
        if not path.exists():
            return None, "file is gone"
        mine = os.geteuid() == 0 or path.stat().st_uid == os.geteuid()
        return as_root(not mine) + ["chmod", arg, "--", target], None
    if action == "xfconf":
        channel, _, prop = target.partition(":")
        return ["xfconf-query", "-c", channel, "-p", prop, *json.loads(arg)], None
    if action == "pkg":
        return as_root(True) + ["pacman", "-Rns", "--noconfirm", target], None
    if action == "cmd":
        return ["bash", "-c", target], None
    raise ValueError("Unknown journal action: " + action)


def rollback(journal, want):
    lines = journal.read_text().splitlines(keepends=True)
    rows = [line.rstrip("\n").split("\t") for line in lines]
    selected = {i for i, row in enumerate(rows) if len(row) >= 4 and (want == "all" or row[1] == want)}
    # Check before executing anything: older snapshots cannot overwrite later work.
    touched = [keys(row) if len(row) >= 4 else set() for row in rows]
    for i in selected:
        if any(j > i and j not in selected and touched[i] & touched[j] for j in range(len(rows))):
            print("Rollback conflicts with a later experiment: " + rows[i][3], file=sys.stderr)
            return 1
    for i in sorted(selected, reverse=True):
        row = rows[i]
        action, target = row[2:4]
        try:
            command, note = command_for(action, target, row[4] if len(row) > 4 else "")
        except ValueError as error:
            print(error, file=sys.stderr)
            return 1
        if command is None:
            print(f"Rollback: {action} {target} ({note})", flush=True)
        else:
            print("Rollback:", action, target, flush=True)
            if subprocess.run(command).returncode:
                print("Rollback failed; this and earlier records retained", file=sys.stderr)
                return 1
        lines[i] = ""
        temp = journal.with_suffix(".tmp")
        temp.write_text("".join(lines))
        temp.replace(journal)
    return 0


if __name__ == "__main__":
    sys.exit(rollback(Path(sys.argv[1]), sys.argv[2]))
