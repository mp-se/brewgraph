# BrewGraph

Self-hosted homebrewing telemetry platform. Ingests gravity and pressure readings from physical sensors and tracks batches through their full lifecycle — fermenting → conditioning → kegged or bottled.

Runs entirely on your local network via Docker Compose. No cloud account required.

> **Note:** BrewGraph is the successor to [BrewLogger](https://github.com/mp-se/brewlogger). The brewlogger.com domain was already taken, so the project was renamed and rebuilt as BrewGraph. Existing BrewLogger backups can be imported directly via the restore feature. BrewGraph can be seen as BrewLogger v2.0 since it has a new datamodel and new features.

> **Security notice:** BrewGraph is designed for trusted LAN deployment only. The shared API key authenticates the **web UI** and is delivered to the browser in a static file; IoT devices do not use it — they post to the open ingest endpoints with their own per-device tokens. Do not expose BrewGraph to the public internet. If remote access is needed, use a VPN (WireGuard, Tailscale) or a reverse proxy with its own auth layer. See [Security model & accepted tradeoffs](#security-model--accepted-tradeoffs) for the full threat model.

---

## Features

- Ingest gravity and temperature readings from iSpindel-compatible devices over HTTP
- Ingest pressure readings from PressureMon devices
- BLE ingestion via a sidecar for wireless sensors (Linux only)
- Automatic device discovery via mDNS/Bonjour (Requires Linux host)
- Batch lifecycle management with fermentation-step and dry-hop tracking, plus per-batch notes
- Gravity, pressure, and temperature charts per batch, plus gravity comparison across batches
- Fermentation completion prediction via a machine learning model
- Yeast strain library with batch assignment (Used for improving machine learning result)
- Batch data export (gravity CSV, pressure CSV, batch JSON)
- Brewfather batch/recipe import
- BeerXML recipe import
- Tap and keg management with pour tracking
- Storage vessel management
- Public tap and bottle display
- Configurable measurement-forwarding integrations
- System, device, and ingestion event logs
- Backup and restore of all data
- REST API with interactive OpenAPI docs
- Vue 3 single-page web UI for desktops
- API key authentication
- PostgreSQL backend (SQLite for local development/testing only, not a deployment option)

---

## Requirements

- Docker Engine 24+ and Docker Compose v2
- Linux, macOS, or Windows (WSL2) host
- For BLE ingestion: Linux host with Bluetooth hardware and BlueZ
- For mDNS discovery: `network_mode: host` support (Linux required)

---

## Quick start — pre-built images

The recommended path for most users. Images are published to Docker Hub under `mpse2/brewgraph-*`.

**1. Download the compose file**

```bash
curl -o docker-compose.yaml https://raw.githubusercontent.com/mp-se/brewgraph/main/docker-compose.example.yaml
```

**2. Create a `.env` file with your API key**

```bash
cat > .env <<'EOF'
API_KEY=replace-with-a-long-random-secret
POSTGRES_PASSWORD=replace-with-a-unique-database-password
EOF
```

**3. Start the core services**

```bash
docker compose up -d
```

The web UI is available at `http://localhost:80`. The API is accessible internally at `brewgraph-api:8080` and through the Nginx proxy at `http://localhost:80/api`.

> **Note:** The interactive API docs (`/docs`) are blocked at the Nginx proxy for security. Access them directly on the API's own port instead: `http://localhost:8080/docs`.

---

## Optional services

The default Compose configuration starts all services. The API, database, Redis,
web UI, and display service form the default stack; the remaining sidecars enable
specific capabilities:

| Service | Required | When to enable |
|---|---|---|
| `brewgraph-api` | Yes | Always |
| `brewgraph-db` | Yes | Always |
| `brewgraph-redis` | Yes (default configuration) | Required for caching and integrations; can be disabled only when caching and integrations are unused |
| `brewgraph-web` | Yes | Needed for the web UI |
| `brewgraph-display` | Yes | Public tap and bottle display |
| `brewgraph-log` | No | Device log collection via device websocket API |
| `brewgraph-mdns` | No | Auto-discovery of devices on the LAN (Linux only) |
| `brewgraph-ble` | No | BLE ingestion for GravityMon / PressureMon / ChamberCtl (Linux only) |
| `brew_pgadmin` | No | Optional database management UI |

**Redis is load-bearing for Integrations, not just an optional cache.** Measurement
forwarding (Settings → Integrations) queues each job on Redis at ingest time and drains it in
the background; with `CACHE_ENABLED=false` or Redis unreachable, `enqueue_forward` logs a
warning and drops the job — the reading itself still saves, but nothing gets forwarded, with
no error surfaced anywhere in the UI. If you use Integrations, run `brewgraph-redis`.

---

## Quick start — build from source

Use this path if you want to modify the code or run the latest unreleased version.

```bash
git clone https://github.com/mp-se/brewgraph.git
cd brewgraph
cp docker-compose.example.yaml docker-compose.yaml
cat > .env <<'EOF'
API_KEY=replace-with-a-long-random-secret
POSTGRES_PASSWORD=replace-with-a-unique-database-password
EOF
docker compose build
docker compose up -d
```

---

## Services

| Service | Image | Purpose |
|---|---|---|
| `brewgraph-api` | `mpse2/brewgraph-api` | FastAPI backend, REST API, scheduler |
| `brewgraph-db` | `postgres:17-alpine` | Primary database |
| `brewgraph-redis` | `redis:7-alpine` | Ephemeral state cache |
| `brewgraph-web` | `mpse2/brewgraph-web` | Vue 3 UI served by Nginx (HTTP or HTTPS) |
| `brewgraph-display` | `mpse2/brewgraph-display` | Public tap and bottle display |
| `brewgraph-log` | `mpse2/brewgraph-log` | Collects device serial logs over WebSocket |
| `brewgraph-mdns` | `mpse2/brewgraph-mdns` | Auto-discovers devices via mDNS/Bonjour (Linux only) |
| `brewgraph-ble` | `mpse2/brewgraph-ble` | BLE ingestion from wireless sensors (Linux only) |

> `brewgraph-ble` and `brewgraph-mdns` use `network_mode: host` and only work on Linux. On macOS they start but cannot access LAN multicast or the host Bluetooth stack.

---

## Environment variables

### API (`brewgraph-api`)

| Variable | Required | Default | Description |
|---|---|---|---|
| `DATABASE_URL` | Yes | — | SQLAlchemy URL for the PostgreSQL database. Set automatically by `docker-compose.yaml` |
| `API_KEY` | Yes | — | Bearer token for authenticated UI and management API requests; ingest endpoints use per-device tokens |
| `API_KEY_ENABLED` | No | `true` | Set `false` to disable auth (dev only) |
| `SCHEDULER_ENABLED` | No | `true` | Enable background jobs |
| `CACHE_ENABLED` | No | `true` | Enable Redis cache |
| `REDIS_HOST` | No | — | Redis hostname (required if `CACHE_ENABLED=true`) |
| `TRUST_PROXY_HEADERS` | No | `false` | Trust `X-Real-IP` from a reverse proxy. Set `true` when behind Nginx. |
| `AUTH_MAX_FAILURES` | No | `10` | Failed auth attempts before IP block |
| `AUTH_BLOCK_SECONDS` | No | `300` | Seconds an IP stays blocked after too many failures |
| `BREWFATHER_USER_KEY` | No | — | Brewfather integration user key |
| `BREWFATHER_API_KEY` | No | — | Brewfather integration API key |

### Web (`brewgraph-web`)

| Variable | Required | Description |
|---|---|---|
| `API_HOST` | Yes | Hostname of `brewgraph-api` (e.g. `brewgraph-api`) |
| `API_KEY` | Yes | Must match the API's `API_KEY` |

### Log sidecar (`brewgraph-log`)

| Variable | Default | Description |
|---|---|---|
| `API_HOST` | — | Hostname of `brewgraph-api` |
| `API_KEY` | — | Bearer token |
| `REDIS_HOST` | — | Redis hostname (optional) |
| `MAX_FILE_SIZE` | `100000` | Bytes before log rotation |

### BLE sidecar (`brewgraph-ble`)

| Variable | Default | Description |
|---|---|---|
| `API_HOST` | — | Use `localhost` with host networking |
| `API_KEY` | — | Bearer token |
| `REDIS_HOST` | — | Redis hostname (optional) |
| `MIN_INTERVAL` | `900` | Min seconds between posts per device |

---

## HTTPS (optional)

Place your certificate and key in `web/certs/`, named exactly:

```
web/certs/server.crt
web/certs/server.key
```

Then, in `docker-compose.yaml`, uncomment both the `brewgraph-web` volume mount and the
`443:443` port mapping:

```yaml
  brewgraph-web:
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./web/certs:/etc/nginx/ssl:ro
```

The Nginx entrypoint detects the certificate files and switches to HTTP+HTTPS automatically.
Without the port mapping above, HTTPS is enabled inside the container but unreachable from
outside it.

---

## Updating

**Pre-built images:**

```bash
docker compose pull
docker compose up -d
```

**Built from source:**

```bash
git pull
docker compose build
docker compose up -d
```

---

## Development

### API

```bash
cd api
make install-test   # install deps including test extras
make run            # dev server on :8080 (SQLite, auth disabled)
make test           # run test suite
make lint           # pylint
make fmt            # autoformat
```

### Web

```bash
cd web
npm install
npm run dev         # dev server on :5173 (proxies API to localhost:8080)
npm run test        # Vitest unit tests
npm run lint        # ESLint
```

---

## Supported devices

| Device | Protocol | Ingest endpoint |
|---|---|---|
| iSpindel | HTTP | `/ingest/ispindel` |
| GravityMon | HTTP / BLE | `/ingest/gravitymon` |
| GravityMon Gateway | HTTP | `/ingest/gravitymon` |
| PressureMon | HTTP / BLE | `/ingest/pressuremon` |
| KegMon | HTTP | `/ingest/kegmon` |
| ChamberCtl | HTTP / BLE | `/ingest/chamber` |

---

## Security model & accepted tradeoffs

BrewGraph OSS targets a **single trusted operator on a private LAN**. The items
below are deliberate design decisions for that threat model — they are **not**
findings, and should not be re-reported in security reviews of the OSS build.

### Trust boundary

The LAN is trusted: anyone who can reach the web UI is treated as the operator.
Do not expose BrewGraph to the public internet. For remote access use a VPN
(WireGuard/Tailscale) or a reverse proxy that adds its own authentication.

### Accepted by design (LAN)

| Area | Decision | Rationale |
|---|---|---|
| API key in the SPA | The web container injects `API_KEY` into a static `env-config.js` that the browser reads. | The key is a **web-UI credential only**. Any LAN client is already trusted, and without TLS (which most LAN deployments skip) a bootstrap handshake would add no real protection. |
| Open ingest endpoints | `/ingest/*` requires no API key. | IoT firmware (iSpindel, GravityMon, PressureMon, KegMon…) authenticates with a **per-device token** in the payload; endpoints are per-IP rate-limited and per-device throttled. |
| CORS `allow_origins: *` | Wildcard origin with `allow_credentials=false`. | No cookies are used and auth is a bearer header, so a wildcard origin cannot drive cross-site credentialed attacks. Simplifies serving the UI and API from different origins/ports. |
| Single shared API key | One full-privilege bearer token, no per-user roles. | Single-operator deployment — there are no other users to isolate. |
| Best-effort rate limiting | Auth brute-force blocking, ingest rate limits, and device throttling require Redis (`CACHE_ENABLED=true`) and no-op if Redis is unavailable. | The API key is a 128-bit `secrets.token_urlsafe` value, so online brute force is infeasible regardless. The limiter is defense-in-depth against device abuse, not the primary control. |
| `API_KEY_ENABLED=false` | Auth can be disabled entirely. | Local development only — never set this in a real deployment. |
| `proxy_fetch` reaches LAN hosts | The authenticated UI can proxy requests to private (RFC1918) IPs; cloud-metadata, loopback, and link-local targets are blocked, and the resolved IP is pinned against DNS rebinding. | Configuring physical devices on the LAN is the intended feature, and the caller is already the trusted operator. |

### Still enforced (do not weaken)

- API key compared with `hmac.compare_digest` (constant-time).
- `proxy_fetch` rejects public, loopback, and link-local targets and pins the
  resolved IP to prevent DNS rebinding.
- Secrets are stored as `SecretStr` and redacted from logs.
- Containers run as a non-root user; CSP and security headers are set at the edge.

---

## License

BrewGraph is licensed under the [GNU General Public License v3.0](LICENSE) for open source use. For commercial use without source disclosure, a separate Commercial License is required.

© 2024–2026 Magnus Persson
