from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.settings_store import get_setting


async def check_connection(db: AsyncSession) -> dict[str, Any]:
    base_url = (await get_setting(db, "qbittorrent_url", "")).rstrip("/")
    username = await get_setting(db, "qbittorrent_username", "")
    password = await get_setting(db, "qbittorrent_password", "")

    if not base_url:
        return {"connected": False, "error": "qBittorrent URL not configured"}

    try:
        async with httpx.AsyncClient(timeout=12, follow_redirects=True) as client:
            # If credentials are set, try authenticated API login first.
            if username and password:
                login = await client.post(
                    f"{base_url}/api/v2/auth/login",
                    data={"username": username, "password": password},
                )
                if login.status_code >= 400:
                    return {"connected": False, "error": f"HTTP {login.status_code}"}
                if "ok" not in login.text.lower():
                    return {"connected": False, "error": "Login failed"}

            version_resp = await client.get(f"{base_url}/api/v2/app/version")
            if version_resp.status_code == 200:
                return {
                    "connected": True,
                    "version": version_resp.text.strip(),
                    "authenticated": bool(username and password),
                }
            return {"connected": False, "error": f"HTTP {version_resp.status_code}"}
    except Exception as exc:
        return {"connected": False, "error": str(exc)}
