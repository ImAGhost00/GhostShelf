from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote_plus, urljoin, urlparse

import httpx

from app.models.models import ContentType

ANNA_BASE = "https://annas-archive.org"
LIBGEN_BASE = "https://libgen.is"
FILE_EXTENSIONS = {
    ".epub",
    ".mobi",
    ".azw3",
    ".pdf",
    ".cbz",
    ".cbr",
    ".zip",
    ".rar",
}


def _clean_query(query: str) -> str:
    return " ".join(query.split()).strip()


def _extract_hrefs(html: str) -> list[str]:
    return re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)


def _looks_like_direct_file(url: str) -> bool:
    parsed = urlparse(url)
    path = (parsed.path or "").lower()
    if any(path.endswith(ext) for ext in FILE_EXTENSIONS):
        return True
    if "get.php" in path:
        return True
    if "download" in path and any(ext in (parsed.query or "").lower() for ext in FILE_EXTENSIONS):
        return True
    return False


def _as_absolute(base: str, href: str) -> str:
    if href.startswith("//"):
        return f"https:{href}"
    return urljoin(base, href)


async def _annas_archive_candidates(query: str, limit: int = 5) -> list[str]:
    url = f"{ANNA_BASE}/search?q={quote_plus(query)}"
    headers = {"User-Agent": "GhostShelf/1.0"}
    out: list[str] = []

    async with httpx.AsyncClient(timeout=18, follow_redirects=True, headers=headers) as client:
        search_resp = await client.get(url)
        search_resp.raise_for_status()
        search_links = [_as_absolute(ANNA_BASE, h) for h in _extract_hrefs(search_resp.text)]

        # Drill into a few detail pages (/md5/...) and collect likely direct file mirrors.
        details = [l for l in search_links if "/md5/" in l][:limit]
        for detail_url in details:
            try:
                detail_resp = await client.get(detail_url)
                detail_resp.raise_for_status()
                for href in _extract_hrefs(detail_resp.text):
                    candidate = _as_absolute(detail_url, href)
                    if _looks_like_direct_file(candidate):
                        out.append(candidate)
            except Exception:
                continue

    return out


async def _libgen_candidates(query: str, limit: int = 8) -> list[str]:
    # Libgen JSON API shape can vary by mirror; keep parsing defensive.
    params = {
        "req": query,
        "fields": "Title,Author,MD5,Extension,Mirror_1,Mirror_2,Mirror_3",
        "limit": str(limit),
        "mode": "libgen",
    }
    headers = {"User-Agent": "GhostShelf/1.0"}
    out: list[str] = []

    async with httpx.AsyncClient(timeout=18, follow_redirects=True, headers=headers) as client:
        resp = await client.get(f"{LIBGEN_BASE}/json.php", params=params)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            return out

        for row in data:
            if not isinstance(row, dict):
                continue

            mirrors = [
                str(row.get("Mirror_1", "") or "").strip(),
                str(row.get("Mirror_2", "") or "").strip(),
                str(row.get("Mirror_3", "") or "").strip(),
            ]
            mirrors = [m for m in mirrors if m.startswith(("http://", "https://"))]

            for mirror in mirrors:
                if _looks_like_direct_file(mirror):
                    out.append(mirror)
                    continue
                try:
                    mirror_resp = await client.get(mirror)
                    mirror_resp.raise_for_status()
                    for href in _extract_hrefs(mirror_resp.text):
                        candidate = _as_absolute(mirror, href)
                        if _looks_like_direct_file(candidate):
                            out.append(candidate)
                except Exception:
                    continue

    return out


def _dedupe(urls: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for u in urls:
        clean = (u or "").strip()
        if clean and clean not in seen:
            seen.add(clean)
            out.append(clean)
    return out


async def find_direct_urls(query: str, content_type: ContentType) -> list[dict[str, Any]]:
    # The same sources can return books/comics/manga; query drives relevance.
    q = _clean_query(query)
    if not q:
        return []

    candidates: list[dict[str, Any]] = []

    try:
        anna_urls = await _annas_archive_candidates(q)
        candidates.extend({"source": "annas_archive", "url": u, "content_type": content_type.value} for u in anna_urls)
    except Exception:
        pass

    try:
        libgen_urls = await _libgen_candidates(q)
        candidates.extend({"source": "libgen", "url": u, "content_type": content_type.value} for u in libgen_urls)
    except Exception:
        pass

    unique = _dedupe([c["url"] for c in candidates])
    by_url = {c["url"]: c for c in candidates}
    return [by_url[u] for u in unique]
