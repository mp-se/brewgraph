#!/bin/sh
set -e

echo "Starting BrewGraph Web"
echo "API host: ${API_HOST:-brewgraph-api}"
echo "API key: $([ -n "${API_KEY}" ] && echo "(set)" || echo "(not set)")"

# Inject a JSON-encoded runtime API key so quotes, slashes, and newlines cannot
# escape the JavaScript string literal. jq is installed in the runtime image.
API_KEY_JSON=$(printf '%s' "${API_KEY:-}" | jq -Rs .)
printf 'window.VITE_APP_TOKEN=%s;\n' "$API_KEY_JSON" > /usr/share/nginx/html/env-config.js
chmod 644 /usr/share/nginx/html/env-config.js

# Select HTTP or HTTP+HTTPS config based on SSL cert presence
if [ -f /etc/nginx/ssl/server.crt ] && [ -f /etc/nginx/ssl/server.key ]; then
  echo "SSL certificates found — using HTTP+HTTPS"
  envsubst '${API_HOST}' < /etc/nginx/templates/nginx.https.conf > /etc/nginx/conf.d/default.conf
else
  echo "No SSL certificates — using HTTP only"
  envsubst '${API_HOST}' < /etc/nginx/templates/nginx.http.conf > /etc/nginx/conf.d/default.conf
fi

nginx -t
nginx -g "daemon off;"
