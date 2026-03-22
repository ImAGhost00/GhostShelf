from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.routers import books, comics, watchlist, downloads, integrations, settings as settings_router

_settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title=_settings.app_name,
    version=_settings.app_version,
    description="GhostShelf — unified discovery for books (Calibre-Web Automated) and comics/manga (Komga)",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(books.router, prefix="/api")
app.include_router(comics.router, prefix="/api")
app.include_router(watchlist.router, prefix="/api")
app.include_router(downloads.router, prefix="/api")
app.include_router(integrations.router, prefix="/api")
app.include_router(settings_router.router, prefix="/api")


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": _settings.app_name, "version": _settings.app_version}
