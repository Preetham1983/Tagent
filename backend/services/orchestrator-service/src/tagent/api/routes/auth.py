"""Microsoft Teams device-code auth endpoints."""

from __future__ import annotations

import json
import os
import time

import httpx
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/auth/teams")

_CACHE_DIR = os.environ.get("TOKEN_CACHE_DIR", os.path.join(os.path.expanduser("~"), ".tagent"))
_MS_TOKEN_CACHE = os.path.join(_CACHE_DIR, "ms_graph_token_cache.json")
_MS_SCOPES = "User.Read Chat.ReadWrite Chat.Read ChannelMessage.Send offline_access"


@router.post("/start")
async def start_teams_auth() -> dict:
    """Begin Microsoft device-code flow. Returns user_code + verification_uri for the UI."""
    from tagent.infrastructure.config.settings import Settings

    s = Settings()
    if not s.ms_client_id or not s.ms_tenant_id:
        raise HTTPException(
            status_code=400,
            detail="MS_CLIENT_ID and MS_TENANT_ID must be set in the orchestrator .env before signing in.",
        )

    async with httpx.AsyncClient(timeout=15) as http:
        r = await http.post(
            f"https://login.microsoftonline.com/{s.ms_tenant_id}/oauth2/v2.0/devicecode",
            data={"client_id": s.ms_client_id, "scope": _MS_SCOPES},
        )

    if r.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Azure AD error: {r.text[:300]}")

    data = r.json()
    return {
        "user_code": data["user_code"],
        "verification_uri": data["verification_uri"],
        "expires_in": data.get("expires_in", 900),
        "interval": data.get("interval", 5),
        "device_code": data["device_code"],
    }


@router.post("/poll")
async def poll_teams_auth(req: Request) -> dict:
    """Poll Azure AD to check if the user completed the device-code sign-in."""
    from tagent.infrastructure.config.settings import Settings

    s = Settings()
    body = await req.json()
    device_code = (body.get("device_code") or "").strip()
    if not device_code:
        raise HTTPException(status_code=400, detail="device_code is required")

    async with httpx.AsyncClient(timeout=15) as http:
        r = await http.post(
            f"https://login.microsoftonline.com/{s.ms_tenant_id}/oauth2/v2.0/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_code,
                "client_id": s.ms_client_id,
            },
        )

    data = r.json()
    error = data.get("error", "")

    if error in ("authorization_pending", "slow_down"):
        return {"status": "pending"}
    if error:
        return {"status": "error", "message": data.get("error_description", error)[:200]}

    if "access_token" in data:
        cache = {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token", ""),
            "token_expiry": time.time() + data.get("expires_in", 3600),
            "tenant_id": s.ms_tenant_id,
            "client_id": s.ms_client_id,
            "scopes": data.get("scope", _MS_SCOPES),
            "updated_at": int(time.time()),
        }
        os.makedirs(os.path.dirname(_MS_TOKEN_CACHE), exist_ok=True)
        with open(_MS_TOKEN_CACHE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
        import base64
        token_b64 = base64.b64encode(json.dumps(cache).encode()).decode()
        return {
            "status": "ok",
            "message": "Microsoft Teams connected successfully!",
            "token_data": token_b64,
        }

    return {"status": "error", "message": "Unexpected response from Azure AD"}
