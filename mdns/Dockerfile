FROM python:3.13-slim

WORKDIR /app

ENV PYTHONFAULTHANDLER=1
ENV PYTHONUNBUFFERED=1

# avahi + nss-mdns are required for mDNS resolution on Linux
# upgrade: security fixes without waiting for a new base image
RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && apt-get install -y --no-install-recommends avahi-utils libnss-mdns \
 && rm -rf /var/lib/apt/lists/*

COPY requirements/requirements.txt /app/requirements.txt

# Nothing installs packages at runtime; pip only adds its vendored libraries to the image.
RUN pip install --no-cache-dir -r requirements.txt \
 && pip uninstall -y pip

COPY mdns.py /app/
COPY entrypoint.sh /entrypoint.sh

RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
