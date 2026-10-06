.PHONY: install compile lint format test run

VENV_PYTHON ?= ../.venv/bin/python
PIP        ?= pip

# ── Setup ─────────────────────────────────────────────────────────────────────

install:
	$(PIP) install -r requirements/requirements.txt

compile:
	pip-compile requirements/requirements.in -o requirements/requirements.txt

# ── Testing ───────────────────────────────────────────────────────────────────

test:
	$(VENV_PYTHON) -m pytest tests/

# ── Lint ──────────────────────────────────────────────────────────────────────

lint:
	$(VENV_PYTHON) -m pylint logcollector.py

format:
	$(VENV_PYTHON) -m isort logcollector.py tests

# ── Run ───────────────────────────────────────────────────────────────────────

run:
	API_HOST=localhost \
	API_KEY=devkey \
	$(VENV_PYTHON) logcollector.py
