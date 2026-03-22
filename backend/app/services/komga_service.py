"""
Komga integration service.

Komga exposes a REST API at http://<host>/api/v1/
Docs: https://komga.org/docs/api
"""
from __future__ import annotations

import httpx
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.settings_store import get_setting


async def _base_url(db: AsyncSession) -> str:
    url = (await get_setting(db, "komga_url", "")).rstrip("/")
    return f"{url}/api/v1"


async def _auth(db: AsyncSession) -> tuple[str, str] | None:
    username = await get_setting(db, "komga_username", "")
    password = await get_setting(db, "komga_password", "")
    if username and password:
        return (username, password)
    return None


async def check_connection(db: AsyncSession) -> dict[str, Any]:
    komga_url = await get_setting(db, "komga_url", "")
    if not komga_url:
        return {"connected": False, "error": "Komga URL not configured"}

    base_url = await _base_url(db)
    auth = await _auth(db)
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{base_url}/users/me", auth=auth)
            if resp.status_code == 200:
                data = resp.json()
                return {"connected": True, "user": data.get("email", ""), "roles": data.get("roles", [])}
            return {"connected": False, "error": f"HTTP {resp.status_code}"}
    except Exception as exc:
        return {"connected": False, "error": str(exc)}


async def get_libraries(db: AsyncSession) -> list[dict]:
    komga_url = await get_setting(db, "komga_url", "")
    if not komga_url:
        return []

    base_url = await _base_url(db)
    auth = await _auth(db)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{base_url}/libraries", auth=auth)
        resp.raise_for_status()
    return resp.json()


async def scan_library(db: AsyncSession, library_id: str) -> dict[str, Any]:
    komga_url = await get_setting(db, "komga_url", "")
    if not komga_url:
        return {"success": False, "error": "Komga URL not configured"}

    base_url = await _base_url(db)
    auth = await _auth(db)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.post(f"{base_url}/libraries/{library_id}/scan", auth=auth)
        return {"success": resp.status_code in (200, 202, 204)}


async def get_series(
    db: AsyncSession,
    library_id: str | None = None,
    page: int = 0,
    size: int = 20,
) -> dict[str, Any]:
    komga_url = await get_setting(db, "komga_url", "")
    if not komga_url:
        return {"content": [], "totalElements": 0}

    params: dict[str, Any] = {"page": page, "size": size}
    if library_id:
        params["library_id"] = library_id

    base_url = await _base_url(db)
    auth = await _auth(db)
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{base_url}/series", params=params, auth=auth)
        resp.raise_for_status()
    return resp.json()
