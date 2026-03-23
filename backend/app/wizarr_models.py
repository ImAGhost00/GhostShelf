"""Read-only access to Wizarr's SQLite database for GhostShelf auth."""
from __future__ import annotations

import logging
import os
from datetime import datetime

import httpx
from sqlalchemy import Boolean, Column, DateTime, Integer, String, create_engine, select
from sqlalchemy.orm import Session, declarative_base

logger = logging.getLogger(__name__)

wizarr_db_path = os.getenv("WIZARR_DB_PATH", "/opt/yams/config/wizarr/database/database.db")
wizarr_engine = create_engine(
    f"sqlite:///{wizarr_db_path}",
    connect_args={"check_same_thread": False},
    echo=False,
)
Base = declarative_base()


class WizarrUser(Base):
    __tablename__ = "user"

    id = Column(Integer, primary_key=True)
    token = Column(String, nullable=False, unique=True)
    username = Column(String, nullable=False)
    email = Column(String, nullable=True)
    code = Column(String, nullable=False)
    photo = Column(String, nullable=True)
    expires = Column(DateTime, nullable=True)
    server_id = Column(Integer, nullable=True)
    is_disabled = Column(Boolean, nullable=False, default=False)


class WizarrMediaServer(Base):
    __tablename__ = "media_server"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    server_type = Column(String, nullable=False)
    url = Column(String, nullable=False)
    api_key = Column(String, nullable=True)
    external_url = Column(String, nullable=True)
    verified = Column(Boolean, nullable=False, default=False)


def _is_active_user(user: WizarrUser) -> bool:
    if user.is_disabled:
        return False
    if user.expires and datetime.now() > user.expires:
        logger.debug("User membership expired: %s", user.username)
        return False
    return True


def get_wizarr_user_by_token(token: str) -> WizarrUser | None:
    """Fetch an active user from the Wizarr database by token."""
    try:
        with Session(wizarr_engine) as session:
            user = session.query(WizarrUser).filter_by(token=token).first()
            if user and _is_active_user(user):
                return user
            return None
    except Exception as e:
        logger.error("Error querying Wizarr database for user token: %s", type(e).__name__, exc_info=False)
        raise RuntimeError("Failed to authenticate user: database error") from e


def get_wizarr_user_by_id(user_id: int) -> WizarrUser | None:
    """Fetch an active user from the Wizarr database by id."""
    try:
        with Session(wizarr_engine) as session:
            user = session.get(WizarrUser, user_id)
            if user and _is_active_user(user):
                return user
            return None
    except Exception as e:
        logger.error("Error querying Wizarr database for user id: %s", type(e).__name__, exc_info=False)
        raise RuntimeError("Failed to authenticate user: database error") from e


def get_wizarr_users_by_username(username: str) -> list[WizarrUser]:
    """Fetch active Wizarr users matching a username."""
    try:
        with Session(wizarr_engine) as session:
            rows = session.query(WizarrUser).filter_by(username=username).all()
            return [row for row in rows if _is_active_user(row)]
    except Exception as e:
        logger.error("Error querying Wizarr database for username: %s", type(e).__name__, exc_info=False)
        raise RuntimeError("Failed to authenticate user: database error") from e


def get_media_server_by_id(server_id: int | None) -> WizarrMediaServer | None:
    if server_id is None:
        return None
    try:
        with Session(wizarr_engine) as session:
            return session.get(WizarrMediaServer, server_id)
    except Exception as e:
        logger.error("Error querying Wizarr media server: %s", type(e).__name__, exc_info=False)
        raise RuntimeError("Failed to load media server configuration") from e


async def authenticate_wizarr_user(username: str, password: str) -> WizarrUser | None:
    """Authenticate a Wizarr-linked user against their upstream media server."""
    candidates = get_wizarr_users_by_username(username.strip())
    if not candidates:
        return None

    for user in candidates:
        server = get_media_server_by_id(user.server_id)
        if not server:
            continue
        if await _authenticate_against_server(server, username.strip(), password):
            return user
    return None


async def _authenticate_against_server(server: WizarrMediaServer, username: str, password: str) -> bool:
    server_type = (server.server_type or "").lower()
    if server_type in {"jellyfin", "emby"}:
        return await _authenticate_jellyfin_like(server, username, password)
    if server_type == "audiobookshelf":
        return await _authenticate_audiobookshelf(server, username, password)
    if server_type == "komga":
        return await _authenticate_komga(server, username, password)
    if server_type == "romm":
        return await _authenticate_romm(server, username, password)

    logger.info("Unsupported Wizarr upstream server type for login: %s", server_type)
    return False


async def _authenticate_jellyfin_like(server: WizarrMediaServer, username: str, password: str) -> bool:
    headers = {
        "X-Emby-Authorization": 'MediaBrowser Client="GhostShelf", Device="GhostShelf", DeviceId="ghostshelf", Version="1.0.0"',
        "Content-Type": "application/json",
    }
    payload = {"Username": username, "Pw": password}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f"{server.url.rstrip('/')}/Users/AuthenticateByName", json=payload, headers=headers)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


async def _authenticate_audiobookshelf(server: WizarrMediaServer, username: str, password: str) -> bool:
    payload = {"username": username, "password": password}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(f"{server.url.rstrip('/')}/login", json=payload)
        return response.status_code == 200
    except httpx.HTTPError:
        return False


async def _authenticate_komga(server: WizarrMediaServer, username: str, password: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10.0, auth=(username, password)) as client:
            response = await client.get(f"{server.url.rstrip('/')}/api/v1/users/me")
        return response.status_code == 200
    except httpx.HTTPError:
        return False


async def _authenticate_romm(server: WizarrMediaServer, username: str, password: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=10.0, auth=(username, password)) as client:
            response = await client.get(f"{server.url.rstrip('/')}/api/users/me")
        return response.status_code == 200
    except httpx.HTTPError:
        return False


def check_wizarr_db_accessible() -> bool:
    """Test connection to Wizarr database."""
    try:
        with Session(wizarr_engine) as session:
            session.execute(select(1))
        return True
    except Exception as e:
        logger.warning("Wizarr database not accessible: %s", type(e).__name__)
        return False
