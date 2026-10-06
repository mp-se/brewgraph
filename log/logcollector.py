# BrewGraph
# Copyright (c) 2021-2026 Magnus
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Alternatively, this software may be used under the terms of a
# commercial license. See LICENSE_COMMERCIAL for details.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.
#

"""Collect serial logs from registered devices via their websocket serial endpoint.

Required env vars:
- API_HOST: Hostname/IP of the API (e.g. brewgraph-api)
- API_KEY: API key for authentication

Optional env vars:
- REDIS_HOST: Redis hostname for status sharing
- MAX_FILE_SIZE: Maximum log file size in bytes before rotation
"""
import asyncio
import logging
import os
import threading
from time import time

import redis
import requests
from websockets.exceptions import WebSocketException
from websockets.sync.client import connect

logger = logging.getLogger(__name__)

# Redis keys written per device:
#   log_<chipId>_start : connect timestamp
#   log_<chipId>_last  : last-message timestamp
#   log_<chipId>_count : total lines received
#   log_<chipId>_size  : total bytes received

endpoint = ""
headers = {}
threads = {}
max_file_size = 100000
pool = None


def write_key(key, value):
    """Write a telemetry key to Redis if Redis status sharing is enabled."""
    if pool is None:
        return True

    ttl = 60 * 60 * 6  # 6 hours

    logger.info("Writing key %s = %s ttl:%d.", key, value, ttl)
    try:
        r = redis.Redis(connection_pool=pool)
        r.set(name=key, value=str(value), ex=ttl)
        return True
    except redis.exceptions.ConnectionError as e:
        logger.error("Failed to connect with redis: %s.", e)
    return False


class ThreadWrapper:
    """Container for a worker thread and its cooperative stop signal."""

    def __init__(self):
        """Initialize an empty thread wrapper."""
        self.thread = None
        self.event = threading.Event()

    def is_stopped(self):
        """Return True when a stop request has been signaled."""
        return self.event.is_set()

    def is_alive(self):
        """Return True when the underlying worker thread is alive."""
        return self.thread.is_alive()

    def stop(self):
        """Signal the worker loop to stop."""
        self.event.set()


def websocket_collector(url, chip_id):
    """Consume websocket serial output for one device and append to its log file."""
    uri = url.replace("http://", "ws://") + "serialws"
    logger.info("Collecting logs from %s for device %s", uri, chip_id)
    file_name = "log/" + chip_id + ".log"

    try:
        with connect(uri) as websocket:
            logger.info("Connected to %s, listening for logs...", uri)
            write_key(f"log_{chip_id}_start", int(time()))

            line = ""
            line_cnt = 0
            byte_cnt = 0

            while True:
                line += websocket.recv()
                if line.endswith("\n") or len(line) > 200:
                    with open(file_name, "a", encoding="utf-8") as f:
                        f.write(line)
                    line_cnt += 1
                    byte_cnt += len(line)
                    line = ""
                    write_key(f"log_{chip_id}_last", int(time()))
                    write_key(f"log_{chip_id}_count", line_cnt)
                    write_key(f"log_{chip_id}_size", byte_cnt)

                    if os.stat(file_name).st_size > max_file_size:
                        logger.info(
                            "Log file too large (>%d), rotating %s → %s.1",
                            max_file_size, file_name, file_name,
                        )
                        try:
                            os.remove(file_name + ".1")
                        except OSError:
                            pass
                        os.rename(file_name, file_name + ".1")

                # Graceful shutdown check
                tw = threads.get(chip_id)
                if tw is not None and tw.is_stopped():
                    break

    except WebSocketException as e:
        logger.error("WebSocket exception for %s: %s", chip_id, e)
    except OSError as e:
        logger.error("I/O error for %s: %s", chip_id, e)

    logger.info("Stopping log collection for %s", uri)


def _start_collector_thread(chip_id, url):
    """Start a log collector thread for one device."""
    logger.info("Starting log collection for %s @ %s", chip_id, url)
    tw = ThreadWrapper()
    tw.thread = threading.Thread(target=websocket_collector, args=[url, chip_id])
    tw.thread.daemon = True
    tw.thread.start()
    threads[chip_id] = tw


def _sync_device_collector(device):
    """Start/stop/cleanup per-device collector threads based on device state."""
    chip_id = device.get("chipId") or device.get("chip_id")
    collect_logs = device.get("collectLogs") or device.get("collect_logs", False)
    url = device.get("url", "")

    tw = threads.get(chip_id)
    if tw is None:
        if not collect_logs:
            return
        if not url:
            logger.warning("Device %s has logging enabled but no URL set.", chip_id)
            return
        _start_collector_thread(chip_id, url)
        return

    if not collect_logs:
        if not tw.is_stopped():
            logger.info("Stopping thread for %s", chip_id)
            tw.stop()
        elif not tw.is_alive():
            logger.info("Removing thread for %s", chip_id)
            threads.pop(chip_id)
        return

    logger.debug("Thread alive check for %s: %s", chip_id, tw.is_alive())
    if not tw.is_alive():
        logger.warning("Thread exited for device %s, removing.", chip_id)
        threads.pop(chip_id)


def _fetch_devices():
    """Fetch the current device list from BrewGraph API."""
    devices = []
    try:
        logger.info("Fetching device list from BrewGraph API: %s", endpoint)
        response = requests.get(endpoint, headers=headers, timeout=10)
        if response.ok:
            payload = response.json()
            if isinstance(payload, dict) and isinstance(payload.get("items"), list):
                devices = payload["items"]
            else:
                logger.warning("Unexpected device-list response from BrewGraph API")
    except requests.RequestException as err:
        logger.error("Failed to fetch device list: %s", err)
    return devices


def _configure_redis_pool(redis_host):
    """Initialize Redis connection pool when REDIS_HOST is configured."""
    global pool  # pylint: disable=global-statement
    if redis_host is None:
        logger.warning("No REDIS_HOST env variable — status sharing disabled.")
        return

    logger.info("Using Redis at %s", redis_host)
    pool = redis.ConnectionPool(host=redis_host, port=6379, db=0)


async def main():
    """Run the polling loop and reconcile collector threads for all devices."""

    redis_host = os.getenv("REDIS_HOST")
    _configure_redis_pool(redis_host)

    os.makedirs("log", exist_ok=True)

    while True:
        for device in _fetch_devices():
            _sync_device_collector(device)

        await asyncio.sleep(5)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)-15s %(name)-8s %(levelname)s: %(message)s",
    )

    api_host = os.getenv("API_HOST")
    api_key = os.getenv("API_KEY")
    max_file_size_env = os.getenv("MAX_FILE_SIZE")

    if max_file_size_env is not None:
        max_file_size = int(max_file_size_env)

    if api_host is None or api_key is None:
        logging.error("API_HOST and API_KEY environment variables must be set.")
        raise SystemExit(1)

    endpoint = f"http://{api_host}/api/devices?pageSize=200"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    logger.info(
        "Starting BrewGraph log collector — max file size %d KB",
        max_file_size // 1000,
    )
    asyncio.run(main())
    logger.info("Exiting...")
