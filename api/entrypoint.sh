#!/bin/bash
set -e

echo "Starting BrewGraph API v$(python3 -c 'from core.config import get_settings; print(get_settings().version)' 2>/dev/null || echo '2.0.0')"
DB_DISPLAY=$(python3 -c "
from urllib.parse import urlparse
u = urlparse('${DATABASE_URL:-sqlite:////data/brewgraph.sqlite}')
print(f'{u.scheme}://***@{u.hostname}{u.path}' if u.password else u.geturl())
" 2>/dev/null || echo "(unable to parse)")
echo "Database: ${DB_DISPLAY}"
echo "API key auth enabled: ${API_KEY_ENABLED:-true}"
echo "Scheduler enabled: ${SCHEDULER_ENABLED:-true}"
echo "Cache enabled: ${CACHE_ENABLED:-false}"

echo "Running database migrations..."
alembic upgrade head

exec uvicorn main_oss:app \
    --host 0.0.0.0 \
    --port 80 \
    --log-config log_conf.yaml
