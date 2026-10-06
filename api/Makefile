.PHONY: install install-test compile compile-test test test-cov lint fmt run

VENV_PYTHON ?= ../.venv/bin/python
PIP        ?= pip

# ── Setup ─────────────────────────────────────────────────────────────────────

install:
	$(PIP) install -r requirements/requirements.txt

install-test:
	$(PIP) install -r requirements/test-requirements.txt

compile:
	pip-compile requirements/requirements.in -o requirements/requirements.txt
	pip-compile requirements/test-requirements.in -o requirements/test-requirements.txt

# ── Testing ───────────────────────────────────────────────────────────────────

test:
	CACHE_ENABLED=false $(VENV_PYTHON) -m pytest tests/

test-cov:
	CACHE_ENABLED=false $(VENV_PYTHON) -m pytest tests/ --cov=core --cov=oss --cov-report=term-missing --cov-report=html

# ── Lint / Format ─────────────────────────────────────────────────────────────

lint:
	$(VENV_PYTHON) -m pylint main_oss.py core oss tests

format:
	$(VENV_PYTHON) -m isort main_oss.py core tests

# ── Dev server ────────────────────────────────────────────────────────────────

run:
	DATABASE_URL=sqlite:///./brewgraph.sqlite \
	API_KEY=devkey \
	API_KEY_ENABLED=false \
	SCHEDULER_ENABLED=false \
	CACHE_ENABLED=false \
	uvicorn main_oss:app --reload --host 0.0.0.0 --port 8080
