.PHONY: check test build diff apply status
PYTHON ?= python3

check:
	$(PYTHON) tools/desktop.py check

test: check
	$(PYTHON) -m unittest discover -s tests -v
	xvfb-run -a $(PYTHON) tests/gtk_smoke.py

build: check
	$(PYTHON) tools/desktop.py build

diff: build
	$(PYTHON) tools/desktop.py diff

apply: test build
	$(PYTHON) tools/desktop.py apply

status:
	$(PYTHON) tools/desktop.py status
