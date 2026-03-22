from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models.models import WatchlistItem, ContentType, ItemStatus

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class WatchlistAddRequest(BaseModel):
    title: str
    author: Optional[str] = None
    description: Optional[str] = None
    cover_url: Optional[str] = None
    content_type: ContentType
    source: Optional[str] = None
    source_id: Optional[str] = None
    year: Optional[str] = None
    genres: Optional[list[str]] = None
    notes: Optional[str] = None


class WatchlistUpdateRequest(BaseModel):
    status: Optional[ItemStatus] = None
    notes: Optional[str] = None


def _item_to_dict(item: WatchlistItem) -> dict:
    return {
        "id": item.id,
        "title": item.title,
        "author": item.author,
        "description": item.description,
        "cover_url": item.cover_url,
        "content_type": item.content_type,
        "status": item.status,
        "source": item.source,
        "source_id": item.source_id,
        "year": item.year,
        "genres": item.genres.split(",") if item.genres else [],
        "notes": item.notes,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


@router.get("")
async def list_watchlist(db: AsyncSession = Depends(get_db)):
    """Return all watchlist items."""
    result = await db.execute(select(WatchlistItem).order_by(WatchlistItem.created_at.desc()))
    items = result.scalars().all()
    return [_item_to_dict(i) for i in items]


@router.post("", status_code=201)
async def add_to_watchlist(body: WatchlistAddRequest, db: AsyncSession = Depends(get_db)):
    """Add an item to the watchlist."""
    genres_str = ",".join(body.genres) if body.genres else None
    item = WatchlistItem(
        title=body.title,
        author=body.author,
        description=body.description,
        cover_url=body.cover_url,
        content_type=body.content_type,
        source=body.source,
        source_id=body.source_id,
        year=body.year,
        genres=genres_str,
        notes=body.notes,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return _item_to_dict(item)


@router.patch("/{item_id}")
async def update_watchlist_item(
    item_id: int, body: WatchlistUpdateRequest, db: AsyncSession = Depends(get_db)
):
    """Update status or notes on a watchlist item."""
    result = await db.execute(select(WatchlistItem).where(WatchlistItem.id == item_id))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    if body.status is not None:
        item.status = body.status
    if body.notes is not None:
        item.notes = body.notes
    await db.commit()
    await db.refresh(item)
    return _item_to_dict(item)


@router.delete("/{item_id}", status_code=204)
async def remove_from_watchlist(item_id: int, db: AsyncSession = Depends(get_db)):
    """Remove an item from the watchlist."""
    result = await db.execute(select(WatchlistItem).where(WatchlistItem.id == item_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Item not found")
    await db.execute(delete(WatchlistItem).where(WatchlistItem.id == item_id))
    await db.commit()
