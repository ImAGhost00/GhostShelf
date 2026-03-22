from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.models import AppSetting


async def get_setting(db: AsyncSession, key: str, default: str = "") -> str:
    """Read runtime setting from DB, falling back to environment settings."""
    result = await db.execute(select(AppSetting).where(AppSetting.key == key))
    row = result.scalar_one_or_none()
    if row and row.value is not None:
        return row.value

    settings = get_settings()
    env_val = getattr(settings, key, default)
    if env_val is None:
        return default
    return str(env_val)
