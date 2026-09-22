#!/usr/bin/env python3
"""Rollback with conflict detection and durable failure records."""
import os
from pathlib import Path
import subprocess
import sys


def rollback(journal, want):
    lines = journal.read_text().splitlines(keepends=True)
    rows = [line.rstrip("\n").split("\t") for line in lines]
    selected = {i for i, row in enumerate(rows) if len(row) >= 4 and (want == "all" or row[1] == want)}
    # Check before executing anything: older snapshots cannot overwrite later work.
    for i in selected:
        row = rows[i]
        if row[2] in ("backup", "file"):
            if any(j not in selected and later[2] in ("backup", "file") and later[3] == row[3]
                   for j, later in enumerate(rows) if j > i and len(later) >= 4):
                print("Rollback conflicts with a later experiment: " + row[3], file=sys.stderr)
                return 1
    for i in sorted(selected, reverse=True):
        row = rows[i]
        action, target = row[2:4]
        root = [] if os.geteuid() == 0 else ["sudo"]
        if action == "backup":
            if len(row) < 5 or not Path(row[4]).is_file():
                print("Missing backup; journal retained: " + target, file=sys.stderr)
                return 1
            command = root + ["cp", "-a", "--remove-destination", row[4], target]
        elif action == "file":
            command = root + ["rm", "-f", target]
        elif action == "pkg":
            command = root + ["pacman", "-Rns", "--noconfirm", target]
        elif action == "cmd":
            command = ["bash", "-c", target]
        else:
            print("Unknown journal action: " + action, file=sys.stderr)
            return 1
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
