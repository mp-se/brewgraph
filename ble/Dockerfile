FROM python:3.13-slim

WORKDIR /app

ENV PYTHONFAULTHANDLER=1
ENV PYTHONUNBUFFERED=1

# bluez: HCI tools for host-side BLE; libcap2-bin: setcap
# gcc + python3-dev: needed by some bleak back-ends at compile time
# upgrade: security fixes without waiting for a new base image
RUN apt-get update \
 && apt-get upgrade -y --no-install-recommends \
 && apt-get install -y --no-install-recommends bluez libcap2-bin gcc python3-dev \
 && rm -rf /var/lib/apt/lists/*

COPY requirements/requirements.in /app/requirements.in

# Nothing installs packages at runtime; pip only adds its vendored libraries to the image.
RUN pip install --no-cache-dir -r requirements.in \
 && pip uninstall -y pip

COPY scan.py /app/

# Allow BLE scanning without running as root
RUN setcap 'cap_net_raw,cap_net_admin+eip' "$(readlink -f "$(which python3)")"

CMD ["python3", "scan.py"]
