.PHONY: install compile lint format run test test-integration

VENV_PYTHON ?= ../.venv/bin/python
PIP        ?= pip

# ── Setup ─────────────────────────────────────────────────────────────────────

install:
	$(PIP) install -r requirements/requirements.txt

compile:
	pip-compile requirements/requirements.in -o requirements/requirements.txt

# ── Lint ──────────────────────────────────────────────────────────────────────

lint:
	$(VENV_PYTHON) -m pylint scan.py tests

format:
	$(VENV_PYTHON) -m isort scan.py tests

# ── Test ──────────────────────────────────────────────────────────────────────

test:
	$(VENV_PYTHON) -m pytest tests/test_parsers.py -v

test-integration:
	API_HOST=localhost:8080 \
	API_KEY=devkey \
	$(VENV_PYTHON) -m pytest tests/test_client.py -m integration -v

# ── Run ───────────────────────────────────────────────────────────────────────

run:
	API_HOST=localhost \
	API_KEY=devkey \
	$(VENV_PYTHON) scan.py
