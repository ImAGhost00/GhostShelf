from __future__ import annotations

import os
import re
import shutil
from typing import Any
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import ContentType, DownloadItem, ItemStatus, WatchlistItem
from app.services.download_service import get_download_target_folder
from app.services.settings_store import get_setting

TAG_PREFIX = "ghostshelf-"


def _webui_headers(base_url: str) -> dict[str, str]:
    parsed = urlsplit(base_url)
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return {
        "Origin": origin,
        "Referer": f"{origin}/",
    }


def _download_tag(download_id: int) -> str:
    return f"{TAG_PREFIX}{download_id}"


def _parse_download_id_from_tags(tags: str | None) -> int | None:
    for tag in (tags or "").split(","):
        clean = tag.strip()
        if clean.startswith(TAG_PREFIX):
            suffix = clean[len(TAG_PREFIX):]
            if suffix.isdigit():
                return int(suffix)
    return None


async def _login_client(client: httpx.AsyncClient, base_url: str, username: str, password: str) -> None:
    if username and password:
        login = await client.post(
            f"{base_url}/api/v2/auth/login",
            data={"username": username, "password": password},
        )
        if login.status_code >= 400 or "ok" not in login.text.lower():
            raise RuntimeError("qBittorrent login failed")


async def _get_categories(client: httpx.AsyncClient, base_url: str) -> dict[str, Any]:
    response = await client.get(f"{base_url}/api/v2/torrents/categories")
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else {}


async def _ensure_category_exists(client: httpx.AsyncClient, base_url: str, category: str) -> None:
    clean = (category or "").strip()
    if not clean:
        return
    categories = await _get_categories(client, base_url)
    if clean in categories:
        return
    response = await client.post(
        f"{base_url}/api/v2/torrents/createCategory",
        data={"category": clean},
    )
    if response.status_code >= 400:
        raise RuntimeError(f'Unable to create qBittorrent category "{clean}"')


async def _category_for_content_type(db: AsyncSession, content_type: ContentType) -> str:
    key_map = {
        ContentType.book: "qbittorrent_book_category",
        ContentType.comic: "qbittorrent_comic_category",
        ContentType.manga: "qbittorrent_manga_category",
    }
    key = key_map.get(content_type)
    if not key:
        return ""
    return (await get_setting(db, key, "")).strip()


def _normalize_path(path: str) -> str:
    return path.replace("\\", "/").rstrip("/")


def _map_remote_path_to_local(remote_path: str, remote_root: str, local_root: str) -> str:
    remote_path_norm = _normalize_path(remote_path)
    remote_root_norm = _normalize_path(remote_root)
    local_root_norm = _normalize_path(local_root)

    if remote_path_norm.startswith(remote_root_norm + "/"):
        rel_path = remote_path_norm[len(remote_root_norm) + 1:]
        return os.path.join(local_root_norm, *rel_path.split("/"))
    return os.path.join(local_root_norm, os.path.basename(remote_path_norm))


def _torrent_is_complete(torrent: dict[str, Any]) -> bool:
    progress = float(torrent.get("progress") or 0.0)
    amount_left = int(torrent.get("amount_left") or 0)
    state = str(torrent.get("state") or "")
    return progress >= 1.0 or amount_left == 0 or state in {"uploading", "stalledUP", "pausedUP", "queuedUP", "forcedUP", "checkingUP"}


def _torrent_is_failed(torrent: dict[str, Any]) -> bool:
    state = str(torrent.get("state") or "").lower()
    return "error" in state or "missingfiles" in state


def _unique_target_path(base_dir: str, name: str) -> str:
    candidate = os.path.join(base_dir, name)
    if not os.path.exists(candidate):
        return candidate
    stem, ext = os.path.splitext(name)
    index = 1
    while True:
        alt_name = f"{stem} ({index}){ext}"
        alt_path = os.path.join(base_dir, alt_name)
        if not os.path.exists(alt_path):
            return alt_path
        index += 1


async def _update_watchlist_status(db: AsyncSession, watchlist_id: int | None, status: ItemStatus) -> None:
    if not watchlist_id:
        return
    result = await db.execute(select(WatchlistItem).where(WatchlistItem.id == watchlist_id))
    item = result.scalar_one_or_none()
    if item:
        item.status = status


async def _fetch_torrents(client: httpx.AsyncClient, base_url: str) -> list[dict[str, Any]]:
    response = await client.get(f"{base_url}/api/v2/torrents/info")
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, list) else []


async def _finalize_completed_torrent(
    client: httpx.AsyncClient,
    base_url: str,
    db: AsyncSession,
    download: DownloadItem,
    torrent: dict[str, Any],
    remote_root: str,
    local_root: str,
) -> dict[str, Any]:
    target_dir = download.destination or await get_download_target_folder(db, download.content_type, None)
    if not target_dir:
        raise RuntimeError("Final destination folder not configured")

    remote_content_path = str(torrent.get("content_path") or "")
    if not remote_content_path:
        remote_save_path = str(torrent.get("save_path") or remote_root)
        remote_name = str(torrent.get("name") or download.title)
        remote_content_path = f"{_normalize_path(remote_save_path)}/{remote_name}"

    local_content_path = _map_remote_path_to_local(remote_content_path, remote_root, local_root)
    if not os.path.exists(local_content_path):
        raise RuntimeError(f"Completed download not found locally: {local_content_path}")

    torrent_hash = str(torrent.get("hash") or "")
    if torrent_hash:
        await client.post(
            f"{base_url}/api/v2/torrents/delete",
            data={"hashes": torrent_hash, "deleteFiles": "false"},
        )

    os.makedirs(target_dir, exist_ok=True)
    base_name = os.path.basename(local_content_path.rstrip(os.sep))
    final_path = _unique_target_path(target_dir, base_name)
    moved_path = shutil.move(local_content_path, final_path)

    download.status = "done"
    download.destination = moved_path
    download.error_message = None
    await _update_watchlist_status(db, download.watchlist_id, ItemStatus.downloaded)

    return {
        "progress": 1,
        "eta": 0,
        "speed": 0,
        "upload_speed": 0,
        "state": "completed",
        "save_path": moved_path,
        "hash": str(torrent.get("hash") or ""),
        "category": str(torrent.get("category") or ""),
        "size": int(torrent.get("size") or torrent.get("total_size") or 0),
        "downloaded": int(torrent.get("downloaded") or torrent.get("completed") or 0),
    }


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
        async with httpx.AsyncClient(timeout=12, follow_redirects=True, headers=_webui_headers(base_url)) as client:
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
    final_folder = await get_download_target_folder(db, content_type, destination)
    if not final_folder:
        return {"ok": False, "error": "Destination folder not configured"}

    base_url = (await get_setting(db, "qbittorrent_url", "")).rstrip("/")
    username = await get_setting(db, "qbittorrent_username", "")
    password = await get_setting(db, "qbittorrent_password", "")
    qb_download_folder = await get_setting(db, "qbittorrent_download_folder", "/data/downloads")
    category = await _category_for_content_type(db, content_type)
    if not base_url:
        return {"ok": False, "error": "qBittorrent URL not configured"}

    download = DownloadItem(
        watchlist_id=watchlist_id,
        title=title,
        content_type=content_type,
        download_url=source_url,
        status="queued",
        destination=final_folder,
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
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=_webui_headers(base_url)) as client:
            await _login_client(client, base_url, username, password)
            await _ensure_category_exists(client, base_url, category)

            add_resp = await client.post(
                f"{base_url}/api/v2/torrents/add",
                data={
                    "urls": source_url,
                    "savepath": qb_download_folder,
                    "category": category,
                    "tags": _download_tag(download.id),
                },
            )
            if add_resp.status_code >= 400:
                raise RuntimeError(f"qBittorrent add failed with HTTP {add_resp.status_code}")

        return {
            "ok": True,
            "download_id": download.id,
            "destination": final_folder,
            "status": download.status,
            "queued_in": "qbittorrent",
            "category": category,
        }
    except Exception as exc:
        download.status = "failed"
        download.error_message = str(exc)
        if watchlist_item:
            watchlist_item.status = ItemStatus.failed
        await db.commit()
        return {"ok": False, "download_id": download.id, "error": str(exc), "status": download.status}


async def refresh_downloads(db: AsyncSession) -> dict[int, dict[str, Any]]:
    """Sync active download records with qBittorrent and finalize completed jobs."""
    result = await db.execute(select(DownloadItem).where(DownloadItem.status.in_(["queued", "downloading"])))
    downloads = result.scalars().all()
    if not downloads:
        return {}

    base_url = (await get_setting(db, "qbittorrent_url", "")).rstrip("/")
    username = await get_setting(db, "qbittorrent_username", "")
    password = await get_setting(db, "qbittorrent_password", "")
    qb_download_folder = await get_setting(db, "qbittorrent_download_folder", "/data/downloads")
    local_downloads_folder = await get_setting(db, "local_downloads_folder", "/media/downloads")
    if not base_url:
        return {}

    metadata: dict[int, dict[str, Any]] = {}
    changed = False

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=_webui_headers(base_url)) as client:
            await _login_client(client, base_url, username, password)
            torrents = await _fetch_torrents(client, base_url)
            torrents_by_download_id = {
                download_id: torrent
                for torrent in torrents
                if (download_id := _parse_download_id_from_tags(torrent.get("tags"))) is not None
            }

            for download in downloads:
                torrent = torrents_by_download_id.get(download.id)
                if not torrent:
                    continue

                if _torrent_is_failed(torrent):
                    download.status = "failed"
                    download.error_message = str(torrent.get("state") or "Torrent failed")
                    await _update_watchlist_status(db, download.watchlist_id, ItemStatus.failed)
                    metadata[download.id] = {
                        "progress": float(torrent.get("progress") or 0.0),
                        "eta": int(torrent.get("eta") or 0),
                        "speed": int(torrent.get("dlspeed") or 0),
                        "upload_speed": int(torrent.get("upspeed") or 0),
                        "state": str(torrent.get("state") or "failed"),
                        "save_path": str(torrent.get("save_path") or ""),
                        "hash": str(torrent.get("hash") or ""),
                        "category": str(torrent.get("category") or ""),
                        "size": int(torrent.get("size") or torrent.get("total_size") or 0),
                        "downloaded": int(torrent.get("downloaded") or torrent.get("completed") or 0),
                    }
                    changed = True
                    continue

                if _torrent_is_complete(torrent):
                    metadata[download.id] = await _finalize_completed_torrent(
                        client,
                        base_url,
                        db,
                        download,
                        torrent,
                        qb_download_folder,
                        local_downloads_folder,
                    )
                    changed = True
                    continue

                progress = float(torrent.get("progress") or 0.0)
                download.status = "downloading" if progress > 0 else "queued"
                download.error_message = None
                metadata[download.id] = {
                    "progress": progress,
                    "eta": int(torrent.get("eta") or 0),
                    "speed": int(torrent.get("dlspeed") or 0),
                    "upload_speed": int(torrent.get("upspeed") or 0),
                    "state": str(torrent.get("state") or download.status),
                    "save_path": str(torrent.get("save_path") or ""),
                    "hash": str(torrent.get("hash") or ""),
                    "category": str(torrent.get("category") or ""),
                    "size": int(torrent.get("size") or torrent.get("total_size") or 0),
                    "downloaded": int(torrent.get("downloaded") or torrent.get("completed") or 0),
                }
                changed = True
    except Exception:
        return metadata

    if changed:
        await db.commit()
    return metadata


async def cancel_download(db: AsyncSession, download: DownloadItem) -> None:
    """Cancel an active qBittorrent-backed download using the download tag."""
    base_url = (await get_setting(db, "qbittorrent_url", "")).rstrip("/")
    username = await get_setting(db, "qbittorrent_username", "")
    password = await get_setting(db, "qbittorrent_password", "")
    if not base_url:
        return

    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True, headers=_webui_headers(base_url)) as client:
            await _login_client(client, base_url, username, password)
            torrents = await _fetch_torrents(client, base_url)
            tag = _download_tag(download.id)
            hashes = [str(t.get("hash") or "") for t in torrents if tag in str(t.get("tags") or "")]
            hashes = [h for h in hashes if h]
            if hashes:
                await client.post(
                    f"{base_url}/api/v2/torrents/delete",
                    data={"hashes": "|".join(hashes), "deleteFiles": "false"},
                )
    except Exception:
        return
