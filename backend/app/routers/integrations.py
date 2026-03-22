from __future__ import annotations

from fastapi import APIRouter, HTTPException
from typing import Optional

from app.services import komga_service, cwa_service, prowlarr_service, qbittorrent_service
from app.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import Depends

router = APIRouter(prefix="/integrations", tags=["integrations"])


# ─── Komga ────────────────────────────────────────────────────────────────────

@router.get("/komga/status")
async def komga_status(db: AsyncSession = Depends(get_db)):
    """Check Komga connection."""
    return await komga_service.check_connection(db)


@router.get("/komga/libraries")
async def komga_libraries(db: AsyncSession = Depends(get_db)):
    """List Komga libraries."""
    try:
        return await komga_service.get_libraries(db)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/komga/libraries/{library_id}/scan")
async def komga_scan(library_id: str, db: AsyncSession = Depends(get_db)):
    """Trigger a Komga library scan."""
    try:
        return await komga_service.scan_library(db, library_id)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


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
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ─── CWA ──────────────────────────────────────────────────────────────────────

@router.get("/cwa/status")
async def cwa_status(db: AsyncSession = Depends(get_db)):
    """Check CWA connection."""
    return await cwa_service.check_connection(db)


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
        raise HTTPException(status_code=502, detail=str(exc)) from exc


# ─── qBittorrent ──────────────────────────────────────────────────────────────

@router.get("/qbittorrent/status")
async def qbittorrent_status(db: AsyncSession = Depends(get_db)):
    """Check qBittorrent connection."""
    try:
        return await qbittorrent_service.check_connection(db)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
