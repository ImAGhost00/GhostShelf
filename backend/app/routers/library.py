from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import ContentType
from app.services.library_service import check_many_owned, find_owned_match, get_library_overview

router = APIRouter(prefix="/library", tags=["library"])


class OwnedCheckRequest(BaseModel):
    title: str
    content_type: ContentType


class BatchOwnedCheckRequest(BaseModel):
    items: list[OwnedCheckRequest]


@router.get("")
async def library_overview(db: AsyncSession = Depends(get_db)):
    return await get_library_overview(db)


@router.post("/owned")
async def check_owned(body: OwnedCheckRequest, db: AsyncSession = Depends(get_db)):
    match = await find_owned_match(db, title=body.title, content_type=body.content_type)
    return {
        "title": body.title,
        "content_type": body.content_type.value,
        "owned": bool(match),
        "match": match,
    }


@router.post("/owned/batch")
async def check_owned_batch(body: BatchOwnedCheckRequest, db: AsyncSession = Depends(get_db)):
    items = [
        {"title": i.title, "content_type": i.content_type.value}
        for i in body.items
    ]
    matches = await check_many_owned(db, items)
    return {"items": matches}
