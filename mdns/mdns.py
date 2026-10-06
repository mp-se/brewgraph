# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Continuously scan for mDNS-advertised brewing devices and report them to the API.

Reports discovered devices to the BrewGraph API (POST /api/devices/mdns).

Requires the following environment variables:

  API_HOST: Hostname/IP of the API (e.g. brewgraph-api)
  API_KEY:  API Key for authentication
"""

import asyncio
import logging
import os
import time
from typing import Optional, cast

import requests
from zeroconf import DNSQuestionType, IPVersion, ServiceStateChange, Zeroconf
from zeroconf.asyncio import (AsyncServiceBrowser, AsyncServiceInfo,
                              AsyncZeroconf)

ALL_SERVICES = [
    "_pressuremon._tcp.local.",
    "_gravitymon._tcp.local.",
    "_gravitymon-gateway._tcp.local.",
    "_kegmon._tcp.local.",
    "_chamberctl._tcp.local.",
]

logger = logging.getLogger(__name__)
scan_result = []

# Filled in __main__
api_host = ""
api_key = ""


async def scan_for_mdns(timeout: int):
    """Run a single mDNS scan for all known service types and return discovered devices."""
    logger.info("Scanning for mDNS devices, timeout=%ds", timeout)
    scan_result.clear()
    runner = AsyncDeviceScanner(timeout)
    await runner.async_run()
    logger.info("Scan completed: %s", scan_result)
    return scan_result


def async_on_service_state_change(
    zeroconf: Zeroconf, service_type: str, name: str, state_change: ServiceStateChange
) -> None:
    """Handle a zeroconf service state-change event by scheduling an info lookup."""
    logger.debug("Service %s of type %s state changed: %s", name, service_type, state_change)
    asyncio.ensure_future(_async_show_service_info(zeroconf, service_type, name))


async def _async_show_service_info(
    zeroconf: Zeroconf, service_type: str, name: str
) -> None:
    """Resolve service details and append a discovery record to scan_result."""
    info = AsyncServiceInfo(service_type, name)
    await info.async_request(zeroconf, 3000, question_type=DNSQuestionType.QU)
    logger.debug("Info from zeroconf: %r", info)
    if info:
        addresses = [
            f"{addr}:{cast(int, info.port)}" for addr in info.parsed_addresses()
        ]
        mdns_type = info.type
        host_str = ", ".join(addresses)
        host = info.server
        logger.info("Found: %s %s %s", mdns_type, host_str, host)
        mdns = {"type": mdns_type, "host": host_str, "name": host.strip(".")}
        scan_result.append(mdns)


class AsyncDeviceScanner:
    """Runs an async zeroconf browser for all known brewing service types."""

    def __init__(self, timeout: int) -> None:
        """Initialise with the scan window duration in seconds."""
        self.start = time.time()
        self.timeout = timeout
        self.aiobrowser: Optional[AsyncServiceBrowser] = None
        self.aiozc: Optional[AsyncZeroconf] = None

    async def async_run(self) -> None:
        """Start the zeroconf browser and wait for the scan window to elapse."""
        self.aiozc = AsyncZeroconf(ip_version=IPVersion.V4Only)
        await self.aiozc.zeroconf.async_wait_for_start()
        logger.info("Browsing services: %s", ALL_SERVICES)
        kwargs = {
            "handlers": [async_on_service_state_change],
            "question_type": DNSQuestionType.QU,
        }
        self.aiobrowser = AsyncServiceBrowser(
            self.aiozc.zeroconf, ALL_SERVICES, **kwargs
        )
        while (time.time() - self.start) < self.timeout:
            await asyncio.sleep(1)
        logger.info("Scan window elapsed, closing browser.")
        await self.async_close()

    async def async_close(self) -> None:
        """Cancel the browser and close the zeroconf instance."""
        assert self.aiozc is not None
        assert self.aiobrowser is not None
        await self.aiobrowser.async_cancel()
        await self.aiozc.async_close()


async def task_scan_mdns():
    """Execute one mDNS scan round and POST each discovered device to the API."""
    logger.info("Starting mDNS scan round")

    mdns_list = await scan_for_mdns(20)

    # The API keeps each record for a limited time, so every round re-reports.
    endpoint = "http://" + api_host + "/api/devices/mdns"
    req_headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer " + api_key,
    }

    for mdns in mdns_list:
        try:
            logger.info("Posting to %s: %s", endpoint, mdns)
            r = requests.post(endpoint, json=mdns, headers=req_headers, timeout=10)
            logger.info("Response: %d", r.status_code)
        except requests.RequestException as e:
            logger.error("Failed to post mDNS record: %s", e)


async def main():
    """Run the mDNS scan loop indefinitely."""
    while True:
        await task_scan_mdns()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)-15s %(name)-8s %(levelname)s: %(message)s",
    )

    api_host = os.getenv("API_HOST")
    if not api_host:
        logger.error("API_HOST environment variable must be set.")
        raise SystemExit(1)

    api_key = os.getenv("API_KEY")
    if not api_key:
        logger.error("API_KEY environment variable must be set.")
        raise SystemExit(1)

    logger.info("Starting BrewGraph mDNS scanner → API at %s", api_host)
    asyncio.run(main())
