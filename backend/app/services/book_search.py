"""
Book search service.

Sources supported:
  - open_library  (no key required)
  - google_books  (no key required for basic usage; key improves quota)
"""
from __future__ import annotations

import httpx
from typing import Any

from app.config import get_settings

settings = get_settings()


# ─── schema ──────────────────────────────────────────────────────────────────

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
) -> dict[str, Any]:
    return {
        "source": source,
        "source_id": source_id,
        "content_type": "book",
        "title": title,
        "author": ", ".join(authors),
        "description": description,
        "cover_url": cover_url,
        "year": year,
        "genres": genres,
        "isbn": isbn,
    }


# ─── Open Library ────────────────────────────────────────────────────────────

async def _search_open_library(query: str, limit: int) -> list[dict]:
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
                source="open_library",
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


# ─── Google Books ─────────────────────────────────────────────────────────────

async def _search_google_books(query: str, limit: int) -> list[dict]:
    url = "https://www.googleapis.com/books/v1/volumes"
    params: dict[str, Any] = {"q": query, "maxResults": min(limit, 40), "printType": "books"}
    if settings.google_books_api_key:
        params["key"] = settings.google_books_api_key
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
    data = resp.json()
    results = []
    for item in data.get("items", []):
        info = item.get("volumeInfo", {})
        images = info.get("imageLinks", {})
        cover_url = images.get("thumbnail", images.get("smallThumbnail", ""))
        # Use HTTPS
        cover_url = cover_url.replace("http://", "https://")
        isbn = ""
        for ident in info.get("industryIdentifiers", []):
            if ident.get("type") in ("ISBN_13", "ISBN_10"):
                isbn = ident["identifier"]
                break
        published = info.get("publishedDate", "")
        year = published[:4] if published else ""
        results.append(
            _book_obj(
                source="google_books",
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


# ─── public entry point ───────────────────────────────────────────────────────

async def search_books(query: str, source: str = "all", limit: int = 20) -> list[dict]:
    """
    Search books. source may be 'open_library', 'google_books', or 'all'.
    """
    query = query.strip()
    if not query:
        return []

    if source == "open_library":
        return await _search_open_library(query, limit)
    if source == "google_books":
        return await _search_google_books(query, limit)

    # "all" — merge, deduplicate by title similarity (simple approach: keep both)
    ol, gb = [], []
    try:
        ol = await _search_open_library(query, limit // 2 or 10)
    except Exception:
        pass
    try:
        gb = await _search_google_books(query, limit // 2 or 10)
    except Exception:
        pass
    return ol + gb
