from __future__ import annotations

import os
import re
import urllib.parse
import logging
from typing import Any

import aiofiles
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.models import ContentType, DownloadItem, WatchlistItem, ItemStatus
from app.services.settings_store import get_setting

logger = logging.getLogger(__name__)


def _safe_filename(name: str) -> str:
    name = re.sub(r"[\\/:*?\"<>|]+", "_", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name[:180] if name else "download"


def _extension_from_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url)
    path = parsed.path or ""
    _, ext = os.path.splitext(path)
    return ext[:12] if ext else ""


def _validate_destination_path(destination: str) -> bool:
    """
    Validate that destination path is safe and within allowed directories.
    Prevents path traversal attacks by verifying resolved path is within expected roots.
    """
    if not destination:
        return False
    
    # Resolve symlinks and relative paths
    try:
        real_dest = os.path.realpath(destination)
    except (OSError, ValueError):
        logger.warning(f"Failed to resolve destination path: {destination}")
        return False
    
    # Get allowed root directories
    allowed_roots = [
        "/media/MediaPool/books",
        "/media/MediaPool/book-ingest",
        "/media/MediaPool/comics",
        "/media/MediaPool/manga",
        "/media/MediaPool/downloads",
        "/media/downloads",
    ]
    
    # Allow any path that starts with an allowed root (with proper separator)
    for allowed_root in allowed_roots:
        try:
            real_root = os.path.realpath(allowed_root)
            # Check if destination is within this root
            if real_dest == real_root or real_dest.startswith(real_root + os.sep):
                return True
        except (OSError, ValueError):
            continue
    
    logger.warning(f"Attempted download to path outside allowed directories: {destination}")
    return False


async def get_download_target_folder(db: AsyncSession, content_type: ContentType, explicit_destination: str | None) -> str:
    # If user provided a destination, validate it before using
    if explicit_destination:
        if not _validate_destination_path(explicit_destination):
            raise ValueError(f"Destination path is not allowed: {explicit_destination}")
        return explicit_destination
    
    if content_type == ContentType.book:
        return await get_setting(db, "cwa_ingest_folder", "")
    if content_type == ContentType.comic:
        comic_folder = await get_setting(db, "comic_ingest_folder", "")
        if comic_folder:
            return comic_folder
        return await get_setting(db, "komga_ingest_folder", "")
    if content_type == ContentType.manga:
        manga_folder = await get_setting(db, "manga_ingest_folder", "")
        if manga_folder:
            return manga_folder
        return await get_setting(db, "komga_ingest_folder", "")
    return await get_setting(db, "komga_ingest_folder", "")


async def start_direct_download(
    db: AsyncSession,
    title: str,
    content_type: ContentType,
    download_url: str,
    mirror_urls: list[str] | None = None,
    watchlist_id: int | None = None,
    destination: str | None = None,
) -> dict[str, Any]:
    """Download a file immediately and persist lifecycle in downloads table."""
    download = DownloadItem(
        watchlist_id=watchlist_id,
        title=title,
        content_type=content_type,
        download_url=download_url,
        status="downloading",
        destination=destination,
    )
    db.add(download)
    await db.commit()
    await db.refresh(download)

    watchlist_item: WatchlistItem | None = None
    if watchlist_id:
        result = await db.execute(select(WatchlistItem).where(WatchlistItem.id == watchlist_id))
        watchlist_item = result.scalar_one_or_none()
        if watchlist_item:
            watchlist_item.status = ItemStatus.downloading
            await db.commit()

    folder = await get_download_target_folder(db, content_type, destination)
    if not folder:
        download.status = "failed"
        download.error_message = "Destination folder not configured"
        if watchlist_item:
            watchlist_item.status = ItemStatus.failed
        await db.commit()
        return {"ok": False, "error": download.error_message, "download_id": download.id}

    try:
        os.makedirs(folder, exist_ok=True)

        urls = [download_url] + (mirror_urls or [])
        # Keep order but remove duplicates and blanks
        seen: set[str] = set()
        candidates: list[str] = []
        for u in urls:
            clean = (u or "").strip()
            if clean and clean not in seen:
                seen.add(clean)
                candidates.append(clean)

        errors: list[str] = []
        used_url = ""
        filepath = ""

        async with httpx.AsyncClient(timeout=90, follow_redirects=True) as client:
            for candidate in candidates:
                try:
                    ext = _extension_from_url(candidate)
                    filename = f"{_safe_filename(title)}{ext or '.bin'}"
                    filepath = os.path.join(folder, filename)

                    async with client.stream("GET", candidate) as response:
                        response.raise_for_status()
                        async with aiofiles.open(filepath, "wb") as f:
                            async for chunk in response.aiter_bytes(1024 * 128):
                                if chunk:
                                    await f.write(chunk)
                    used_url = candidate
                    break
                except Exception as exc:
                    errors.append(f"{candidate}: {exc}")

        if not used_url:
            raise RuntimeError("All direct URLs and mirrors failed: " + " | ".join(errors[:4]))

        download.status = "done"
        download.destination = filepath
        download.download_url = used_url
        download.error_message = None
        if watchlist_item:
            watchlist_item.status = ItemStatus.downloaded
        await db.commit()
        return {
            "ok": True,
            "download_id": download.id,
            "destination": filepath,
            "status": download.status,
        }
    except Exception as exc:
        download.status = "failed"
        download.error_message = str(exc)
        if watchlist_item:
            watchlist_item.status = ItemStatus.failed
        await db.commit()
        return {"ok": False, "download_id": download.id, "error": str(exc), "status": download.status}
