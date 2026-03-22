"""
Comics & Manga search service.

Sources supported:
  - mangadex     (no key required — manga)
  - comicvine    (API key required — Western comics)
  - anilist      (GraphQL, no key — anime/manga metadata)
"""
from __future__ import annotations

import httpx
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.settings_store import get_setting

MANGADEX_BASE = "https://api.mangadex.org"
COMICVINE_BASE = "https://comicvine.gamespot.com/api"
ANILIST_BASE = "https://graphql.anilist.co"


def _comic_obj(
    source: str,
    source_id: str,
    content_type: str,  # "comic" | "manga"
    title: str,
    authors: list[str],
    description: str,
    cover_url: str,
    year: str,
    genres: list[str],
) -> dict[str, Any]:
    return {
        "source": source,
        "source_id": source_id,
        "content_type": content_type,
        "title": title,
        "author": ", ".join(authors),
        "description": description,
        "cover_url": cover_url,
        "year": year,
        "genres": genres,
    }


# ─── MangaDex ─────────────────────────────────────────────────────────────────

async def _search_mangadex(query: str, limit: int) -> list[dict]:
    params = {
        "title": query,
        "limit": limit,
        "includes[]": ["cover_art", "author"],
        "order[relevance]": "desc",
    }
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{MANGADEX_BASE}/manga", params=params)
        resp.raise_for_status()
    data = resp.json()
    results = []
    for item in data.get("data", []):
        attrs = item.get("attributes", {})
        md_id = item.get("id", "")

        # Title (prefer English, fallback to first available)
        title_map = attrs.get("title", {})
        title = title_map.get("en") or next(iter(title_map.values()), "Unknown")

        # Description
        desc_map = attrs.get("description", {})
        description = desc_map.get("en") or next(iter(desc_map.values()), "")

        # Year
        year = str(attrs.get("year", "")) if attrs.get("year") else ""

        # Genres / tags
        genres = []
        for tag in attrs.get("tags", []):
            tag_name = tag.get("attributes", {}).get("name", {})
            en_name = tag_name.get("en", "")
            if en_name:
                genres.append(en_name)

        # Cover
        cover_url = ""
        for rel in item.get("relationships", []):
            if rel.get("type") == "cover_art":
                fname = rel.get("attributes", {}).get("fileName", "")
                if fname:
                    cover_url = f"https://uploads.mangadex.org/covers/{md_id}/{fname}.256.jpg"
                break

        # Authors
        authors = []
        for rel in item.get("relationships", []):
            if rel.get("type") == "author":
                a_name = rel.get("attributes", {}).get("name", "")
                if a_name:
                    authors.append(a_name)

        results.append(
            _comic_obj(
                source="mangadex",
                source_id=md_id,
                content_type="manga",
                title=title,
                authors=authors,
                description=description,
                cover_url=cover_url,
                year=year,
                genres=genres[:6],
            )
        )
    return results


# ─── ComicVine ────────────────────────────────────────────────────────────────

async def _search_comicvine(db: AsyncSession, query: str, limit: int) -> list[dict]:
    comicvine_api_key = await get_setting(db, "comicvine_api_key", "")
    if not comicvine_api_key:
        return []
    params = {
        "api_key": comicvine_api_key,
        "format": "json",
        "query": query,
        "resources": "volume",
        "limit": limit,
    }
    headers = {"User-Agent": "GhostShelf/1.0"}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.get(f"{COMICVINE_BASE}/search/", params=params, headers=headers)
        resp.raise_for_status()
    data = resp.json()
    results = []
    for item in data.get("results", []):
        cover = item.get("image", {})
        cover_url = cover.get("medium_url") or cover.get("small_url", "")
        start_year = str(item.get("start_year", "")) if item.get("start_year") else ""
        publisher = item.get("publisher", {})
        pub_name = publisher.get("name", "") if publisher else ""
        results.append(
            _comic_obj(
                source="comicvine",
                source_id=str(item.get("id", "")),
                content_type="comic",
                title=item.get("name", "Unknown"),
                authors=[],
                description=item.get("deck", "") or item.get("description", ""),
                cover_url=cover_url,
                year=start_year,
                genres=[pub_name] if pub_name else [],
            )
        )
    return results


# ─── AniList ──────────────────────────────────────────────────────────────────

ANILIST_QUERY = """
query ($search: String, $perPage: Int) {
  Page(perPage: $perPage) {
    media(search: $search, type: MANGA) {
      id
      title { english romaji native }
      description(asHtml: false)
      coverImage { large medium }
      startDate { year }
      genres
      staff(perPage: 3) {
        edges {
          node { name { full } }
          role
        }
      }
    }
  }
}
"""


async def _search_anilist(query: str, limit: int) -> list[dict]:
    payload = {"query": ANILIST_QUERY, "variables": {"search": query, "perPage": limit}}
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(ANILIST_BASE, json=payload)
        resp.raise_for_status()
    data = resp.json()
    results = []
    for item in data.get("data", {}).get("Page", {}).get("media", []):
        title_data = item.get("title", {})
        title = title_data.get("english") or title_data.get("romaji") or title_data.get("native", "Unknown")
        cover = item.get("coverImage", {})
        cover_url = cover.get("large") or cover.get("medium", "")
        start_date = item.get("startDate", {})
        year = str(start_date.get("year", "")) if start_date.get("year") else ""
        authors = []
        for edge in item.get("staff", {}).get("edges", []):
            role = edge.get("role", "")
            if "Story" in role or "Art" in role or "Original" in role:
                name = edge.get("node", {}).get("name", {}).get("full", "")
                if name:
                    authors.append(name)
        description = item.get("description", "") or ""
        results.append(
            _comic_obj(
                source="anilist",
                source_id=str(item.get("id", "")),
                content_type="manga",
                title=title,
                authors=authors,
                description=description[:500],
                cover_url=cover_url,
                year=year,
                genres=item.get("genres", [])[:6],
            )
        )
    return results


# ─── public entry point ───────────────────────────────────────────────────────

async def search_comics(
    db: AsyncSession,
    query: str,
    source: str = "all",
    content_type: str = "all",  # "comic" | "manga" | "all"
    limit: int = 20,
) -> list[dict]:
    """
    Search comics / manga.

    source:       'mangadex' | 'comicvine' | 'anilist' | 'all'
    content_type: 'comic'    | 'manga'     | 'all'
    """
    query = query.strip()
    if not query:
        return []

    wanted_manga = content_type in ("manga", "all")
    wanted_comic = content_type in ("comic", "all")

    tasks: list[Any] = []

    if source == "mangadex" and wanted_manga:
        return await _search_mangadex(query, limit)
    if source == "comicvine" and wanted_comic:
        return await _search_comicvine(db, query, limit)
    if source == "anilist" and wanted_manga:
        return await _search_anilist(query, limit)

    # "all"
    per = max(limit // 2, 5)
    results: list[dict] = []
    if wanted_manga:
        try:
            results += await _search_mangadex(query, per)
        except Exception:
            pass
        try:
            results += await _search_anilist(query, per)
        except Exception:
            pass
    if wanted_comic:
        try:
            results += await _search_comicvine(db, query, per)
        except Exception:
            pass
    return results
