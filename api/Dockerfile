FROM python:3.13-slim

WORKDIR /app

ENV PYTHONFAULTHANDLER=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Install system dependencies and apply security patches
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements/requirements.txt /app/requirements.txt
# Nothing installs packages at runtime; pip only adds its vendored libraries to the image.
RUN pip install --no-cache-dir --upgrade -r /app/requirements.txt \
    && pip uninstall -y pip

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
