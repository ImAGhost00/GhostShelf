from fastapi import APIRouter, Query, HTTPException
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.comic_search import search_comics

router = APIRouter(prefix="/comics", tags=["comics"])


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    source: str = Query("all", description="Source: mangadex | comicvine | anilist | all"),
    content_type: str = Query("all", description="Type: comic | manga | all"),
    limit: int = Query(20, ge=1, le=40),
    db: AsyncSession = Depends(get_db),
):
    """Search for comics and manga across configured sources."""
    try:
        results = await search_comics(db, q, source=source, content_type=content_type, limit=limit)
        return {"query": q, "source": source, "content_type": content_type, "total": len(results), "results": results}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Search failed: {exc}") from exc
