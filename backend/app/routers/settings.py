from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models.models import AppSetting

router = APIRouter(prefix="/settings", tags=["settings"])

# These are the keys that can be persisted to the DB
ALLOWED_KEYS = {
    "cwa_url",
    "cwa_opds_url",
    "cwa_username",
    "cwa_password",
    "cwa_ingest_folder",
    "komga_ingest_folder",
    "comic_ingest_folder",
    "manga_ingest_folder",
    "komga_url",
    "komga_username",
    "komga_password",
    "google_books_api_key",
    "comicvine_api_key",
    "prowlarr_url",
    "prowlarr_api_key",
    "qbittorrent_url",
    "qbittorrent_username",
    "qbittorrent_password",
    "qbittorrent_book_category",
    "qbittorrent_comic_category",
    "qbittorrent_manga_category",
    "qbittorrent_download_folder",
    "local_downloads_folder",
}


class SettingUpdate(BaseModel):
    key: str
    value: Optional[str] = None


@router.get("")
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Return all persisted settings (passwords are masked)."""
    result = await db.execute(select(AppSetting))
    rows = result.scalars().all()
    data = {}
    for row in rows:
        val = row.value or ""
        # Mask sensitive fields
        if "password" in row.key or "api_key" in row.key:
            val = "***" if val else ""
        data[row.key] = val
    return data


@router.post("")
async def upsert_setting(body: SettingUpdate, db: AsyncSession = Depends(get_db)):
    """Create or update a setting."""
    if body.key not in ALLOWED_KEYS:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail=f"Unknown setting key: {body.key}")

    result = await db.execute(select(AppSetting).where(AppSetting.key == body.key))
    row = result.scalar_one_or_none()
    if row:
        row.value = body.value
    else:
        row = AppSetting(key=body.key, value=body.value)
        db.add(row)
    await db.commit()
    return {"key": body.key, "saved": True}


@router.post("/bulk")
async def upsert_settings_bulk(body: dict, db: AsyncSession = Depends(get_db)):
    """Save multiple settings at once."""
    saved = []
    for key, value in body.items():
        if key not in ALLOWED_KEYS:
            continue
        # Frontend sends masked values for secrets. Skip those so we do not overwrite real values.
        if isinstance(value, str) and value.strip() == "***":
            continue
        result = await db.execute(select(AppSetting).where(AppSetting.key == key))
        row = result.scalar_one_or_none()
        if row:
            row.value = str(value) if value is not None else None
        else:
            row = AppSetting(key=key, value=str(value) if value is not None else None)
            db.add(row)
        saved.append(key)
    await db.commit()
    return {"saved": saved}
