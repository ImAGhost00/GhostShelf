from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional
from urllib.parse import urlparse

from app.database import get_db
from app.models.models import DownloadItem, ContentType
from app.services.download_service import start_direct_download
from app.services.prowlarr_service import search_releases
from app.services.qbittorrent_service import (
    cancel_download as cancel_qbittorrent_download,
    enqueue_download as enqueue_qbittorrent_download,
    refresh_downloads as refresh_qbittorrent_downloads,
)
from app.services.smart_download_service import find_direct_urls
from app.services.library_service import find_owned_match

router = APIRouter(prefix="/downloads", tags=["downloads"])


def _normalize_title(value: str) -> str:
    return " ".join(value.strip().split()).casefold()


def _looks_like_torrent_url(url: str) -> bool:
    cleaned = (url or "").strip().lower()
    if cleaned.startswith("magnet:"):
        return True
    if "xt=urn:btih:" in cleaned:
        return True
    parsed = urlparse(cleaned)
    return parsed.path.endswith(".torrent")


async def _get_active_duplicate(
    db: AsyncSession,
    title: str,
    content_type: ContentType,
) -> DownloadItem | None:
    result = await db.execute(
        select(DownloadItem).where(
            DownloadItem.content_type == content_type,
            DownloadItem.status.in_(["queued", "downloading"]),
        )
    )
    target = _normalize_title(title)
    for item in result.scalars().all():
        if _normalize_title(item.title) == target:
            return item
    return None


async def _ensure_not_duplicate_active(
    db: AsyncSession,
    title: str,
    content_type: ContentType,
) -> None:
    existing = await _get_active_duplicate(db, title, content_type)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f'"{title}" is already downloading (id={existing.id})',
        )


async def _ensure_not_already_owned(
    db: AsyncSession,
    title: str,
    content_type: ContentType,
) -> None:
    owned_match = await find_owned_match(db, title=title, content_type=content_type)
    if owned_match:
        source = owned_match.get("source") or "library"
        library = owned_match.get("library") or ""
        where = f" in {library}" if library else ""
        raise HTTPException(
            status_code=409,
            detail=f'"{title}" appears to already exist in {source}{where}',
        )


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


class SmartAutoRequest(BaseModel):
    title: str
    content_type: ContentType
    watchlist_id: Optional[int] = None
    destination: Optional[str] = None


def _item_to_dict(item: DownloadItem, extra: dict | None = None) -> dict:
    data = {
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
    if extra:
        data.update(extra)
    return data


@router.get("")
async def list_downloads(db: AsyncSession = Depends(get_db)):
    progress_by_id = await refresh_qbittorrent_downloads(db)
    result = await db.execute(select(DownloadItem).order_by(DownloadItem.created_at.desc()))
    return [_item_to_dict(i, progress_by_id.get(i.id)) for i in result.scalars().all()]


@router.post("", status_code=201)
async def queue_download(body: DownloadRequest, db: AsyncSession = Depends(get_db)):
    """Add an item to the download queue."""
    await _ensure_not_duplicate_active(db, body.title, body.content_type)
    await _ensure_not_already_owned(db, body.title, body.content_type)
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
    """Download directly from an HTTP URL or queue a torrent/magnet in qBittorrent."""
    await _ensure_not_duplicate_active(db, body.title, body.content_type)
    await _ensure_not_already_owned(db, body.title, body.content_type)
    if _looks_like_torrent_url(body.download_url):
        result = await enqueue_qbittorrent_download(
            db=db,
            title=body.title,
            content_type=body.content_type,
            source_url=body.download_url,
            watchlist_id=body.watchlist_id,
            destination=body.destination,
        )
        if not result.get("ok"):
            raise HTTPException(status_code=400, detail=result.get("error", "Download failed"))
        return result

    if not body.download_url.startswith(("http://", "https://")):
        raise HTTPException(status_code=400, detail="download_url must be http://, https://, or magnet:")
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
    """Search Prowlarr by title and either direct-download or queue the best release."""
    await _ensure_not_duplicate_active(db, body.title, body.content_type)
    await _ensure_not_already_owned(db, body.title, body.content_type)
    results = await search_releases(db=db, query=body.title, content_type=body.content_type, limit=25)
    chosen = next((r for r in results if str(r.get("downloadUrl", "")).strip()), None)
    if not chosen:
        raise HTTPException(status_code=404, detail="No downloadable result found in Prowlarr")

    download_url = str(chosen.get("downloadUrl", "")).strip()
    result = await enqueue_qbittorrent_download(
        db=db,
        title=body.title,
        content_type=body.content_type,
        source_url=download_url,
        watchlist_id=body.watchlist_id,
        destination=body.destination,
    )

    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "Download failed"))
    return {
        "release": chosen,
        "download": result,
    }


@router.post("/auto", status_code=201)
async def smart_auto_download(body: SmartAutoRequest, db: AsyncSession = Depends(get_db)):
    """Workflow: try Anna's Archive / Libgen first, fallback to Prowlarr indexers."""
    await _ensure_not_duplicate_active(db, body.title, body.content_type)
    await _ensure_not_already_owned(db, body.title, body.content_type)
    direct_attempt_error: str | None = None

    direct_candidates = await find_direct_urls(body.title, body.content_type)
    if direct_candidates:
        primary = direct_candidates[0]
        mirrors = [c["url"] for c in direct_candidates[1:6]]
        direct = await start_direct_download(
            db=db,
            title=body.title,
            content_type=body.content_type,
            download_url=primary["url"],
            mirror_urls=mirrors,
            watchlist_id=body.watchlist_id,
            destination=body.destination,
        )
        if direct.get("ok"):
            return {
                "strategy": "direct-first",
                "source": primary.get("source", "direct"),
                "download": direct,
                "used_url": primary["url"],
                "candidate_count": len(direct_candidates),
            }
        direct_attempt_error = str(direct.get("error", "Direct source failed"))

    # Fallback to Prowlarr indexer search when direct sources miss/fail.
    releases = await search_releases(db=db, query=body.title, content_type=body.content_type, limit=25)
    chosen = next((r for r in releases if str(r.get("downloadUrl", "")).strip()), None)
    if not chosen:
        detail = "No direct source found and no downloadable Prowlarr result found"
        if direct_attempt_error:
            detail = f"{detail}. Direct error: {direct_attempt_error}"
        raise HTTPException(status_code=404, detail=detail)

    fallback_url = str(chosen.get("downloadUrl", "")).strip()
    fallback = await enqueue_qbittorrent_download(
        db=db,
        title=body.title,
        content_type=body.content_type,
        source_url=fallback_url,
        watchlist_id=body.watchlist_id,
        destination=body.destination,
    )
    if not fallback.get("ok"):
        raise HTTPException(status_code=400, detail=fallback.get("error", "Download failed"))

    return {
        "strategy": "prowlarr-fallback",
        "source": "prowlarr",
        "release": chosen,
        "download": fallback,
        "direct_candidate_count": len(direct_candidates),
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
    if status == "cancelled":
        await cancel_qbittorrent_download(db, item)
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
