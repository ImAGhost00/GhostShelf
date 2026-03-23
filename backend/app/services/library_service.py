from __future__ import annotations

import re
from typing import Any
from urllib.parse import urljoin
from xml.etree import ElementTree

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import ContentType
from app.services import komga_service
from app.services.settings_store import get_setting


def _normalize_title(value: str) -> str:
    return " ".join((value or "").strip().split()).casefold()


def _remove_parenthetical(value: str) -> str:
    return re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", value or "")


def _series_key(value: str) -> str:
    cleaned = _remove_parenthetical(value)
    cleaned = re.sub(r"\b(volume|vol\.?|v\.?|book|issue|chapter|ch\.?|part|pt\.?)\s*\d+[\w.-]*\b", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"[^a-zA-Z0-9]+", " ", cleaned)
    return _normalize_title(cleaned)


def _extract_volume_numbers(value: str) -> set[int]:
    text = value or ""
    nums: set[int] = set()
    for pattern in (
        r"\b(?:volume|vol\.?|v\.?|book)\s*(\d{1,4})\b",
        r"\b(?:issues?|ch(?:apter)?|ch\.?|part|pt\.?)\s*(\d{1,4})\b",
        r"\b(\d{1,4})\b",
    ):
        for match in re.findall(pattern, text, flags=re.IGNORECASE):
            try:
                nums.add(int(match))
            except ValueError:
                continue
    return nums


def _komga_entry_to_owned(entry: dict[str, Any], library_name: str | None = None) -> dict[str, Any]:
    metadata = entry.get("metadata") or {}
    books_count = entry.get("booksCount") or entry.get("books_count")
    title = str(metadata.get("title") or entry.get("name") or "")
    return {
        "source": "komga",
        "id": str(entry.get("id") or ""),
        "title": title,
        "author": str(metadata.get("summary") or ""),
        "content_type": "comic",
        "library": library_name or "",
        "books_count": books_count if isinstance(books_count, int) else 0,
        "volume_numbers": sorted(_extract_volume_numbers(title)),
        "series_key": _series_key(title),
    }


def _komga_book_to_owned(
    entry: dict[str, Any],
    library_name: str | None = None,
    default_content_type: str = "comic",
) -> dict[str, Any]:
    metadata = entry.get("metadata") or {}
    series_title = str(metadata.get("seriesTitle") or metadata.get("title") or entry.get("name") or "")
    number = str(metadata.get("number") or "").strip()
    title = f"{series_title} {number}".strip() if series_title else str(metadata.get("title") or entry.get("name") or "")
    return {
        "source": "komga",
        "id": str(entry.get("id") or ""),
        "title": title,
        "author": "",
        "content_type": default_content_type,
        "library": library_name or "",
        "books_count": 1,
        "volume_numbers": sorted(_extract_volume_numbers(title)),
        "series_key": _series_key(series_title or title),
    }


def _calibre_entry_to_owned(title: str, author: str = "") -> dict[str, Any]:
    return {
        "source": "calibre",
        "id": _normalize_title(f"{title}::{author}"),
        "title": title,
        "author": author,
        "content_type": "book",
        "library": "Calibre",
        "books_count": 1,
        "volume_numbers": sorted(_extract_volume_numbers(title)),
        "series_key": _series_key(title),
    }


async def _fetch_calibre_books_from_opds(
    cwa_url: str,
    limit: int = 200,
    opds_url_override: str = "",
    username: str = "",
    password: str = "",
) -> list[dict[str, Any]]:
    if not cwa_url and not opds_url_override:
        return []
    opds_url = opds_url_override.strip() or f"{cwa_url.rstrip('/')}/opds"
    auth = (username, password) if username and password else None
    async with httpx.AsyncClient(timeout=15, follow_redirects=True, auth=auth) as client:
        try:
            root = await _opds_fetch_root(client, opds_url)
        except Exception:
            return []

        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "dc": "http://purl.org/dc/terms/",
        }
        out: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        # Parse current feed first (can already contain acquisition entries).
        _opds_extract_books(root, ns, out, seen_ids, limit)
        if len(out) >= limit:
            return out

        # Traverse navigation/subsection links one level deep to discover actual books.
        nav_links = _opds_navigation_links(root, ns, base_url=opds_url)
        for link in nav_links[:30]:
            try:
                sub_root = await _opds_fetch_root(client, link)
            except Exception:
                continue
            _opds_extract_books(sub_root, ns, out, seen_ids, limit)
            if len(out) >= limit:
                break
        return out


async def _opds_fetch_root(client: httpx.AsyncClient, url: str) -> ElementTree.Element:
    resp = await client.get(url)
    resp.raise_for_status()
    return ElementTree.fromstring(resp.text)


def _opds_navigation_links(root: ElementTree.Element, ns: dict[str, str], base_url: str) -> list[str]:
    links: list[str] = []
    for entry in root.findall("atom:entry", ns):
        for link in entry.findall("atom:link", ns):
            rel = (link.attrib.get("rel") or "").lower()
            href = (link.attrib.get("href") or "").strip()
            typ = (link.attrib.get("type") or "").lower()
            if not href:
                continue
            if "acquisition" in rel:
                continue
            if "atom+xml" in typ or rel in {"subsection", "collection"}:
                links.append(urljoin(base_url, href))
    return links


def _opds_extract_books(
    root: ElementTree.Element,
    ns: dict[str, str],
    out: list[dict[str, Any]],
    seen_ids: set[str],
    limit: int,
) -> None:
    for entry in root.findall("atom:entry", ns):
        title = (entry.findtext("atom:title", default="", namespaces=ns) or "").strip()
        author = (entry.findtext("dc:creator", default="", namespaces=ns) or "").strip()
        entry_id = (entry.findtext("atom:id", default="", namespaces=ns) or "").strip()

        has_acquisition = False
        for link in entry.findall("atom:link", ns):
            rel = (link.attrib.get("rel") or "").lower()
            if "acquisition" in rel:
                has_acquisition = True
                break

        if not title or not has_acquisition:
            continue

        dedupe_id = entry_id or _normalize_title(f"{title}::{author}")
        if dedupe_id in seen_ids:
            continue
        seen_ids.add(dedupe_id)
        out.append(_calibre_entry_to_owned(title=title, author=author))
        if len(out) >= limit:
            return


async def get_komga_owned_items(db: AsyncSession, limit_per_library: int = 200) -> list[dict[str, Any]]:
    libraries = await komga_service.get_libraries(db)
    all_items: list[dict[str, Any]] = []

    for lib in libraries:
        lib_id = str(lib.get("id") or "")
        lib_name = str(lib.get("name") or "")
        lib_type = str(lib.get("type") or "").lower()
        default_type = "manga" if "manga" in lib_type or "manga" in lib_name.lower() else "comic"

        # Prefer books-level listing to preserve volume/chapter granularity.
        book_page = 0
        book_fetched = 0
        while book_fetched < limit_per_library:
            books = await komga_service.get_books(
                db,
                library_id=lib_id,
                page=book_page,
                size=100,
            )
            chunk = books.get("content") or []
            if not chunk:
                break
            for entry in chunk:
                all_items.append(_komga_book_to_owned(entry, lib_name, default_content_type=default_type))
            book_fetched += len(chunk)
            if len(chunk) < 100:
                break
            book_page += 1

        if book_fetched > 0:
            continue

        # Fallback to series-level listing if books endpoint is unavailable.
        page = 0
        fetched = 0
        size = 100
        while fetched < limit_per_library:
            series = await komga_service.get_series(db, library_id=lib_id, page=page, size=size)
            chunk = series.get("content") or []
            if not chunk:
                break
            for entry in chunk:
                mapped = _komga_entry_to_owned(entry, lib_name)
                mapped["content_type"] = default_type
                all_items.append(mapped)
            fetched += len(chunk)
            if len(chunk) < size:
                break
            page += 1
    return all_items


async def get_calibre_owned_items(db: AsyncSession, limit: int = 300) -> list[dict[str, Any]]:
    cwa_url = await get_setting(db, "cwa_url", "")
    cwa_opds_url = await get_setting(db, "cwa_opds_url", "")
    cwa_username = await get_setting(db, "cwa_username", "")
    cwa_password = await get_setting(db, "cwa_password", "")
    return await _fetch_calibre_books_from_opds(
        cwa_url,
        limit=limit,
        opds_url_override=cwa_opds_url,
        username=cwa_username,
        password=cwa_password,
    )


async def get_library_overview(db: AsyncSession) -> dict[str, Any]:
    komga_items: list[dict[str, Any]] = []
    calibre_items: list[dict[str, Any]] = []
    komga_error = ""
    calibre_error = ""

    try:
        komga_items = await get_komga_owned_items(db)
    except Exception as exc:
        komga_error = str(exc)

    try:
        calibre_items = await get_calibre_owned_items(db)
    except Exception as exc:
        calibre_error = str(exc)

    return {
        "komga": {
            "count": len(komga_items),
            "items": komga_items,
            "error": komga_error or None,
        },
        "calibre": {
            "count": len(calibre_items),
            "items": calibre_items,
            "error": calibre_error or None,
        },
        "total": len(komga_items) + len(calibre_items),
    }


def _matches_owned_item(title: str, content_type: ContentType, owned: dict[str, Any]) -> bool:
    target_series = _series_key(title)
    owned_series = str(owned.get("series_key") or "")
    if not target_series or not owned_series:
        return False

    if target_series != owned_series:
        return False

    if content_type == ContentType.book:
        return True

    # Comics/manga can share a base series while requesting a specific volume/chapter.
    target_numbers = _extract_volume_numbers(title)
    owned_numbers = set(owned.get("volume_numbers") or [])

    if not target_numbers:
        return True
    if not owned_numbers:
        books_count = int(owned.get("books_count") or 0)
        return books_count > 0
    return not target_numbers.isdisjoint(owned_numbers)


async def find_owned_match(db: AsyncSession, title: str, content_type: ContentType) -> dict[str, Any] | None:
    content_is_book = content_type == ContentType.book
    owned_items: list[dict[str, Any]] = []

    if content_is_book:
        try:
            owned_items.extend(await get_calibre_owned_items(db, limit=400))
        except Exception:
            pass
    else:
        try:
            owned_items.extend(await get_komga_owned_items(db, limit_per_library=400))
        except Exception:
            pass

    for owned in owned_items:
        if _matches_owned_item(title, content_type, owned):
            return {
                "source": owned.get("source"),
                "title": owned.get("title"),
                "library": owned.get("library"),
            }
    return None


async def check_many_owned(
    db: AsyncSession,
    items: list[dict[str, str]],
) -> list[dict[str, Any]]:
    overview = await get_library_overview(db)
    owned_pool = (overview.get("komga", {}).get("items") or []) + (overview.get("calibre", {}).get("items") or [])

    out: list[dict[str, Any]] = []
    for item in items:
        title = str(item.get("title") or "")
        raw_type = str(item.get("content_type") or "book")
        try:
            content_type = ContentType(raw_type)
        except ValueError:
            content_type = ContentType.book

        match = None
        for owned in owned_pool:
            if _matches_owned_item(title, content_type, owned):
                match = {
                    "source": owned.get("source"),
                    "title": owned.get("title"),
                    "library": owned.get("library"),
                }
                break
        out.append(
            {
                "title": title,
                "content_type": content_type.value,
                "owned": bool(match),
                "match": match,
            }
        )
    return out
