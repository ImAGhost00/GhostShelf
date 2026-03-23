from fastapi import APIRouter, Query, HTTPException
from fastapi import Depends
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.comic_search import search_comics

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/comics", tags=["comics"])


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1, max_length=200, description="Search query"),
    source: str = Query("prowlarr", description="Source: prowlarr"),
    content_type: str = Query("all", description="Type: comic | manga | all"),
    limit: int = Query(20, ge=1, le=40),
    db: AsyncSession = Depends(get_db),
):
    """Search comics and manga from Prowlarr and enrich metadata automatically."""
    try:
        results = await search_comics(db, q, source=source, content_type=content_type, limit=limit)
        return {"query": q, "source": source, "content_type": content_type, "total": len(results), "results": results}
    except ValueError as exc:
        logger.warning(f"Search validation error: {exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Search error: {exc}", exc_info=False)
        raise HTTPException(status_code=502, detail="Search service unavailable") from exc
