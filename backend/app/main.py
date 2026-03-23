from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import init_db
from app.init_admin import init_admin
from app.routers import auth, books, comics, watchlist, downloads, integrations, settings as settings_router
from app.routers.auth import get_current_user

_settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    # Initialize default admin user if Wizarr DB is accessible
    try:
        init_admin()
    except Exception as e:
        # Don't fail startup if Wizarr DB is not ready yet
        print(f"Warning: Could not initialize admin user: {e}")
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

# ─── Public routers (no auth required) ───────────────────────────────────

# Auth router must be registered first (login endpoint is public)
app.include_router(auth.router, prefix="/api")


# ─── Protected routers (auth required) ────────────────────────────────────

# These routes require authentication via Authorization header (Bearer token)
app.include_router(books.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(comics.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(watchlist.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(downloads.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(integrations.router, prefix="/api", dependencies=[Depends(get_current_user)])
app.include_router(settings_router.router, prefix="/api", dependencies=[Depends(get_current_user)])


@app.get("/api/health")
async def health():
    return {"status": "ok", "app": _settings.app_name, "version": _settings.app_version}
