from fastapi import APIRouter, Query, HTTPException
from fastapi import Depends
import logging
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.book_search import search_books

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/books", tags=["books"])


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1, max_length=200, description="Search query"),
    source: str = Query("all", description="Source: libgen | annas_archive | prowlarr | all"),
    limit: int = Query(20, ge=1, le=40),
    db: AsyncSession = Depends(get_db),
):
    """Search books across Libgen, Anna's Archive, and Prowlarr with metadata enrichment."""
    try:
        results = await search_books(db, q, source=source, limit=limit)
        return {"query": q, "source": source, "total": len(results), "results": results}
    except ValueError as exc:
        logger.warning(f"Search validation error: {exc}")
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.error(f"Search error: {exc}", exc_info=False)
        raise HTTPException(status_code=502, detail="Search service unavailable") from exc
