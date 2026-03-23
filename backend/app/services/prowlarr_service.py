from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import ContentType
from app.services.settings_store import get_setting

ENGLISH_LANGUAGE_CODES = {"en", "eng", "en-us", "en-gb", "english"}


def _prowlarr_category(content_type: ContentType) -> str:
    # Newznab categories: Books=7000, Comics=7030
    if content_type == ContentType.book:
        return "7000"
    return "7030"


async def _base(db: AsyncSession) -> tuple[str, str]:
    url = (await get_setting(db, "prowlarr_url", "")).rstrip("/")
    api_key = await get_setting(db, "prowlarr_api_key", "")
    return url, api_key


async def check_connection(db: AsyncSession) -> dict[str, Any]:
    url, api_key = await _base(db)
    return await check_connection_inline(url, api_key)


async def check_connection_inline(url: str, api_key: str) -> dict[str, Any]:
    if not url:
        return {"connected": False, "error": "Prowlarr URL not configured"}
    if not api_key:
        return {"connected": False, "error": "Prowlarr API key not configured"}
    url = url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.get(
                f"{url}/api/v1/system/status",
                headers={"X-Api-Key": api_key},
            )
            if resp.status_code == 200:
                data = resp.json()
                return {
                    "connected": True,
                    "version": data.get("version", ""),
                    "appName": data.get("appName", "Prowlarr"),
                }
            return {"connected": False, "error": f"HTTP {resp.status_code}"}
    except Exception as exc:
        return {"connected": False, "error": str(exc)}


def _language_tokens(value: Any) -> set[str]:
    tokens: set[str] = set()
    if value is None:
        return tokens
    if isinstance(value, str):
        cleaned = value.strip().casefold()
        if cleaned:
            tokens.add(cleaned)
        return tokens
    if isinstance(value, dict):
        for key in ("name", "value", "code", "label", "displayName"):
            tokens.update(_language_tokens(value.get(key)))
        return tokens
    if isinstance(value, list):
        for item in value:
            tokens.update(_language_tokens(item))
    return tokens


def _is_english_release(item: dict[str, Any]) -> bool:
    language_tokens: set[str] = set()
    for key in ("languages", "language", "lang"):
        language_tokens.update(_language_tokens(item.get(key)))

    if not language_tokens:
        return True

    for token in language_tokens:
        if token in ENGLISH_LANGUAGE_CODES:
            return True
        if token.startswith("en-"):
            return True
    return False


async def search_releases(
    db: AsyncSession,
    query: str,
    content_type: ContentType,
    limit: int = 20,
) -> list[dict[str, Any]]:
    url, api_key = await _base(db)
    if not url or not api_key:
        return []

    params = {
        "query": query,
        "categories": _prowlarr_category(content_type),
        "type": "search",
    }
    headers = {"X-Api-Key": api_key}

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{url}/api/v1/search", params=params, headers=headers)
        resp.raise_for_status()

    data = resp.json()
    out: list[dict[str, Any]] = []
    for item in data:
        if not _is_english_release(item):
            continue
        out.append(
            {
                "title": item.get("title", ""),
                "indexer": item.get("indexer", ""),
                "indexerId": item.get("indexerId"),
                "guid": item.get("guid", ""),
                "downloadUrl": item.get("downloadUrl") or item.get("guid") or "",
                "publishDate": item.get("publishDate", ""),
                "size": item.get("size", 0),
                "seeders": item.get("seeders", 0),
            }
        )
        if len(out) >= limit:
            break
    return out
