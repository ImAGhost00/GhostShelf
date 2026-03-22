"""
Komga integration service.

Komga exposes a REST API at http://<host>/api/v1/
Docs: https://komga.org/docs/api
"""
from __future__ import annotations

import httpx
from typing import Any

from app.config import get_settings

settings = get_settings()


def _base_url() -> str:
    url = settings.komga_url.rstrip("/")
    return f"{url}/api/v1"


def _auth() -> tuple[str, str] | None:
    if settings.komga_username and settings.komga_password:
        return (settings.komga_username, settings.komga_password)
    return None


async def check_connection() -> dict[str, Any]:
    if not settings.komga_url:
        return {"connected": False, "error": "Komga URL not configured"}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{_base_url()}/users/me", auth=_auth())
            if resp.status_code == 200:
                data = resp.json()
                return {"connected": True, "user": data.get("email", ""), "roles": data.get("roles", [])}
            return {"connected": False, "error": f"HTTP {resp.status_code}"}
    except Exception as exc:
        return {"connected": False, "error": str(exc)}


async def get_libraries() -> list[dict]:
    if not settings.komga_url:
        return []
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{_base_url()}/libraries", auth=_auth())
        resp.raise_for_status()
    return resp.json()


async def scan_library(library_id: str) -> dict[str, Any]:
    if not settings.komga_url:
        return {"success": False, "error": "Komga URL not configured"}
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(f"{_base_url()}/libraries/{library_id}/scan", auth=_auth())
        return {"success": resp.status_code in (200, 202, 204)}


async def get_series(library_id: str | None = None, page: int = 0, size: int = 20) -> dict[str, Any]:
    if not settings.komga_url:
        return {"content": [], "totalElements": 0}
    params: dict[str, Any] = {"page": page, "size": size}
    if library_id:
        params["library_id"] = library_id
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{_base_url()}/series", params=params, auth=_auth())
        resp.raise_for_status()
    return resp.json()
