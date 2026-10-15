# Fix task A: deskd (audit `research/audit-2026-10-15/a-deskd.md`)
Rules: `tools/audit/fix-common.md`. Files you may edit: `desktop/share/deskd/*.py`,
`desktop/share/sky-desktop/i3ipc.py`, `desktop/bin/deskd-favorites`, `desktop/bin/deskd-ctl`,
`tests/deskd_smoke.py`, `tests/deskd_bench.py`, docs lines about these in ARCHITECTURE.md/FEATURES.md
only if a fix changes documented behaviour.
Fix: A2, A3, A4, A7, A8, A9, A11, A12, A13, A14; A5 (cheap validation on the relevant i3 events);
A6 (log unexpected X errors — but only once per (opcode, error type) per minute so the journal is not
flooded; keep ignoring BadWindow/BadDrawable races); A10 (defer output reconciliation until a gesture
ends); A1 + A16 in the harness (readiness marker / wait-until-converged with deadlines and a diagnostic
dump on failure) and, if you find the engine race, the engine fix. Then run `make test-deskd` (Xephyr :9 —
allowed for this harness) up to 4 times and report pass counts; run `tests/deskd_bench.py` once and
report whether the request counts changed versus round 66 (279/3, 185/8, 86/43, 3/0).
