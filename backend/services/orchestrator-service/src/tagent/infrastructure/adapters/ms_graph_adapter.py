"""Microsoft Graph API adapter — real HTTP calls via delegated or client-credentials flow."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

import httpx

_GRAPH = "https://graph.microsoft.com/v1.0"
_LOGIN = "https://login.microsoftonline.com"


class MSGraphAdapter:
    """OAuth2 adapter for Microsoft Graph API — supports delegated (user) and app-only flows."""

    def __init__(self, tenant_id: str, client_id: str, client_secret: str) -> None:
        self._tenant_id = tenant_id
        self._client_id = client_id
        self._client_secret = client_secret
        self._token: str | None = None
        self._token_expiry: float = 0.0
        self._refresh_token: str | None = None
        # Keep delegated auth opt-in to avoid repeated interactive prompts in restricted tenants.
        self._use_delegated: bool = os.getenv("MS_GRAPH_USE_DELEGATED", "false").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        self._allow_interactive_auth: bool = os.getenv("MS_GRAPH_ALLOW_INTERACTIVE_AUTH", "false").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        # Default to calendar-only delegated scopes to avoid admin-consent-heavy permissions.
        self._enable_transcripts: bool = os.getenv("MS_GRAPH_ENABLE_TRANSCRIPTS", "false").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    def _delegated_scopes(self) -> str:
        base_scopes = ["User.Read", "Calendars.Read", "offline_access"]
        if self._enable_transcripts:
            base_scopes.append("OnlineMeetings.Read")
        return " ".join(base_scopes)

    def _token_cache_file(self) -> str:
        return os.getenv(
            "MS_GRAPH_TOKEN_CACHE_FILE",
            os.path.join(os.path.expanduser("~"), ".tagent", "ms_graph_token_cache.json"),
        )

    def _load_cached_tokens(self) -> None:
        cache_file = self._token_cache_file()
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
        except Exception:
            return

        if cached.get("tenant_id") != self._tenant_id or cached.get("client_id") != self._client_id:
            return

        self._token = cached.get("access_token")
        self._refresh_token = cached.get("refresh_token")
        self._token_expiry = float(cached.get("token_expiry", 0.0))

    def _save_cached_tokens(self) -> None:
        cache_file = self._token_cache_file()
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        payload = {
            "tenant_id": self._tenant_id,
            "client_id": self._client_id,
            "scopes": self._delegated_scopes(),
            "access_token": self._token,
            "refresh_token": self._refresh_token,
            "token_expiry": self._token_expiry,
            "updated_at": int(time.time()),
        }
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(payload, f)

    # ── Auth ─────────────────────────────────────────────────────────────────

    async def _get_token(self) -> str:
        if not self._token and not self._refresh_token:
            self._load_cached_tokens()

        if self._token and time.time() < self._token_expiry - 60:
            return self._token

        # Try refresh token first (from prior delegated login)
        if self._refresh_token:
            try:
                return await self._refresh_delegated_token()
            except Exception:
                self._refresh_token = None

        # If delegated mode is enabled, try refresh token first and only do device-code when allowed.
        if self._use_delegated and self._allow_interactive_auth:
            try:
                return await self._device_code_flow()
            except Exception:
                pass

        # Fallback to client credentials
        return await self._client_credentials_flow()

    async def _client_credentials_flow(self) -> str:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{_LOGIN}/{self._tenant_id}/oauth2/v2.0/token",
                data={
                    "grant_type": "client_credentials",
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "scope": "https://graph.microsoft.com/.default",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        self._token = data["access_token"]
        self._token_expiry = time.time() + data.get("expires_in", 3600)
        self._save_cached_tokens()
        return self._token  # type: ignore[return-value]

    async def _device_code_flow(self) -> str:
        """Interactive device-code flow — prints a URL + code for user to sign in."""
        import sys

        scopes = self._delegated_scopes()
        async with httpx.AsyncClient(timeout=30) as client:
            # Step 1: Request device code
            resp = await client.post(
                f"{_LOGIN}/{self._tenant_id}/oauth2/v2.0/devicecode",
                data={
                    "client_id": self._client_id,
                    "scope": scopes,
                },
            )
            resp.raise_for_status()
            dc = resp.json()

            print(f"\n{'='*60}", file=sys.stderr)
            print(f"  SIGN IN REQUIRED", file=sys.stderr)
            print(f"  {dc['message']}", file=sys.stderr)
            print(f"{'='*60}\n", file=sys.stderr, flush=True)

            # Step 2: Poll for user to complete sign-in
            interval = dc.get("interval", 5)
            device_code = dc["device_code"]
            deadline = time.time() + dc.get("expires_in", 900)

            while time.time() < deadline:
                import asyncio
                await asyncio.sleep(interval)
                poll_resp = await client.post(
                    f"{_LOGIN}/{self._tenant_id}/oauth2/v2.0/token",
                    data={
                        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                        "client_id": self._client_id,
                        "client_secret": self._client_secret,
                        "device_code": device_code,
                    },
                )
                poll_data = poll_resp.json()
                if "access_token" in poll_data:
                    self._token = poll_data["access_token"]
                    self._refresh_token = poll_data.get("refresh_token")
                    self._token_expiry = time.time() + poll_data.get("expires_in", 3600)
                    self._save_cached_tokens()
                    print("  ✓ Sign-in successful!\n", file=sys.stderr, flush=True)
                    return self._token  # type: ignore[return-value]
                if poll_data.get("error") == "authorization_pending":
                    continue
                if poll_data.get("error") in ("authorization_declined", "expired_token", "bad_verification_code"):
                    break

        raise RuntimeError("Device code flow timed out or was declined")

    async def _refresh_delegated_token(self) -> str:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{_LOGIN}/{self._tenant_id}/oauth2/v2.0/token",
                data={
                    "grant_type": "refresh_token",
                    "client_id": self._client_id,
                    "refresh_token": self._refresh_token,
                    "scope": self._delegated_scopes(),
                },
            )
            resp.raise_for_status()
            data = resp.json()
        self._token = data["access_token"]
        self._refresh_token = data.get("refresh_token", self._refresh_token)
        self._token_expiry = time.time() + data.get("expires_in", 3600)
        self._save_cached_tokens()
        return self._token  # type: ignore[return-value]

    async def _get(self, path: str, params: dict | None = None) -> dict:
        token = await self._get_token()
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{_GRAPH}{path}",
                headers={"Authorization": f"Bearer {token}"},
                params=params or {},
            )
            resp.raise_for_status()
            return resp.json()

    # ── Users ─────────────────────────────────────────────────────────────────

    async def get_me(self) -> dict:
        """Get the signed-in user's profile (delegated) or first user (app-only)."""
        try:
            return await self._get("/me", params={"$select": "id,displayName,mail,userPrincipalName,jobTitle,department"})
        except Exception:
            # Fallback for app-only: list users
            data = await self._get("/users", params={"$top": "1", "$select": "id,displayName,mail,userPrincipalName"})
            users = data.get("value", [])
            return users[0] if users else {}

    async def get_user_by_upn(self, upn: str) -> dict:
        """Look up a user by their UPN (email)."""
        return await self._get(f"/users/{upn}", params={"$select": "id,displayName,mail,userPrincipalName,jobTitle,department"})

    async def list_users(self, top: int = 20) -> list[dict]:
        """List users in the tenant."""
        data = await self._get("/users", params={"$top": str(top), "$select": "id,displayName,mail,userPrincipalName,jobTitle,department"})
        return data.get("value", [])

    # ── Calendar ──────────────────────────────────────────────────────────────

    async def get_today_meetings(self, user_id: str) -> list[dict]:
        """Get today's calendar events for a user."""
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat().replace("+00:00", "Z")
        end = now.replace(hour=23, minute=59, second=59, microsecond=0).isoformat().replace("+00:00", "Z")
        data = await self._get(
            f"/users/{user_id}/calendarView",
            params={
                "startDateTime": start,
                "endDateTime": end,
                "$select": "id,subject,start,end,attendees,onlineMeeting,isOnlineMeeting",
                "$orderby": "start/dateTime",
                "$top": "20",
            },
        )
        return data.get("value", [])

    # ── Online Meetings & Transcripts ─────────────────────────────────────────

    async def get_online_meetings(self, user_id: str) -> list[dict]:
        """List online meetings for a user."""
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        data = await self._get(
            f"/users/{user_id}/onlineMeetings",
            params={
                "$filter": f"startDateTime ge {start}",
                "$select": "id,subject,startDateTime,endDateTime,participants",
                "$top": "10",
            },
        )
        return data.get("value", [])

    async def get_transcripts_for_meeting(self, user_id: str, meeting_id: str) -> list[dict]:
        """List available transcripts for an online meeting."""
        data = await self._get(f"/users/{user_id}/onlineMeetings/{meeting_id}/transcripts")
        return data.get("value", [])

    async def get_transcript_content(self, user_id: str, meeting_id: str, transcript_id: str) -> str:
        """Fetch the text content of a transcript."""
        token = await self._get_token()
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(
                f"{_GRAPH}/users/{user_id}/onlineMeetings/{meeting_id}/transcripts/{transcript_id}/content",
                headers={"Authorization": f"Bearer {token}", "Accept": "text/vtt"},
            )
            if resp.status_code == 200:
                return resp.text
        return ""

    # ── Convenience: full standup fetch ───────────────────────────────────────

    async def get_standup_context(self, user_id: str) -> dict:
        """
        Fetches today's meetings and, optionally, transcripts.
        Uses /me/calendarView for delegated tokens, /users/{id}/calendarView for app-only.
        """
        # Try /me first (delegated), fall back to /users/{id}
        now = datetime.now(timezone.utc)
        start = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        end = now.replace(hour=23, minute=59, second=59, microsecond=0).isoformat()
        params = {
            "startDateTime": start,
            "endDateTime": end,
            "$select": "id,subject,start,end,attendees,onlineMeeting,isOnlineMeeting",
            "$orderby": "start/dateTime",
            "$top": "20",
        }
        data: dict = {"value": []}
        calendar_error = ""
        try:
            data = await self._get("/me/calendarView", params=params)
        except Exception as e:
            calendar_error = str(e)
            try:
                data = await self._get(f"/users/{user_id}/calendarView", params=params)
            except Exception as e2:
                return {
                    "meetings": [],
                    "transcript": "",
                    "note": (
                        "Calendar access is unavailable right now. "
                        f"Primary error: {calendar_error[:120]}; fallback error: {str(e2)[:120]}"
                    ),
                }

        meetings = data.get("value", [])
        standup_meetings = [
            m for m in meetings
            if any(kw in (m.get("subject") or "").lower() for kw in ("standup", "stand-up", "stand up", "daily", "scrum", "sync"))
        ] or meetings  # fall back to all today's meetings if none match

        if not self._enable_transcripts:
            return {
                "meetings": standup_meetings,
                "transcript": "",
                "note": "Transcript fetch is disabled in fallback mode (calendar-only).",
            }

        transcript_text = ""
        for meeting in standup_meetings[:3]:
            online_meeting = meeting.get("onlineMeeting") or {}
            join_url = online_meeting.get("joinUrl", "")
            if not join_url:
                continue
            try:
                transcripts = await self.get_transcripts_for_meeting(user_id, join_url)
                for tr in transcripts[:1]:
                    content = await self.get_transcript_content(user_id, join_url, tr["id"])
                    if content:
                        transcript_text += f"\n\n[{meeting.get('subject')}]\n{content}"
            except Exception:
                pass

        return {
            "meetings": standup_meetings,
            "transcript": transcript_text.strip(),
            "note": "",
        }


_default_graph: MSGraphAdapter | None = None


def get_graph_adapter() -> MSGraphAdapter:
    """Return a singleton MSGraphAdapter built from Settings."""
    global _default_graph
    if _default_graph is None:
        from tagent.infrastructure.config.settings import Settings
        s = Settings()
        _default_graph = MSGraphAdapter(
            tenant_id=s.ms_tenant_id,
            client_id=s.ms_client_id,
            client_secret=s.ms_client_secret,
        )
    return _default_graph

