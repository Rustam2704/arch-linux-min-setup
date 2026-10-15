# Fix task B3: installer and lab journal (audit `research/audit-2026-10-15/b-daemons.md`, B20–B25, B26 installer part)
Rules: `tools/audit/fix-common.md`. Files you may edit: `tools/desktop.py`, `lab/lab`, `lab/rollback.py`,
`Makefile`, new tests under `tests/` (e.g. `tests/test_installer.py`), MAINTENANCE.md lines about these.
NEVER run apply/rollback against the real system or the real `lab/journal.tsv`: tests must use a temp
tree (temp HOME, temp root prefix, temp journal) — add an environment override for the journal path and
target root if needed, defaulting to today's behaviour. Do not rewrite or reformat existing journal records;
new record types must stay backward compatible with the existing TSV.
Fix: B20 (install manifest; `status`/`diff` report targets whose source was deleted; `apply` removes
them via a journaled `lab remove`; prune stale `.build/desktop`), B21 (elevate per target: no sudo for paths
the user can write; root-created directories removed with the matching privilege), B22 (structured
xfconf records with channel/property, included in conflict checking — old `cmd` records stay as they are),
B23 (expected mode in drift detection; mode-only fixes journaled), B24 (query live xfconf values via
xfconf-query for status/undo — read-only queries only in tests, or mock them), B25 (journal record
written only after the mutation succeeded, or a prepared/applied pair; staged temp files cleaned on error).
B26: temp-tree tests for deletion, modes, first-install rollback, directories, xfconf conflict ordering.
Also run `make status` on the real tree at the end (read-only) and report what it now shows (e.g. targets
of deleted sources) — do NOT apply anything.
