# Copyright (c) 2024-2026 Magnus Persson
# SPDX-License-Identifier: GPL-3.0-only
# BrewGraph — https://github.com/mp-se/brewgraph
#
# This file is part of BrewGraph. For open source use it is licensed under
# the GNU General Public License v3.0. For commercial use without source
# disclosure, a separate Commercial License is required.
# See LICENSE for details.

"""Device management API endpoints."""
import json
import logging
import math
import os
import re
import uuid
from dataclasses import dataclass
from json import JSONDecodeError
from pathlib import Path
from typing import Any, List, Literal, Optional
from urllib.parse import urlparse

import httpx
from fastapi import BackgroundTasks, Depends, Query, Response
from fastapi.routing import APIRouter
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException

import oss.schemas.device  # noqa: F401,W0611 — side-effect: triggers self-registration  # pylint: disable=unused-import
from core.cache import find_key, read_key, write_key
from core.events import notify_clients
from core.log import LogLevel, system_log
from core.middleware.auth import AuthContext, check_quota
from core.openapi_tags import DEVICES, DEVICES_LOCAL
from core.schemas.errors import NOT_FOUND_RESPONSES, ErrorResponse
from core.utils import resolve_and_pin_private_url
from oss.extensions.auth import oss_auth_provider as api_key_auth
from oss.extensions.tenant import DEFAULT_TENANT_ID
from oss.schemas._page import CursorPage, Page, encode_cursor, parse_cursor
from oss.schemas.platform import MdnsDevice
from oss.schemas.prediction import PredictionResponse
from oss.schemas.registry import get as _s
from oss.services import (DeviceService, get_device_service,
                          get_prediction_service)
from oss.services.prediction import PredictionService

DeviceCreate   = _s("DeviceCreate")
DeviceUpdate   = _s("DeviceUpdate")
DeviceResponse = _s("DeviceResponse")


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/devices", dependencies=[Depends(api_key_auth)])

LOG_DIR = Path(__file__).parent.parent.parent / "log"
# A serial device can emit arbitrary output. Keep the newest diagnostics useful
# without letting one log force the API to read and return an unbounded response.
_MAX_DEVICE_LOG_BYTES = 512 * 1024
_MAX_PROXY_BYTES = 512 * 1024


@dataclass(frozen=True)
class _ProxyTarget:
    """A private device URL pinned to an IP while retaining TLS identity."""

    url: str
    host_header: str
    sni_hostname: str


class ProxyRequest(BaseModel):
    """Payload schema used by the device proxy endpoint."""

    url: str = Field(max_length=2048)
    method: Literal["GET", "POST", "PUT", "DELETE"]
    body: Optional[str] = Field(default=None, max_length=_MAX_PROXY_BYTES)
    header: Optional[str] = Field(default="", max_length=4096)


@router.get("",
    tags=[DEVICES], response_model=Page[DeviceResponse], dependencies=[Depends(api_key_auth)])
async def list_devices(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200, alias="pageSize"),
    device_service: DeviceService = Depends(get_device_service),
) -> Any:
    """List all non-deleted devices (paginated)."""
    logger.info("Endpoint GET /devices/?page=%d&pageSize=%d", page, page_size)
    items, total = device_service.list_page(page=page, page_size=page_size)
    return Page(items=items, total=total, page=page, page_size=page_size,
                pages=max(1, math.ceil(total / page_size)))



@router.post("/proxy-fetch",
    tags=[DEVICES_LOCAL], status_code=200, dependencies=[Depends(api_key_auth)])
async def fetch_data_from_device(proxy_req: ProxyRequest) -> Any:
    """Fetch data from a device via proxy request."""
    logger.info("Endpoint POST /devices/proxy_fetch")

    try:
        target = _validate_proxy_target(proxy_req.url)
        headers = _parse_proxy_header(proxy_req.header)
        # The configured hostname is authoritative; a caller cannot redirect a
        # pinned connection to a different virtual host through a Host header.
        headers["Host"] = target.host_header
        timeout = httpx.Timeout(10.0, connect=10.0, read=10.0)

        async with httpx.AsyncClient(timeout=timeout) as client:
            status_code, content = await _send_proxy_request(
                client, proxy_req.method, target, headers, proxy_req.body
            )

            if status_code != 200:
                raise HTTPException(status_code=status_code, detail="Response from endpoint.")

            try:
                return json.loads(content)
            except (JSONDecodeError, UnicodeDecodeError):
                return content.decode("utf-8", errors="replace")

    except JSONDecodeError as exc:
        raise HTTPException(
            status_code=400,
            detail="Unable to parse JSON from remote endpoint.",
        ) from exc
    except httpx.ReadTimeout as exc:
        logger.warning("Proxy fetch to remote endpoint timed out reading response: %s", exc)
        raise HTTPException(
            status_code=400,
            detail="Unable to connect to remote endpoint.",
        ) from exc
    except httpx.ConnectError as exc:
        logger.warning("Proxy fetch to remote endpoint failed to connect: %s", exc)
        raise HTTPException(
            status_code=400,
            detail="Unable to connect to remote endpoint.",
        ) from exc
    except httpx.ConnectTimeout as exc:
        logger.warning("Proxy fetch to remote endpoint timed out connecting: %s", exc)
        raise HTTPException(
            status_code=400,
            detail="Unable to connect to remote endpoint.",
        ) from exc


@router.get("/logs",
    response_model=List[str],
    tags=[DEVICES_LOCAL], dependencies=[Depends(api_key_auth)])
async def get_device_logs() -> List[str]:
    """Retrieve list of device log files."""
    logger.info("Endpoint GET /devices/logs/")
    try:
        files = [
            f for f in os.listdir(LOG_DIR)
            if (LOG_DIR / f).is_file() and re.fullmatch(r"[0-9a-fA-F]{6}\.log(\.1)?", f)
        ]
    except FileNotFoundError:
        files = []
    return files


@router.get("/logs/{chip_id}",
    responses=NOT_FOUND_RESPONSES,
    tags=[DEVICES_LOCAL], dependencies=[Depends(api_key_auth)])
async def get_device_log(chip_id: str, rotated: bool = Query(default=False)) -> Response:
    """Retrieve the current or previous serial log for one device.

    Logs are deliberately returned through the authenticated API rather than a
    public nginx alias: serial logs can include local hostnames and credentials.
    """
    logger.info("Endpoint GET /devices/logs/%s rotated=%s", chip_id, rotated)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", chip_id):
        raise HTTPException(status_code=400, detail="Invalid chip_id")
    path = LOG_DIR / f"{chip_id}.log{'.1' if rotated else ''}"
    try:
        size = path.stat().st_size
        with path.open("rb") as stream:
            truncated = size > _MAX_DEVICE_LOG_BYTES
            if truncated:
                stream.seek(-_MAX_DEVICE_LOG_BYTES, os.SEEK_END)
            content = stream.read().decode("utf-8", errors="replace")
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Log file not found") from exc
    headers = {"Cache-Control": "no-store"}
    if truncated:
        content = "[... older log content omitted ...]\n" + content
        headers["X-Log-Truncated"] = "true"
    return Response(content=content, media_type="text/plain", headers=headers)


@router.delete("/logs/{chip_id}",
    responses=NOT_FOUND_RESPONSES,
    tags=[DEVICES_LOCAL], status_code=204, dependencies=[Depends(api_key_auth)])
async def delete_device_log(chip_id: str) -> None:
    """Delete device log files for a specific chip ID."""
    logger.info("Endpoint DELETE /devices/logs/%s", chip_id)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", chip_id):
        raise HTTPException(status_code=400, detail="Invalid chip_id")
    for suffix in ["", ".1"]:
        try:
            (LOG_DIR / f"{chip_id}.log{suffix}").unlink()
        except FileNotFoundError:
            pass



@router.get("/mdns",
    response_model=List[MdnsDevice],
    tags=[DEVICES_LOCAL], dependencies=[Depends(api_key_auth)])
async def scan_for_mdns_devices() -> list:
    """Return mDNS-discovered devices cached by the mdns service."""
    logger.info("Endpoint GET /devices/mdns/")
    mdns = []
    for key in find_key("*.local."):
        value = read_key(key)
        if value:
            mdns.append(json.loads(value.decode()))
    return mdns


# The sidecar rescans back-to-back (a 20 s listen window plus up to 3 s of
# service resolution per device) and re-reports every device it finds on each
# round, which refreshes the record. A record not refreshed for five rounds
# (~2 minutes, tolerant of a few lost multicast replies) is a device that left.
_MDNS_TTL_SECONDS = 120


def _mdns_cache_key(device: MdnsDevice) -> str:
    """Return the cache key for one discovered service.

    Keyed by host name and service type so a host advertising several services
    keeps one record each, and a re-report replaces rather than duplicates. The
    trailing ``.local.`` is what the GET's ``*.local.`` scan matches.
    """
    host = (device.name or "").strip().rstrip(".")
    service = str((device.model_extra or {}).get("type") or "").strip()
    if not host or any(c in host + service for c in "*?[]\\ \r\n"):
        raise HTTPException(status_code=422, detail="name must be a host name")
    if not host.endswith(".local"):
        host += ".local"
    return f"mdns:{host}.{service}" if service.endswith(".local.") else f"mdns:{host}."


@router.post("/mdns",
    status_code=204,
    responses={503: {"model": ErrorResponse, "description": "Cache unavailable"}},
    tags=[DEVICES_LOCAL], dependencies=[Depends(api_key_auth)])
async def report_mdns_device(device: MdnsDevice) -> None:
    """Record a device discovered by the mdns service, replacing any earlier record."""
    logger.info("Endpoint POST /devices/mdns/")
    key = _mdns_cache_key(device)
    if not write_key(key, device.model_dump_json(exclude_none=True), _MDNS_TTL_SECONDS):
        raise HTTPException(status_code=503, detail="Cache unavailable")


@router.get(
    "/{device_id}",
    tags=[DEVICES],
    response_model=DeviceResponse,
    responses={404: {"model": ErrorResponse, "description": "Device not found"}},
    dependencies=[Depends(api_key_auth)],
)
async def get_device_by_id(
    device_id: uuid.UUID,
    device_service: DeviceService = Depends(get_device_service),
) -> Any:
    """Retrieve a specific device by ID."""
    logger.info("Endpoint GET /devices/%s", device_id)
    device = device_service.get(device_id)
    if device is None or device.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Device not found")
    return device


@router.post(
    "",
    tags=[DEVICES],
    response_model=DeviceResponse,
    status_code=201,
    responses={409: {"model": ErrorResponse, "description": "Conflict Error"}},
)
async def create_device(
    device: DeviceCreate,
    background_tasks: BackgroundTasks,
    device_service: DeviceService = Depends(get_device_service),
    auth: AuthContext = Depends(api_key_auth),
) -> Any:
    """Create a new device. Returns the device with its initial token."""
    logger.info("Endpoint POST /devices/")
    check_quota(device_service.count(), auth, "devices")
    created = device_service.create(device)
    token = device_service.generate_token(created.id)
    system_log("device_created", f"Device created: {created.chip_id}", level=LogLevel.INFO)
    background_tasks.add_task(notify_clients, "device", "create", created.id,
                                   DEFAULT_TENANT_ID, source="device")
    response = DeviceResponse.model_validate(created)
    return response.model_copy(update={"token": token})


@router.patch(
    "/{device_id}",
    responses=NOT_FOUND_RESPONSES,
    tags=[DEVICES],
    response_model=DeviceResponse,
    dependencies=[Depends(api_key_auth)],
)
async def update_device_by_id(
    device_id: uuid.UUID,
    device: DeviceUpdate,
    background_tasks: BackgroundTasks,
    device_service: DeviceService = Depends(get_device_service),
) -> Any:
    """Update a specific device by ID."""
    logger.info("Endpoint PATCH /devices/%s", device_id)
    updated = device_service.update(device_id, device)
    if updated is None:
        raise HTTPException(status_code=404, detail="Device not found")
    system_log("device_updated", f"Device {device_id} updated", level=LogLevel.INFO)
    background_tasks.add_task(notify_clients, "device", "update", device_id,
                                   DEFAULT_TENANT_ID, source="device")
    return updated


@router.delete("/{device_id}",
    responses=NOT_FOUND_RESPONSES,
    tags=[DEVICES], status_code=204, dependencies=[Depends(api_key_auth)])
async def delete_device_by_id(
    device_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    device_service: DeviceService = Depends(get_device_service),
):
    """Soft-delete a specific device by ID."""
    logger.info("Endpoint DELETE /devices/%s", device_id)
    device = device_service.get(device_id)
    if not device or device.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Device not found")
    system_log(
        "device_deleted",
        f"Device {device_id} ({device.chip_id}) deleted",
        level=LogLevel.INFO,
    )
    device_service.soft_delete(device_id)
    background_tasks.add_task(notify_clients, "device", "delete", device_id,
                                   DEFAULT_TENANT_ID, source="device")


@router.get(
    "/{device_id}/token",
    tags=[DEVICES],
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
def get_token(
    device_id: uuid.UUID,
    device_service: DeviceService = Depends(get_device_service),
) -> dict:
    """Return the device's current ingest token.

    Ingest tokens are not secret in this project's model — holding one only
    lets a caller add readings for this device, never modify or delete
    anything. The same value is already returned in plaintext by
    GET /devices and GET /devices/{device_id}; this endpoint exists so a
    caller that only knows the device_id can fetch just the token without
    the rest of the device payload. Use POST /{device_id}/token to rotate it.
    """
    logger.info("Endpoint GET /devices/%s/token", device_id)
    device = device_service.get(device_id)
    if not device or device.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Device not found")
    return {"token": device.token}


@router.post(
    "/{device_id}/token",
    tags=[DEVICES],
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def regenerate_token(
    device_id: uuid.UUID,
    device_service: DeviceService = Depends(get_device_service),
) -> dict:
    """Regenerate the API token for a device. Returns the new token."""
    logger.info("Endpoint POST /devices/%s/token", device_id)
    device = device_service.get(device_id)
    if not device or device.deleted_at is not None:
        raise HTTPException(status_code=404, detail="Device not found")
    token = device_service.generate_token(device_id)
    system_log(
        "device_token_regenerated",
        f"Token regenerated for device {device_id}",
        level=LogLevel.INFO,
    )
    return {"token": token}


def _validate_proxy_target(url: str) -> _ProxyTarget:
    """Validate and DNS-pin a private target while preserving HTTPS identity."""
    try:
        pinned_url = resolve_and_pin_private_url(url)
        parsed = urlparse(url)
        host = parsed.hostname or ""
        host_header = host if ":" not in host else f"[{host}]"
        if parsed.port is not None:
            host_header = f"{host_header}:{parsed.port}"
        return _ProxyTarget(
            url=pinned_url,
            host_header=host_header,
            sni_hostname=host,
        )
    except ValueError as exc:
        logger.warning("Rejected proxy target %s: %s", url, exc)
        raise HTTPException(status_code=400, detail="Target is not reachable") from exc


def _parse_proxy_header(header: Optional[str]) -> dict:
    if not header:
        return {}
    parts = header.split(":", 1)
    if len(parts) != 2:
        return {}
    return {parts[0]: parts[1].strip()}


async def _send_proxy_request(
    client: httpx.AsyncClient, method: str, target: _ProxyTarget, headers: dict, body: Any
) -> tuple[int, bytes]:
    """Send a bounded private-device request without buffering its whole response."""
    request = client.build_request(
        method,
        target.url,
        content=body,
        headers=headers,
        extensions={"sni_hostname": target.sni_hostname},
    )
    response = await client.send(request, stream=True)
    try:
        if response.status_code != 200:
            return response.status_code, b""
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > _MAX_PROXY_BYTES:
                raise HTTPException(status_code=502, detail="Remote response too large")
            chunks.append(chunk)
        return response.status_code, b"".join(chunks)
    finally:
        await response.aclose()


@router.get(
    "/{device_id}/predictions",
    response_model=CursorPage[PredictionResponse],
    tags=["predictions"],
    dependencies=[Depends(api_key_auth)],
    responses=NOT_FOUND_RESPONSES,
)
async def get_device_predictions(
    device_id: uuid.UUID,
    limit: int = Query(200, ge=1, le=1000),
    cursor: Optional[str] = Query(None),
    prediction_service: PredictionService = Depends(get_prediction_service),
) -> Any:
    """Return prediction history for a device, newest first (cursor-paginated)."""
    logger.info("Endpoint GET /devices/%s/predictions", device_id)
    try:
        cursor_dt = parse_cursor(cursor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid cursor format") from exc
    items, has_more = prediction_service.history_cursor(
        "device_id", device_id, limit=limit, cursor=cursor_dt
    )
    next_cursor = encode_cursor(items[-1].created_at, items[-1].id) if has_more and items else None
    return CursorPage(items=items, next_cursor=next_cursor, has_more=has_more)

@router.post(
    "/{device_id}/restore",
    tags=[DEVICES],
    response_model=DeviceResponse,
    responses={404: {"model": ErrorResponse, "description": "Not found or not deleted"}},
    dependencies=[Depends(api_key_auth)],
)
async def restore_device(
    device_id: uuid.UUID,
    device_service: DeviceService = Depends(get_device_service),
) -> Any:
    """Undo a soft delete, until the grace-window purge removes the row.

    Only what was deleted here comes back — a child soft-deleted in its own right
    stays deleted, so restoring is not a way to undo every deletion that ever
    touched this device.
    """
    logger.info("Endpoint POST /devices/%s/restore", device_id)
    if not device_service.restore(device_id):
        raise HTTPException(status_code=404, detail="Device not found or not deleted")
    return device_service.get(device_id)
