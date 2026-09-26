# Membership Lookup and Registry — short commands (npm-run style).
# Usage: make <target>  (e.g. make setup, make seed, make tui, make test)
# All targets use .venv/bin/python directly, so no `source .venv/bin/activate`
# needed. Windows PowerShell equivalent: .venv\Scripts\python.exe <same args>.

PY := .venv/bin/python
APP := src/membership_registry/app.py
TUI := src/membership_registry/app_textual.py
SEED := src/membership_registry/seed.py
N ?= 12

.PHONY: help setup seed app tui list search test test-verbose clean

help: ## show this list
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | sed 's/:.*## /  —  /'

setup: ## create .venv + install requirements
	python3 -m venv .venv
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements.txt

seed: ## seed sample entries (N=12, RESET=1 to wipe first) — make seed N=20 / RESET=1
	$(PY) $(SEED) --count $(N) $(if $(RESET),--reset,)

app: ## classic menu CLI/TUI (stdlib only)
	$(PY) $(APP)

tui: ## interactive Textual TUI (live table, mouse, sidebar, buttons)
	$(PY) $(TUI)

list: ## list members — make list STATUS=ACTIVE
	$(PY) $(APP) list $(if $(STATUS),--status $(STATUS),)

search: ## search — make search q=Sntos [STATUS=ACTIVE] [EXACT=1 for --no-fuzzy]
	@if [ -z "$(q)" ]; then echo "usage: make search q=<query>"; exit 2; fi
	$(PY) $(APP) search "$(q)" $(if $(STATUS),--status $(STATUS),) $(if $(EXACT),--no-fuzzy,)

test: ## edge-case tests on a TEMPORARY db (main db untouched)
	$(PY) -m unittest discover -s tests

test-verbose: ## same, verbose
	$(PY) -m unittest discover -s tests -v

clean: ## drop caches
	find . -name __pycache__ -type d -not -path "./.venv/*" -exec rm -rf {} + 2>/dev/null; true
