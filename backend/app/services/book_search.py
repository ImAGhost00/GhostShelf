from __future__ import annotations

import re
from html import unescape
from typing import Any
from urllib.parse import quote_plus, urljoin

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import ContentType
from app.services.prowlarr_service import search_releases
from app.services.settings_store import get_setting

ANNA_BASE = "https://annas-archive.org"
LIBGEN_BASE = "https://libgen.is"


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (value or "").casefold()).strip()


def _strip_tags(value: str) -> str:
    text = re.sub(r"<[^>]+>", " ", value or "")
    return " ".join(unescape(text).split())


def _book_obj(
    source: str,
    source_id: str,
    title: str,
    authors: list[str],
    description: str,
    cover_url: str,
    year: str,
    genres: list[str],
    isbn: str = "",
    available_sources: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "source": source,
        "source_id": source_id,
        "content_type": "book",
        "title": title,
        "author": ", ".join(a for a in authors if a),
        "description": description,
        "cover_url": cover_url,
        "year": year,
        "genres": genres,
        "isbn": isbn,
        "available_sources": available_sources or [source],
    }


async def _search_open_library(query: str, limit: int) -> list[dict[str, Any]]:
    url = "https://openlibrary.org/search.json"
    params = {"q": query, "limit": limit, "fields": "key,title,author_name,first_publish_year,cover_i,subject,isbn"}
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
    data = resp.json()
    results = []
    for doc in data.get("docs", []):
        cover_i = doc.get("cover_i")
        cover_url = f"https://covers.openlibrary.org/b/id/{cover_i}-M.jpg" if cover_i else ""
        isbn_list = doc.get("isbn", [])
        results.append(
            _book_obj(
                source="metadata",
                source_id=doc.get("key", ""),
                title=doc.get("title", "Unknown"),
                authors=doc.get("author_name", []),
                description="",
                cover_url=cover_url,
                year=str(doc.get("first_publish_year", "")),
                genres=doc.get("subject", [])[:5],
                isbn=isbn_list[0] if isbn_list else "",
            )
        )
    return results


async def _search_google_books(db: AsyncSession, query: str, limit: int) -> list[dict[str, Any]]:
    url = "https://www.googleapis.com/books/v1/volumes"
    params: dict[str, Any] = {"q": query, "maxResults": min(limit, 40), "printType": "books"}
    google_books_api_key = await get_setting(db, "google_books_api_key", "")
    if google_books_api_key:
        params["key"] = google_books_api_key
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
    data = resp.json()
    results = []
    for item in data.get("items", []):
        info = item.get("volumeInfo", {})
        images = info.get("imageLinks", {})
        cover_url = images.get("thumbnail", images.get("smallThumbnail", "")).replace("http://", "https://")
        isbn = ""
        for ident in info.get("industryIdentifiers", []):
            if ident.get("type") in ("ISBN_13", "ISBN_10"):
                isbn = ident["identifier"]
                break
        published = info.get("publishedDate", "")
        year = published[:4] if published else ""
        results.append(
            _book_obj(
                source="metadata",
                source_id=item.get("id", ""),
                title=info.get("title", "Unknown"),
                authors=info.get("authors", []),
                description=info.get("description", ""),
                cover_url=cover_url,
                year=year,
                genres=info.get("categories", []),
                isbn=isbn,
            )
        )
    return results


async def _metadata_candidates(db: AsyncSession, query: str, limit: int) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    try:
        results.extend(await _search_open_library(query, limit))
    except Exception:
        pass
    try:
        results.extend(await _search_google_books(db, query, limit))
    except Exception:
        pass
    return results


async def _search_libgen(query: str, limit: int) -> list[dict[str, Any]]:
    params = {
        "req": query,
        "fields": "Title,Author,Year,Identifier,MD5,Extension,Mirror_1,Mirror_2,Mirror_3",
        "limit": str(limit),
        "mode": "libgen",
    }
    headers = {"User-Agent": "GhostShelf/1.0"}
    out: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=18, follow_redirects=True, headers=headers) as client:
        resp = await client.get(f"{LIBGEN_BASE}/json.php", params=params)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            return out
        for row in data:
            if not isinstance(row, dict):
                continue
            title = str(row.get("Title", "") or "").strip()
            author = str(row.get("Author", "") or "").strip()
            if not title:
                continue
            out.append(
                {
                    "source": "libgen",
                    "source_id": str(row.get("MD5", "") or title),
                    "title": title,
                    "author": author,
                    "year": str(row.get("Year", "") or ""),
                }
            )
            if len(out) >= limit:
                break
    return out


async def _search_annas_archive(query: str, limit: int) -> list[dict[str, Any]]:
    url = f"{ANNA_BASE}/search?q={quote_plus(query)}"
    headers = {"User-Agent": "GhostShelf/1.0"}
    out: list[dict[str, Any]] = []
    pattern = re.compile(r'<a[^>]+href=["\'](?P<href>/md5/[^"\']+)["\'][^>]*>(?P<label>.*?)</a>', re.IGNORECASE | re.DOTALL)
    async with httpx.AsyncClient(timeout=18, follow_redirects=True, headers=headers) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        for match in pattern.finditer(resp.text):
            href = match.group("href")
            label = _strip_tags(match.group("label"))
            if not label:
                continue
            source_id = href.rsplit("/", 1)[-1]
            out.append(
                {
                    "source": "annas_archive",
                    "source_id": source_id,
                    "title": label,
                    "author": "",
                    "year": "",
                }
            )
            if len(out) >= limit:
                break
    return out


def _match_metadata(candidate: dict[str, Any], metadata_pool: list[dict[str, Any]]) -> dict[str, Any] | None:
    candidate_title = _normalize(candidate.get("title", ""))
    if not candidate_title:
        return None
    candidate_author = _normalize(candidate.get("author", ""))

    best: dict[str, Any] | None = None
    best_score = -1
    for meta in metadata_pool:
        meta_title = _normalize(meta.get("title", ""))
        if not meta_title:
            continue
        score = 0
        if candidate_title == meta_title:
            score += 6
        elif candidate_title in meta_title or meta_title in candidate_title:
            score += 4
        overlap = set(candidate_title.split()) & set(meta_title.split())
        score += min(len(overlap), 3)
        meta_author = _normalize(meta.get("author", ""))
        if candidate_author and meta_author and candidate_author in meta_author:
            score += 2
        if score > best_score:
            best_score = score
            best = meta
    return best if best_score >= 3 else None


def _merge_candidates(candidates: list[dict[str, Any]], metadata_pool: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for candidate in candidates:
        matched = _match_metadata(candidate, metadata_pool)
        title = matched.get("title") if matched else candidate.get("title", "")
        author = matched.get("author") if matched else candidate.get("author", "")
        key = f"{_normalize(title)}::{_normalize(author)}"
        if not key.strip(":"):
            continue
        if key not in merged:
            merged[key] = _book_obj(
                source=candidate.get("source", "book"),
                source_id=candidate.get("source_id", key),
                title=title,
                authors=[author] if author else [],
                description=matched.get("description", "") if matched else "",
                cover_url=matched.get("cover_url", "") if matched else "",
                year=matched.get("year", candidate.get("year", "")) if matched else candidate.get("year", ""),
                genres=matched.get("genres", []) if matched else [],
                isbn=matched.get("isbn", "") if matched else "",
                available_sources=[candidate.get("source", "book")],
            )
        else:
            existing_sources = merged[key].setdefault("available_sources", [])
            source = candidate.get("source", "book")
            if source not in existing_sources:
                existing_sources.append(source)
    return list(merged.values())[:limit]


async def search_books(db: AsyncSession, query: str, source: str = "all", limit: int = 20) -> list[dict[str, Any]]:
    query = query.strip()
    if not query:
        return []

    candidate_pool: list[dict[str, Any]] = []
    if source in {"all", "libgen"}:
        try:
            candidate_pool.extend(await _search_libgen(query, limit))
        except Exception:
            pass
    if source in {"all", "annas_archive"}:
        try:
            candidate_pool.extend(await _search_annas_archive(query, limit))
        except Exception:
            pass
    if source in {"all", "prowlarr"}:
        try:
            releases = await search_releases(db, query, ContentType.book, limit=limit)
            candidate_pool.extend(
                {
                    "source": "prowlarr",
                    "source_id": r.get("guid", r.get("title", "")),
                    "title": r.get("title", ""),
                    "author": "",
                    "year": "",
                }
                for r in releases
                if r.get("title")
            )
        except Exception:
            pass

    if not candidate_pool:
        return []

    metadata_pool = await _metadata_candidates(db, query, limit=min(25, limit * 2))
    return _merge_candidates(candidate_pool, metadata_pool, limit=limit)
