"""
Calibre-Web Automated (CWA) integration service.

CWA works by monitoring an "ingest" folder — books dropped there are
automatically imported into Calibre.  We also try to reach the CWA
web UI to verify the connection.
"""
from __future__ import annotations

import httpx
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.settings_store import get_setting

async def check_connection(db: AsyncSession) -> dict[str, Any]:
    cwa_url = await get_setting(db, "cwa_url", "")
    username = await get_setting(db, "cwa_username", "")
    password = await get_setting(db, "cwa_password", "")
    return await check_connection_inline(cwa_url, username, password)


async def check_connection_inline(url: str, username: str = "", password: str = "") -> dict[str, Any]:
    """Test CWA reachability using the provided URL directly."""
    url = url.rstrip("/")
    if not url:
        return {"connected": False, "error": "CWA URL not configured"}
    auth = (username, password) if username and password else None
    try:
        async with httpx.AsyncClient(timeout=10, follow_redirects=True, auth=auth) as client:
            resp = await client.get(url)
            connected = resp.status_code < 500
            return {"connected": connected, "status_code": resp.status_code}
    except Exception as exc:
        return {"connected": False, "error": str(exc)}


async def get_ingest_info(db: AsyncSession) -> dict[str, Any]:
    cwa_url = await get_setting(db, "cwa_url", "")
    cwa_opds_url = await get_setting(db, "cwa_opds_url", "")
    ingest_folder = await get_setting(db, "cwa_ingest_folder", "")
    return {
        "cwa_url": cwa_url,
        "cwa_opds_url": cwa_opds_url,
        "ingest_folder": ingest_folder,
        "configured": bool(ingest_folder),
    }
