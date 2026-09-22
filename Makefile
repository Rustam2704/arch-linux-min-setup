.PHONY: check test build diff apply status packages rollback
PYTHON ?= python3
# Every apply is journaled under an experiment id: make apply EXP=33-short-name
EXP ?= desktop-apply

check:
	$(PYTHON) tools/desktop.py check

test: check
	$(PYTHON) -m unittest discover -s tests -v
	xvfb-run -a $(PYTHON) tests/gtk_smoke.py

build: check
	$(PYTHON) tools/desktop.py build

diff: build
	$(PYTHON) tools/desktop.py diff

status:
	$(PYTHON) tools/desktop.py status

packages:
	$(PYTHON) tools/desktop.py packages

apply: test build
	LAB_EXPERIMENT=$(EXP) $(PYTHON) tools/desktop.py apply

rollback:
	lab/lab rollback $(EXP)
