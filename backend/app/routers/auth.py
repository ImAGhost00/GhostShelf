"""Authentication endpoints for GhostShelf using Wizarr-linked accounts."""
from __future__ import annotations

import jwt
import os
import logging
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.wizarr_models import (
    authenticate_wizarr_user,
    check_wizarr_db_accessible,
    get_unique_wizarr_user_by_username,
    get_wizarr_user_by_id,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

def _load_secret_key() -> str:
    """Load JWT secret from env or a persisted file under /data."""
    env_secret = (os.getenv("SECRET_KEY") or "").strip()
    if env_secret:
        return env_secret

    secret_file = os.getenv("JWT_SECRET_FILE", "/data/ghostshelf.secret")
    try:
        if os.path.exists(secret_file):
            with open(secret_file, "r", encoding="utf-8") as handle:
                file_secret = handle.read().strip()
            if file_secret:
                return file_secret

        os.makedirs(os.path.dirname(secret_file), exist_ok=True)
        generated_secret = secrets.token_urlsafe(48)
        with open(secret_file, "w", encoding="utf-8") as handle:
            handle.write(generated_secret)
        logger.warning("SECRET_KEY not set; generated persistent JWT secret at %s", secret_file)
        return generated_secret
    except OSError as exc:
        raise RuntimeError(
            "Failed to load or create JWT secret. Set SECRET_KEY or ensure /data is writable."
        ) from exc


# JWT configuration
SECRET_KEY = _load_secret_key()
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 168  # 1 week


class LoginRequest(BaseModel):
    username: str
    password: str | None = None


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict


class CurrentUser(BaseModel):
    id: int
    username: str
    email: str | None


def decode_access_token(token: str) -> dict | None:
    """Decode and validate JWT access token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.debug("Token expired during decode")
        return None
    except jwt.InvalidTokenError as e:
        logger.debug(f"Invalid token during decode: {e}")
        return None


async def get_current_user(authorization: str | None = Header(None)) -> CurrentUser:
    """Dependency to get current authenticated user from Authorization header."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")
    
    token = authorization.replace("Bearer ", "")
    payload = decode_access_token(token)
    
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    
    user_id = payload.get("wizarr_user_id")
    if not isinstance(user_id, int):
        raise HTTPException(status_code=401, detail="Invalid token payload")

    user = get_wizarr_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found or disabled")
    
    return CurrentUser(
        id=user.id,
        username=user.username,
        email=user.email,
    )


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Login with the same username and password the user already uses upstream.
    """
    if not check_wizarr_db_accessible():
        raise HTTPException(status_code=503, detail="Wizarr database not accessible")

    username = request.username.strip()
    password = (request.password or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required")

    if password:
        user = await authenticate_wizarr_user(username, password)
    else:
        user = get_unique_wizarr_user_by_username(username)

    if not user:
        detail = "Invalid username or password" if password else "Username not found or is ambiguous"
        raise HTTPException(status_code=401, detail=detail)

    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    to_encode = {
        "wizarr_user_id": user.id,
        "sub": user.username,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    access_token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    
    return LoginResponse(
        access_token=access_token,
        token_type="bearer",
        user={
            "id": user.id,
            "username": user.username,
            "email": user.email,
        },
    )


@router.post("/logout")
async def logout():
    """
    Logout endpoint (client deletes token locally).
    
    Since we use stateless JWT tokens, logout is handled client-side.
    """
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=CurrentUser)
async def get_me(current_user: CurrentUser = Depends(get_current_user)):
    """Get current authenticated user info."""
    return current_user
