from fastapi import APIRouter, Query, HTTPException
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.book_search import search_books

router = APIRouter(prefix="/books", tags=["books"])


@router.get("/search")
async def search(
    q: str = Query(..., min_length=1, description="Search query"),
    source: str = Query("all", description="Source: open_library | google_books | all"),
    limit: int = Query(20, ge=1, le=40),
    db: AsyncSession = Depends(get_db),
):
    """Search for books across configured sources."""
    try:
        results = await search_books(db, q, source=source, limit=limit)
        return {"query": q, "source": source, "total": len(results), "results": results}
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Search failed: {exc}") from exc
