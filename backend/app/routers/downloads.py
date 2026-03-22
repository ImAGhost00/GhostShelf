from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models.models import DownloadItem, ContentType
from app.services.download_service import start_direct_download
from app.services.prowlarr_service import search_releases

router = APIRouter(prefix="/downloads", tags=["downloads"])


class DownloadRequest(BaseModel):
    title: str
    content_type: ContentType
    download_url: Optional[str] = None
    watchlist_id: Optional[int] = None
    destination: Optional[str] = None


class DirectDownloadRequest(BaseModel):
    title: str
    content_type: ContentType
    download_url: str
    mirror_urls: list[str] = []
    watchlist_id: Optional[int] = None
    destination: Optional[str] = None


class ProwlarrAutoRequest(BaseModel):
    title: str
    content_type: ContentType
    watchlist_id: Optional[int] = None
    destination: Optional[str] = None


def _item_to_dict(item: DownloadItem) -> dict:
    return {
        "id": item.id,
        "watchlist_id": item.watchlist_id,
        "title": item.title,
        "content_type": item.content_type,
        "download_url": item.download_url,
        "status": item.status,
        "destination": item.destination,
        "error_message": item.error_message,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


@router.get("")
async def list_downloads(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DownloadItem).order_by(DownloadItem.created_at.desc()))
    return [_item_to_dict(i) for i in result.scalars().all()]


@router.post("", status_code=201)
async def queue_download(body: DownloadRequest, db: AsyncSession = Depends(get_db)):
    """Add an item to the download queue."""
    item = DownloadItem(
        title=body.title,
        content_type=body.content_type,
        download_url=body.download_url,
        watchlist_id=body.watchlist_id,
        destination=body.destination,
        status="queued",
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _item_to_dict(item)


@router.post("/direct", status_code=201)
async def direct_download(body: DirectDownloadRequest, db: AsyncSession = Depends(get_db)):
    """Download directly from an HTTP URL into the configured ingest folder."""
    if not body.download_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="download_url must be http:// or https://")
    for mirror in body.mirror_urls:
        if not mirror.startswith(("http://", "https://")):
            raise HTTPException(status_code=400, detail="All mirror URLs must be http:// or https://")
    result = await start_direct_download(
        db=db,
        title=body.title,
        content_type=body.content_type,
        download_url=body.download_url,
        mirror_urls=body.mirror_urls,
        watchlist_id=body.watchlist_id,
        destination=body.destination,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Download failed"))
    return result


@router.get("/prowlarr/search")
async def prowlarr_search(
    q: str,
    content_type: ContentType,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Search releases via Prowlarr."""
    try:
        results = await search_releases(db=db, query=q, content_type=content_type, limit=limit)
        return {"query": q, "total": len(results), "results": results}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Prowlarr search failed: {exc}") from exc


@router.post("/prowlarr/auto", status_code=201)
async def prowlarr_auto(body: ProwlarrAutoRequest, db: AsyncSession = Depends(get_db)):
    """Search Prowlarr by title and direct-download the top HTTP result."""
    results = await search_releases(db=db, query=body.title, content_type=body.content_type, limit=25)
    chosen = next((r for r in results if str(r.get("downloadUrl", "")).startswith(("http://", "https://"))), None)
    if not chosen:
        raise HTTPException(status_code=404, detail="No direct HTTP result found in Prowlarr")

    result = await start_direct_download(
        db=db,
        title=body.title,
        content_type=body.content_type,
        download_url=chosen["downloadUrl"],
        watchlist_id=body.watchlist_id,
        destination=body.destination,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Download failed"))
    return {
        "release": chosen,
        "download": result,
    }


@router.patch("/{item_id}/status")
async def update_download_status(
    item_id: int,
    status: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(DownloadItem).where(DownloadItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Download not found")
    allowed = {"queued", "downloading", "done", "failed", "cancelled"}
    if status not in allowed:
        raise HTTPException(status_code=400, detail=f"Status must be one of: {', '.join(allowed)}")
    item.status = status
    await db.commit()
    await db.refresh(item)
    return _item_to_dict(item)


@router.delete("/{item_id}", status_code=204)
async def remove_download(item_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DownloadItem).where(DownloadItem.id == item_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Download not found")
    await db.execute(delete(DownloadItem).where(DownloadItem.id == item_id))
    await db.commit()
