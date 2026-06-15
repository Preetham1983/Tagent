"""Shared MS Graph token helper with automatic silent refresh.

The access token expires after ~1 hour. This module transparently refreshes
it using the stored refresh_token (valid for up to 90 days in most tenants)
so users do not need to re-run trigger_login.py every hour.
"""
from __future__ import annotations

import json
import os
import time

import httpx

def _cache_file() -> str:
    cache_dir = os.environ.get(
        "TOKEN_CACHE_DIR",
        os.path.join(os.path.expanduser("~"), ".tagent"),
    )
    return os.path.join(cache_dir, "ms_graph_token_cache.json")


async def get_graph_token() -> str | None:
    """Return a valid MS Graph access token, auto-refreshing if the current one is expired."""
    cache_file = _cache_file()
    try:
        with open(cache_file, "r", encoding="utf-8") as f:
            cached = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None

    access_token = cached.get("access_token", "")
    expiry = float(cached.get("token_expiry", 0))

    # Still valid with a 5-minute safety buffer
    if access_token and time.time() < expiry - 300:
        return access_token

    # Access token expired — attempt a silent refresh
    refresh_token = cached.get("refresh_token", "")
    tenant_id = cached.get("tenant_id") or os.environ.get("MS_TENANT_ID", "")
    client_id = cached.get("client_id") or os.environ.get("MS_CLIENT_ID", "")
    # Never cache the client secret — read from environment at runtime
    client_secret = os.environ.get("MS_CLIENT_SECRET", "")
    scopes = cached.get("scopes", "User.Read offline_access")

    if not (refresh_token and tenant_id and client_id):
        return None  # No way to refresh — user must re-login

    try:
        data: dict[str, str] = {
            "grant_type": "refresh_token",
            "client_id": client_id,
            "refresh_token": refresh_token,
            "scope": scopes,
        }
        if client_secret:
            data["client_secret"] = client_secret

        async with httpx.AsyncClient(timeout=15) as http:
            r = await http.post(
                f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
                data=data,
            )

        if r.status_code == 200:
            token_data = r.json()
            cached["access_token"] = token_data["access_token"]
            # Refresh tokens may rotate on each use — keep the new one
            if "refresh_token" in token_data:
                cached["refresh_token"] = token_data["refresh_token"]
            cached["token_expiry"] = time.time() + token_data.get("expires_in", 3600)
            cached["updated_at"] = int(time.time())

            cache_file = _cache_file()
            os.makedirs(os.path.dirname(cache_file), exist_ok=True)
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cached, f, indent=2)

            return cached["access_token"]
    except Exception:
        pass

    return None
