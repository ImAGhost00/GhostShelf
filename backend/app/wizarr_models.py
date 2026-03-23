"""
Read-only connection to Wizarr's shared SQLite database.

Allows GhostShelf to authenticate users against the same user database
that Komga/Jellyfin/etc. use via Wizarr.

Database location is configurable via WIZARR_DB_PATH env var.
"""
from __future__ import annotations

import os
import logging
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime, select
from sqlalchemy.orm import declarative_base, Session
from datetime import datetime

logger = logging.getLogger(__name__)

class WizarrUser(Base):
    """
    Read-only mirror of Wizarr's User model.
    
    Wizarr stores user tokens and metadata. Each user has:
    - token: Unique identifier (often used for API/session auth)
    - username: Display name
    - email: User email
    - code: Invitation code used
    - is_disabled: Whether account is disabled
    - expires: When membership expires (if time-limited)
    """
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


def get_wizarr_user_by_token(token: str) -> WizarrUser | None:
    """Fetch a user from Wizarr database by token."""
    try:
        with Session(wizarr_engine) as session:
            user = session.query(WizarrUser).filter_by(token=token).first()
            if user and not user.is_disabled:
                # Check expiry if set
                if user.expires and datetime.now() > user.expires:
                    logger.debug(f"User membership expired: {user.username}")
                    return None
                return user
            return None
    except Exception as e:
        logger.error(f"Error querying Wizarr database for user token: {type(e).__name__}", exc_info=False)
        raise RuntimeError(f"Failed to authenticate user: database error") from e


def check_wizarr_db_accessible() -> bool:
    """Test connection to Wizarr database."""
    try:
        with Session(wizarr_engine) as session:
            session.execute(select(1))
        return True
    except Exception as e:
        logger.warning(f"Wizarr database not accessible: {type(e).__name__}")
        return False
