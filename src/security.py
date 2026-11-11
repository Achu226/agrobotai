"""
Network-facing protections for running the server on the LAN.

* LAN guard: the legacy web-UI endpoints (/api/... other than /api/v1), the React dashboard and
  /docs have no authentication, so they are only served to clients on this laptop (loopback).
  Phones on the Wi-Fi may only reach /health and the authenticated /api/v1 + /models routes.
* Request logging to logs/server.log (rotating) — method, path, status, duration, client IP.
* Upload reading with a hard size limit, so a huge body cannot exhaust memory.
"""
from __future__ import annotations

import ipaddress
import logging
import time
from logging.handlers import RotatingFileHandler

from fastapi import HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

from src import config

LAN_ALLOWED_PREFIXES = ("/health", "/api/v1/", "/models/")

_logger: logging.Logger | None = None


def request_logger() -> logging.Logger:
    global _logger
    if _logger is None:
        config.LOG_DIR.mkdir(parents=True, exist_ok=True)
        _logger = logging.getLogger("agrobotai.requests")
        _logger.setLevel(logging.INFO)
        if not _logger.handlers:
            handler = RotatingFileHandler(config.LOG_DIR / "server.log", maxBytes=2_000_000, backupCount=3, encoding="utf-8")
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            _logger.addHandler(handler)
    return _logger


def is_loopback(host: str | None) -> bool:
    if not host:
        return False
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def lan_allowed(path: str) -> bool:
    return path == "/health" or path.startswith(LAN_ALLOWED_PREFIXES)


async def lan_guard_and_log(request: Request, call_next):
    client = request.client.host if request.client else None
    path = request.url.path
    started = time.perf_counter()
    if not is_loopback(client):
        from src import device_status

        device_status.mark_activity()  # a phone or the laptop is using the server: no idle auto-off
    if not is_loopback(client) and not lan_allowed(path):
        response = JSONResponse(
            status_code=403,
            content={"detail": "This endpoint is only available on the server laptop. Mobile clients use /api/v1."},
        )
    else:
        response = await call_next(request)
    request_logger().info("%s %s %s %.0fms client=%s", request.method, path, response.status_code,
                          (time.perf_counter() - started) * 1000, client)
    return response


async def read_upload(file: UploadFile) -> bytes:
    """Reads an uploaded file, enforcing MAX_UPLOAD_MB. Raises 400/413 with a clear message."""
    limit = int(config.MAX_UPLOAD_MB * 1024 * 1024)
    data = await file.read(limit + 1)
    if not data:
        raise HTTPException(status_code=400, detail="The uploaded file is empty.")
    if len(data) > limit:
        raise HTTPException(status_code=413, detail=f"Image is larger than the {config.MAX_UPLOAD_MB:g} MB limit.")
    return data
