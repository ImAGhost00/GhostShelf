"""
Authentication endpoints for GhostShelf.

Uses Wizarr's user database with token-based authentication.
"""
from __future__ import annotations

import jwt
import os
import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.wizarr_models import get_wizarr_user_by_token, check_wizarr_db_accessible

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

# JWT configuration
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError(
        "CRITICAL: SECRET_KEY environment variable must be set before startup. "
        "Generate a strong random string (32+ bytes) and set it via environment variables."
    )
ALGORITHM = "HS256"
TOKEN_EXPIRE_HOURS = 168  # 1 week


class LoginRequest(BaseModel):
    wizarr_token: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict


class CurrentUser(BaseModel):
    id: int
    username: str
    email: str | None
    token: str  # Wizarr token


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
    
    user = get_wizarr_user_by_token(payload.get("wizarr_token"))
    if not user:
        raise HTTPException(status_code=401, detail="User not found or disabled")
    
    return CurrentUser(
        id=user.id,
        username=user.username,
        email=user.email,
        token=user.token,
    )


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Login with a Wizarr token.
    
    Exchanges a Wizarr user token for a GhostShelf JWT access token.
    """
    # Verify Wizarr database is accessible
    if not check_wizarr_db_accessible():
        raise HTTPException(status_code=503, detail="Wizarr database not accessible")
    
    # Look up user in Wizarr database
    user = get_wizarr_user_by_token(request.wizarr_token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid Wizarr token or user disabled")
    
    # Create JWT access token
    expire = datetime.now(timezone.utc) + timedelta(hours=TOKEN_EXPIRE_HOURS)
    to_encode = {
        "wizarr_token": user.token,
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
