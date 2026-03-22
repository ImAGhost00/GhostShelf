from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import os


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "GhostShelf"
    app_version: str = "1.0.0"
    debug: bool = False

    # Database
    database_url: str = "sqlite+aiosqlite:///./ghostshelf.db"

    # CORS origins (comma-separated)
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # Google Books API (optional, unauthenticated works but is rate-limited)
    google_books_api_key: str = ""

    # ComicVine API key (required for comics search via ComicVine)
    comicvine_api_key: str = ""

    # CWA (Calibre-Web Automated) settings
    cwa_url: str = ""
    cwa_ingest_folder: str = ""

    # Folder used for comics/manga files that Komga scans
    komga_ingest_folder: str = ""

    # Komga settings
    komga_url: str = ""
    komga_username: str = ""
    komga_password: str = ""

    # Prowlarr settings
    prowlarr_url: str = ""
    prowlarr_api_key: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache
def get_settings() -> Settings:
    return Settings()
