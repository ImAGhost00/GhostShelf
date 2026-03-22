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
    cwa_url = (await get_setting(db, "cwa_url", "")).rstrip("/")
    cwa_ingest_folder = await get_setting(db, "cwa_ingest_folder", "")

    if not cwa_url:
        return {"connected": False, "error": "CWA URL not configured"}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(cwa_url, follow_redirects=True)
            return {
                "connected": resp.status_code < 500,
                "status_code": resp.status_code,
                "ingest_folder": cwa_ingest_folder or "(not set)",
            }
    except Exception as exc:
        return {"connected": False, "error": str(exc)}


async def get_ingest_info(db: AsyncSession) -> dict[str, Any]:
    cwa_url = await get_setting(db, "cwa_url", "")
    ingest_folder = await get_setting(db, "cwa_ingest_folder", "")
    return {
        "cwa_url": cwa_url,
        "ingest_folder": ingest_folder,
        "configured": bool(ingest_folder),
    }
