from __future__ import annotations

from fastapi import APIRouter, HTTPException
import logging
from typing import Optional

from app.services import komga_service, cwa_service, prowlarr_service, qbittorrent_service
from app.services.settings_store import get_setting
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/integrations", tags=["integrations"])


# ─── Komga ────────────────────────────────────────────────────────────────────

@router.get("/komga/status")
async def komga_status(db: AsyncSession = Depends(get_db)):
    """Check Komga connection."""
    return await komga_service.check_connection(db)


class KomgaTestRequest(BaseModel):
    url: str = ""
    username: str = ""
    password: str = ""


@router.post("/komga/test")
async def komga_test(body: KomgaTestRequest, db: AsyncSession = Depends(get_db)):
    """Test Komga connection using just URL (Komga auth is via Wizarr)."""
    url = body.url or await get_setting(db, "komga_url", "")
    username = body.username or await get_setting(db, "komga_username", "")
    password = (
        body.password
        if body.password and body.password != "***"
        else await get_setting(db, "komga_password", "")
    )
    return await komga_service.check_connection_inline(url, username, password)


@router.get("/komga/libraries")
async def komga_libraries(db: AsyncSession = Depends(get_db)):
    """List Komga libraries."""
    try:
        return await komga_service.get_libraries(db)
    except Exception as exc:
        logger.error(f"Failed to get Komga libraries: {type(exc).__name__}", exc_info=False)
        raise HTTPException(status_code=502, detail="Unable to fetch Komga libraries") from exc


@router.post("/komga/libraries/{library_id}/scan")
async def komga_scan(library_id: str, db: AsyncSession = Depends(get_db)):
    """Trigger a Komga library scan."""
    try:
        return await komga_service.scan_library(db, library_id)
    except Exception as exc:
        logger.error(f"Failed to scan Komga library: {type(exc).__name__}", exc_info=False)
        raise HTTPException(status_code=502, detail="Unable to scan library") from exc


@router.get("/komga/series")
async def komga_series(
    library_id: Optional[str] = None,
    page: int = 0,
    size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """List series in Komga."""
    try:
        return await komga_service.get_series(db, library_id, page, size)
    except Exception as exc:
        logger.error(f"Failed to get Komga series: {type(exc).__name__}", exc_info=False)
        raise HTTPException(status_code=502, detail="Unable to fetch series") from exc


# ─── CWA ──────────────────────────────────────────────────────────────────────

@router.get("/cwa/status")
async def cwa_status(db: AsyncSession = Depends(get_db)):
    """Check CWA connection."""
    return await cwa_service.check_connection(db)


class CwaTestRequest(BaseModel):
    url: str = ""
    username: str = ""
    password: str = ""


@router.post("/cwa/test")
async def cwa_test(body: CwaTestRequest, db: AsyncSession = Depends(get_db)):
    """Test CWA reachability using inline URL (falls back to DB if empty)."""
    from app.services.settings_store import get_setting
    url = body.url or await get_setting(db, "cwa_url", "")
    username = body.username or await get_setting(db, "cwa_username", "")
    password = (
        body.password
        if body.password and body.password != "***"
        else await get_setting(db, "cwa_password", "")
    )
    return await cwa_service.check_connection_inline(url, username, password)


@router.get("/cwa/info")
async def cwa_info(db: AsyncSession = Depends(get_db)):
    """Return CWA ingest folder info."""
    return await cwa_service.get_ingest_info(db)


# ─── Prowlarr ─────────────────────────────────────────────────────────────────

@router.get("/prowlarr/status")
async def prowlarr_status(db: AsyncSession = Depends(get_db)):
    """Check Prowlarr connection."""
    try:
        return await prowlarr_service.check_connection(db)
    except Exception as exc:
        logger.error(f"Prowlarr status check failed: {type(exc).__name__}", exc_info=False)
        raise HTTPException(status_code=502, detail="Unable to check Prowlarr status") from exc


class ProwlarrTestRequest(BaseModel):
    url: str = ""
    api_key: str = ""


@router.post("/prowlarr/test")
async def prowlarr_test(body: ProwlarrTestRequest, db: AsyncSession = Depends(get_db)):
    """Test Prowlarr connection using inline credentials (falls back to DB for masked values)."""
    from app.services.settings_store import get_setting
    url = body.url or await get_setting(db, "prowlarr_url", "")
    api_key = (
        body.api_key
        if body.api_key and body.api_key != "***"
        else await get_setting(db, "prowlarr_api_key", "")
    )
    try:
        return await prowlarr_service.check_connection_inline(url, api_key)
    except Exception as exc:
        logger.error(f"Prowlarr connection test failed: {type(exc).__name__}", exc_info=False)
        raise HTTPException(status_code=502, detail="Unable to connect to Prowlarr") from exc


# ─── qBittorrent ──────────────────────────────────────────────────────────────

@router.get("/qbittorrent/status")
async def qbittorrent_status(db: AsyncSession = Depends(get_db)):
    """Check qBittorrent connection."""
    try:
        return await qbittorrent_service.check_connection(db)
    except Exception as exc:
        logger.error(f"qBittorrent status check failed: {type(exc).__name__}", exc_info=False)
        raise HTTPException(status_code=502, detail="Unable to check qBittorrent status") from exc


class QbittorrentTestRequest(BaseModel):
    url: str = ""
    username: str = ""
    password: str = ""


@router.post("/qbittorrent/test")
async def qbittorrent_test(body: QbittorrentTestRequest, db: AsyncSession = Depends(get_db)):
    """Test qBittorrent connection using inline credentials (falls back to DB for masked values)."""
    from app.services.settings_store import get_setting
    url = body.url or await get_setting(db, "qbittorrent_url", "")
    username = body.username or await get_setting(db, "qbittorrent_username", "")
    password = (
        body.password
        if body.password and body.password != "***"
        else await get_setting(db, "qbittorrent_password", "")
    )
    try:
        return await qbittorrent_service.check_connection_inline(url, username, password)
    except Exception as exc:
        logger.error(f"qBittorrent connection test failed: {type(exc).__name__}", exc_info=False)
        raise HTTPException(status_code=502, detail="Unable to connect to qBittorrent") from exc
