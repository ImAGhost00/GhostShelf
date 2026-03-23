"""
Komga integration service.

Komga exposes a REST API at http://<host>/api/v1/

When deployed behind Wizarr, Komga users are Wizarr users and authentication
is handled centrally. GhostShelf connects to Komga's API endpoints without
separate credentials.

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
    username = (await get_setting(db, "komga_username", "")).strip()
    password = await get_setting(db, "komga_password", "")
    if username and password:
        return (username, password)
    return None


async def check_connection(db: AsyncSession) -> dict[str, Any]:
    """Check Komga connection - Komga authentication is via Wizarr."""
    komga_url = await get_setting(db, "komga_url", "")
    username = await get_setting(db, "komga_username", "")
    password = await get_setting(db, "komga_password", "")
    return await check_connection_inline(komga_url, username, password)


async def check_connection_inline(url: str, username: str = "", password: str = "") -> dict[str, Any]:
    """Check Komga connection - Komga authentication is via Wizarr, not separate credentials."""
    if not url:
        return {"connected": False, "error": "Komga URL not configured"}
    base_url = f"{url.rstrip('/')}/api/v1"
    auth = (username, password) if username and password else None
    
    try:
        async with httpx.AsyncClient(timeout=10, auth=auth) as client:
            # Try to reach a public endpoint that doesn't require auth
            resp = await client.get(f"{base_url}/libraries")
            if resp.status_code == 200:
                return {"connected": True}
            elif resp.status_code in (401, 403):
                # Auth required but reachable
                return {"connected": True, "note": "Auth required (check Wizarr setup)"}
            return {"connected": False, "error": f"HTTP {resp.status_code}"}
    except Exception as exc:
        return {"connected": False, "error": str(exc)}


async def get_libraries(db: AsyncSession) -> list[dict]:
    komga_url = await get_setting(db, "komga_url", "")
    if not komga_url:
        return []

    base_url = await _base_url(db)
    async with httpx.AsyncClient(timeout=10, auth=await _auth(db)) as client:
        resp = await client.get(f"{base_url}/libraries")
        resp.raise_for_status()
    return resp.json()


async def scan_library(db: AsyncSession, library_id: str) -> dict[str, Any]:
    komga_url = await get_setting(db, "komga_url", "")
    if not komga_url:
        return {"success": False, "error": "Komga URL not configured"}

    base_url = await _base_url(db)
    async with httpx.AsyncClient(timeout=10, auth=await _auth(db)) as client:
        resp = await client.post(f"{base_url}/libraries/{library_id}/scan")
        return {"success": resp.status_code in (200, 202, 204)}


def _series_list_body(library_id: str | None, full_text_search: str | None = None) -> dict[str, Any]:
    body: dict[str, Any] = {}
    if full_text_search:
        body["fullTextSearch"] = full_text_search
    if library_id:
        body["condition"] = {
            "libraryId": {
                "operator": "is",
                "value": library_id,
            }
        }
    return body


async def get_series(
    db: AsyncSession,
    library_id: str | None = None,
    page: int = 0,
    size: int = 20,
) -> dict[str, Any]:
    komga_url = await get_setting(db, "komga_url", "")
    if not komga_url:
        return {"content": [], "totalElements": 0}

    base_url = await _base_url(db)
    async with httpx.AsyncClient(timeout=15, auth=await _auth(db)) as client:
        # Preferred OpenAPI endpoint.
        resp = await client.post(
            f"{base_url}/series/list",
            params={"page": page, "size": size},
            json=_series_list_body(library_id=library_id),
        )
        if resp.status_code == 200:
            return resp.json()

        # Backward compatibility fallback for older server behavior.
        params: dict[str, Any] = {"page": page, "size": size}
        if library_id:
            params["library_id"] = library_id
        fallback = await client.get(f"{base_url}/series", params=params)
        fallback.raise_for_status()
        return fallback.json()


def _books_list_body(series_id: str | None = None, library_id: str | None = None) -> dict[str, Any]:
    filters: list[dict[str, Any]] = []
    if series_id:
        filters.append({"seriesId": {"operator": "is", "value": series_id}})
    if library_id:
        filters.append({"libraryId": {"operator": "is", "value": library_id}})
    if not filters:
        return {}
    if len(filters) == 1:
        return {"condition": filters[0]}
    return {"condition": {"allOf": filters}}


async def get_books(
    db: AsyncSession,
    series_id: str | None = None,
    library_id: str | None = None,
    page: int = 0,
    size: int = 50,
) -> dict[str, Any]:
    komga_url = await get_setting(db, "komga_url", "")
    if not komga_url:
        return {"content": [], "totalElements": 0}

    base_url = await _base_url(db)
    async with httpx.AsyncClient(timeout=15, auth=await _auth(db)) as client:
        resp = await client.post(
            f"{base_url}/books/list",
            params={"page": page, "size": size},
            json=_books_list_body(series_id=series_id, library_id=library_id),
        )
        if resp.status_code == 200:
            return resp.json()

        # Legacy fallback for old endpoint shape.
        if series_id:
            fallback = await client.get(f"{base_url}/series/{series_id}/books", params={"page": page, "size": size})
            fallback.raise_for_status()
            return fallback.json()
        fallback = await client.get(f"{base_url}/books", params={"page": page, "size": size})
        fallback.raise_for_status()
        return fallback.json()
