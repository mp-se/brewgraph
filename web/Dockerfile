FROM node:22-alpine AS build

# NOTE: this image builds from the REPOSITORY ROOT as context, not from web/.
#
# `src/modules/backup/validateDocument.ts` imports the two JSON Schemas from
# `api/oss/` — one definition shared by the API, the API's tests, the web tests
# and the bundle. rollup resolves that import at build time, so the files have to
# be inside the build context; with `context: ./web` the build fails with
# "Could not resolve ../../../../api/oss/export-v1.schema.json".
#
# The layout under /app mirrors the repository (/app/web + /app/api/oss) so the
# relative import resolves unchanged and the source needs no build-only special
# case. Duplicating the schemas into web/ would also have fixed the build, at the
# cost of two copies of a contract that exists precisely to be single.
#
# See .dockerignore at the repo root for what the context excludes.
WORKDIR /app/web

ARG GIT_HASH=unknown

# Install the exact lockfile dependency tree used by CI.
COPY web/package.json web/package-lock.json* ./
RUN npm ci

# Schemas first: they change far less often than web sources, so this layer
# stays cached across ordinary frontend edits.
COPY api/oss/export-v1.schema.json api/oss/brewlogger-import.schema.json /app/api/oss/

# Build
COPY web/ ./
RUN VITE_APP_BUILD=${GIT_HASH} npm run build

# ---- Runtime image ----
FROM nginx:1.30-alpine AS runtime

# Apply security patches from Alpine package repo
RUN apk upgrade --no-cache && apk add --no-cache jq

RUN mkdir -p /etc/nginx/templates /etc/nginx/ssl

COPY web/ngnix/nginx.http.conf  /etc/nginx/templates/nginx.http.conf
COPY web/ngnix/nginx.https.conf /etc/nginx/templates/nginx.https.conf
COPY web/ngnix/entrypoint.sh    /entrypoint.sh

COPY --from=build /app/web/dist /usr/share/nginx/html

# Normalise permissions on the static root.
#
# Docker COPY preserves the source file mode, and Vite copies public/ into dist/
# the same way — so a file checked out or created with a restrictive umask (0600
# is common) stays unreadable all the way into this image. nginx's worker runs as
# a different user and answers 403 Forbidden for it, which reads like a missing
# file rather than a permission problem.
#
# That is exactly what happened to public/favicon.ico. env-config.js had the same
# fault and was patched individually in entrypoint.sh; this covers the whole
# directory so the next file added to public/ cannot repeat it.
#
# a+rX, not a+rx: capital X sets the traverse bit on directories without marking
# every asset executable.
RUN chmod -R a+rX /usr/share/nginx/html

RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
