.PHONY: help up down logs build deploy restart clean security scan

# Colors for output
YELLOW := \033[0;33m
GREEN := \033[0;32m
NC := \033[0m # No Color

help:
	@echo "$(YELLOW)BrewGraph — Docker Compose targets$(NC)"
	@echo ""
	@echo "$(GREEN)Main targets:$(NC)"
	@echo "  make up              Build and start services (with automatic git hash)"
	@echo "  make build           Build images (with automatic git hash)"
	@echo "  make deploy          Full rebuild & deploy (with automatic git hash)"
	@echo "  make down            Stop all services"
	@echo "  make restart         Restart all services"
	@echo "  make logs            Follow logs from all services"
	@echo "  make clean           Stop services and remove volumes"
	@echo ""
	@echo "$(GREEN)Component logs:$(NC)"
	@echo "  make logs-api        API logs"
	@echo "  make logs-web        Web logs"
	@echo "  make logs-db         Database logs"
	@echo "  make logs-redis      Redis logs"
	@echo ""
	@echo "$(GREEN)Security:$(NC)"
	@echo "  make security        Audit dependencies (npm + pip) and scan images"
	@echo "  make scan            Trivy CVE scan of built Docker images"
	@echo ""

up:
	@export GIT_HASH=$$(git rev-parse --short HEAD) && \
	echo "$(GREEN)Building and starting services with git hash: $$GIT_HASH$(NC)" && \
	docker compose build --build-arg GIT_HASH="$$GIT_HASH" && \
	docker compose up -d

build:
	@export GIT_HASH=$$(git rev-parse --short HEAD) && \
	echo "$(GREEN)Building images with git hash: $$GIT_HASH$(NC)" && \
	docker compose build --build-arg GIT_HASH="$$GIT_HASH"

deploy: clean up
	@echo "$(GREEN)✓ BrewGraph deployed successfully$(NC)"
	@echo "Web UI:  http://localhost"
	@echo "API:     http://localhost:8080"

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

logs-api:
	docker compose logs -f brewgraph-api

logs-web:
	docker compose logs -f brewgraph-web

logs-db:
	docker compose logs -f brewgraph-db

logs-redis:
	docker compose logs -f brewgraph-redis

clean:
	@echo "$(YELLOW)Stopping services and removing volumes...$(NC)"
	docker compose down -v
	@echo "$(GREEN)Clean complete$(NC)"

ps:
	docker compose ps

shell-api:
	docker compose exec brewgraph-api sh

shell-web:
	docker compose exec brewgraph-web sh

shell-db:
	docker compose exec brewgraph-db psql -U postgres -d app

prune:
	docker system prune -f

## Audit known vulnerabilities in all dependency trees, then scan images.
## Requires: pip-audit (.venv/bin/pip install pip-audit) and trivy (brew install trivy).
## pip findings should be fixed in requirements/*.in then re-compiled, not edited by hand.
security: scan
	@echo "$(GREEN)==> web: npm audit$(NC)"
	cd web && npm audit
	@echo "$(GREEN)==> api: pip-audit$(NC)"
	.venv/bin/pip install -q pip-audit
	.venv/bin/pip-audit -r api/requirements/requirements.txt

## Scan built Docker images for OS + dependency CVEs using Trivy.
## Requires: brew install trivy (or https://trivy.dev/latest/getting-started/installation/).
## Fails on HIGH or CRITICAL severity findings.
scan:
	$(eval SHA := scan)
	@echo "$(GREEN)Building images for scan...$(NC)"
	docker build -q -t brewgraph-api:$(SHA) api > /dev/null
	docker build -q -t brewgraph-web:$(SHA) -f web/Dockerfile . > /dev/null
	@echo "$(GREEN)==> Scanning brewgraph-api$(NC)"
	trivy image --exit-code 1 --severity HIGH,CRITICAL --ignore-unfixed brewgraph-api:$(SHA)
	@echo "$(GREEN)==> Scanning brewgraph-web$(NC)"
	trivy image --exit-code 1 --severity HIGH,CRITICAL --ignore-unfixed brewgraph-web:$(SHA)
