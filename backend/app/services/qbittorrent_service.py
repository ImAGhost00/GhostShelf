from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import ContentType, DownloadItem, ItemStatus, WatchlistItem
from app.services.download_service import get_download_target_folder
from app.services.settings_store import get_setting


async def check_connection(db: AsyncSession) -> dict[str, Any]:
    url = await get_setting(db, "qbittorrent_url", "")
    username = await get_setting(db, "qbittorrent_username", "")
    password = await get_setting(db, "qbittorrent_password", "")
    return await check_connection_inline(url, username, password)


async def check_connection_inline(url: str, username: str, password: str) -> dict[str, Any]:
    base_url = url.rstrip("/")
    if not base_url:
        return {"connected": False, "error": "qBittorrent URL not configured"}
    try:
        async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
            if username and password:
                login = await client.post(
                    f"{base_url}/api/v2/auth/login",
                    data={"username": username, "password": password},
                )
                if login.status_code >= 400:
                    return {"connected": False, "error": f"HTTP {login.status_code}"}
                if "ok" not in login.text.lower():
                    return {"connected": False, "error": "Login failed"}
            version_resp = await client.get(f"{base_url}/api/v2/app/version")
            if version_resp.status_code == 200:
                return {
                    "connected": True,
                    "version": version_resp.text.strip(),
                    "authenticated": bool(username and password),
                }
            return {"connected": False, "error": f"HTTP {version_resp.status_code}"}
    except Exception as exc:
        return {"connected": False, "error": str(exc)}


async def enqueue_download(
    db: AsyncSession,
    title: str,
    content_type: ContentType,
    source_url: str,
    watchlist_id: int | None = None,
    destination: str | None = None,
) -> dict[str, Any]:
    """Queue a magnet or torrent URL in qBittorrent."""
    folder = await get_download_target_folder(db, content_type, destination)
    if not folder:
        return {"ok": False, "error": "Destination folder not configured"}

    base_url = (await get_setting(db, "qbittorrent_url", "")).rstrip("/")
    username = await get_setting(db, "qbittorrent_username", "")
    password = await get_setting(db, "qbittorrent_password", "")
    if not base_url:
        return {"ok": False, "error": "qBittorrent URL not configured"}

    download = DownloadItem(
        watchlist_id=watchlist_id,
        title=title,
        content_type=content_type,
        download_url=source_url,
        status="queued",
        destination=folder,
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

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            if username and password:
                login = await client.post(
                    f"{base_url}/api/v2/auth/login",
                    data={"username": username, "password": password},
                )
                if login.status_code >= 400 or "ok" not in login.text.lower():
                    raise RuntimeError("qBittorrent login failed")

            add_resp = await client.post(
                f"{base_url}/api/v2/torrents/add",
                data={"urls": source_url, "savepath": folder},
            )
            if add_resp.status_code >= 400:
                raise RuntimeError(f"qBittorrent add failed with HTTP {add_resp.status_code}")

        return {
            "ok": True,
            "download_id": download.id,
            "destination": folder,
            "status": download.status,
            "queued_in": "qbittorrent",
        }
    except Exception as exc:
        download.status = "failed"
        download.error_message = str(exc)
        if watchlist_item:
            watchlist_item.status = ItemStatus.failed
        await db.commit()
        return {"ok": False, "download_id": download.id, "error": str(exc), "status": download.status}
