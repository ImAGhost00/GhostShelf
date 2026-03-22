from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, Enum as SAEnum
from sqlalchemy.sql import func
from app.database import Base
import enum


class ContentType(str, enum.Enum):
    book = "book"
    comic = "comic"
    manga = "manga"


class ItemStatus(str, enum.Enum):
    wanted = "wanted"
    found = "found"
    downloading = "downloading"
    downloaded = "downloaded"
    failed = "failed"


class WatchlistItem(Base):
    __tablename__ = "watchlist"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(512), nullable=False)
    author = Column(String(256), nullable=True)
    description = Column(Text, nullable=True)
    cover_url = Column(Text, nullable=True)
    content_type = Column(SAEnum(ContentType), nullable=False)
    status = Column(SAEnum(ItemStatus), nullable=False, default=ItemStatus.wanted)
    source = Column(String(64), nullable=True)      # e.g. "open_library", "mangadex"
    source_id = Column(String(256), nullable=True)  # external ID from source
    year = Column(String(16), nullable=True)
    genres = Column(Text, nullable=True)             # comma-separated genres
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class DownloadItem(Base):
    __tablename__ = "downloads"

    id = Column(Integer, primary_key=True, index=True)
    watchlist_id = Column(Integer, nullable=True)
    title = Column(String(512), nullable=False)
    content_type = Column(SAEnum(ContentType), nullable=False)
    download_url = Column(Text, nullable=True)
    status = Column(String(32), nullable=False, default="queued")
    destination = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class AppSetting(Base):
    __tablename__ = "settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(128), unique=True, nullable=False, index=True)
    value = Column(Text, nullable=True)
    description = Column(Text, nullable=True)
