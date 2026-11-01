# Download target wheels natively so dependency installation avoids QEMU.
FROM --platform=$BUILDPLATFORM python:3.13-slim AS build
ARG TARGETARCH
WORKDIR /build
COPY requirements/requirements.txt ./requirements.txt
RUN case "$TARGETARCH" in \
        amd64) arch=x86_64 ;; \
        arm64) arch=aarch64 ;; \
        *) echo "unsupported TARGETARCH: $TARGETARCH" >&2; exit 1 ;; \
    esac \
    && pip install --no-cache-dir --no-deps --only-binary=:all: --target /deps \
        --platform "manylinux2014_$arch" --platform "manylinux_2_17_$arch" --platform "manylinux_2_28_$arch" \
        --implementation cp --python-version 3.13 -r requirements.txt \
    && python -m compileall -q /deps \
    && mv /deps/bin /scripts

FROM python:3.13-slim AS runtime

WORKDIR /app

ENV PYTHONFAULTHANDLER=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Install system dependencies and apply security patches
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Runtime package installation is disabled; remove the bundled installer.
RUN cd /usr/local/lib/python3.13/site-packages \
    && rm -rf pip pip-* \
    && rm -f /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.*

# Copy target-platform dependencies and their command-line entry points.
COPY --from=build /deps /usr/local/lib/python3.13/site-packages
COPY --from=build /scripts/uvicorn /usr/local/bin/uvicorn
COPY --from=build /scripts/alembic /usr/local/bin/alembic

# Copy application code
COPY core /app/core
COPY migrations /app/migrations
COPY alembic.ini /app/alembic.ini
COPY oss /app/oss
COPY main_oss.py /app/main_oss.py
COPY log_conf.yaml /app/log_conf.yaml
COPY data /app/data

# Create log and data dirs
RUN mkdir -p /app/log /data

# Remove any local sqlite files that may have been copied
RUN rm -f /app/*.sqlite /app/*.sqlite3

COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

RUN adduser --disabled-password --gecos "" appuser \
    && chown -R appuser /app /data
USER appuser

ENTRYPOINT ["/app/entrypoint.sh"]
