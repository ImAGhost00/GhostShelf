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

from app.models.models import ContentType
from app.services.prowlarr_service import search_releases
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
        "available_sources": [source],
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

    target_content_type = ContentType.comic if content_type == "comic" else ContentType.manga

    releases = await search_releases(db=db, query=query, content_type=target_content_type, limit=max(limit * 2, 25))
    metadata_candidates: list[dict[str, Any]] = []
    if target_content_type == ContentType.comic:
        try:
            metadata_candidates.extend(await _search_comicvine(db, query, limit))
        except Exception:
            pass
    else:
        try:
            metadata_candidates.extend(await _search_mangadex(query, limit))
        except Exception:
            pass
        try:
            metadata_candidates.extend(await _search_anilist(query, limit))
        except Exception:
            pass

    def normalize(value: str) -> str:
        return " ".join(value.casefold().split())

    def strong_key(value: str) -> str:
        return "".join(ch for ch in normalize(value) if ch.isalnum())

    def title_score(left: str, right: str) -> int:
        left_norm = normalize(left)
        right_norm = normalize(right)
        if not left_norm or not right_norm:
            return 0
        if left_norm == right_norm:
            return 8
        if left_norm in right_norm or right_norm in left_norm:
            return 5
        left_words = set(left_norm.split())
        right_words = set(right_norm.split())
        overlap = left_words & right_words
        return min(len(overlap), 4)

    def find_meta(title: str) -> dict[str, Any] | None:
        target = normalize(title)
        best = None
        best_score = -1
        for meta in metadata_candidates:
            meta_title = normalize(str(meta.get("title", "")))
            if not meta_title:
                continue
            score = 0
            if target == meta_title:
                score += 6
            elif target in meta_title or meta_title in target:
                score += 4
            overlap = set(target.split()) & set(meta_title.split())
            score += min(len(overlap), 3)
            if score > best_score:
                best_score = score
                best = meta
        return best if best_score >= 3 else None

    if target_content_type == ContentType.manga:
        merged_manga: dict[str, dict[str, Any]] = {}

        for meta in metadata_candidates:
            title = str(meta.get("title", "") or "").strip()
            if not title:
                continue
            key = strong_key(title)
            if not key:
                continue

            related_releases = [release for release in releases if title_score(title, str(release.get("title", ""))) >= 4]
            available_sources = list(dict.fromkeys([meta.get("source", "manga"), *("prowlarr",) if related_releases else tuple()]))
            meta_result = dict(meta)
            meta_result["available_sources"] = [source for source in available_sources if source]
            merged_manga[key] = meta_result

        for release in releases:
            release_title = str(release.get("title", "") or "").strip()
            if not release_title:
                continue
            meta = find_meta(release_title)
            title = str(meta.get("title") if meta else release_title)
            key = strong_key(title)
            if not key:
                continue
            if key in merged_manga:
                sources = merged_manga[key].setdefault("available_sources", [])
                if "prowlarr" not in sources:
                    sources.append("prowlarr")
                continue
            merged_manga[key] = _comic_obj(
                source="prowlarr",
                source_id=str(release.get("guid", release_title)),
                content_type=target_content_type.value,
                title=title,
                authors=[str(meta.get("author", ""))] if meta and meta.get("author") else [],
                description=str(meta.get("description", "")) if meta else "",
                cover_url=str(meta.get("cover_url", "")) if meta else "",
                year=str(meta.get("year", "")) if meta else "",
                genres=list(meta.get("genres", [])) if meta else [],
            )

        return list(merged_manga.values())[:limit]

    if not releases:
        return metadata_candidates[:limit]

    merged: dict[str, dict[str, Any]] = {}
    for release in releases:
        release_title = str(release.get("title", "") or "").strip()
        if not release_title:
            continue
        meta = find_meta(release_title)
        title = str(meta.get("title") if meta else release_title)
        key = normalize(title)
        if key not in merged:
            merged[key] = _comic_obj(
                source="prowlarr",
                source_id=str(release.get("guid", release_title)),
                content_type=target_content_type.value,
                title=title,
                authors=[str(meta.get("author", ""))] if meta and meta.get("author") else [],
                description=str(meta.get("description", "")) if meta else "",
                cover_url=str(meta.get("cover_url", "")) if meta else "",
                year=str(meta.get("year", "")) if meta else "",
                genres=list(meta.get("genres", [])) if meta else [],
            )
        else:
            sources = merged[key].setdefault("available_sources", [])
            if "prowlarr" not in sources:
                sources.append("prowlarr")

    return list(merged.values())[:limit]
