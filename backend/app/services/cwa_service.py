"""
Calibre-Web Automated (CWA) integration service.

CWA works by monitoring an "ingest" folder — books dropped there are
automatically imported into Calibre.  We also try to reach the CWA
web UI to verify the connection.
"""
from __future__ import annotations

import httpx
from typing import Any

from app.config import get_settings

settings = get_settings()


async def check_connection() -> dict[str, Any]:
    if not settings.cwa_url:
        return {"connected": False, "error": "CWA URL not configured"}
    url = settings.cwa_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, follow_redirects=True)
            return {
                "connected": resp.status_code < 500,
                "status_code": resp.status_code,
                "ingest_folder": settings.cwa_ingest_folder or "(not set)",
            }
    except Exception as exc:
        return {"connected": False, "error": str(exc)}


def get_ingest_info() -> dict[str, Any]:
    return {
        "cwa_url": settings.cwa_url or "",
        "ingest_folder": settings.cwa_ingest_folder or "",
        "configured": bool(settings.cwa_ingest_folder),
    }
