"""Direct Google Calendar REST API adapter.

Uses tokens saved by `npx @cocal/google-calendar-mcp auth` — no npx spawning
at call-time. Automatically refreshes expired access tokens.

Token file:  ~/.config/google-calendar-mcp/tokens.json
Credentials: path set via GCAL_MCP_OAUTH_CREDENTIALS (or Settings panel)

Run once to authenticate:
  $env:GOOGLE_OAUTH_CREDENTIALS='C:\\path\\to\\tagent.json'
  npx @cocal/google-calendar-mcp auth
     This stores tokens in ~/.config/google-calendar-mcp/ (auto-refreshed).
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import httpx


_TOKEN_FILE = Path.home() / ".config" / "google-calendar-mcp" / "tokens.json"
_CALENDAR_BASE = "https://www.googleapis.com/calendar/v3"
_TOKEN_URL = "https://oauth2.googleapis.com/token"


class GoogleCalendarMCPAdapter:
    """Calls Google Calendar REST API directly using stored OAuth tokens."""

    def __init__(self, oauth_credentials: str = "", timeout_seconds: int = 30) -> None:
        self._oauth_credentials = (oauth_credentials or "").strip()
        self._timeout_seconds = timeout_seconds

    def enabled(self) -> bool:
        return _TOKEN_FILE.exists()

    # ── Token helpers ─────────────────────────────────────────────────────────

    def _load_tokens(self) -> dict | None:
        """Return the first valid account token dict from the token file."""
        try:
            data = json.loads(_TOKEN_FILE.read_text(encoding="utf-8"))
            for tokens in data.values():
                if isinstance(tokens, dict) and tokens.get("refresh_token"):
                    return tokens
        except Exception:
            pass
        return None

    def _load_client_creds(self) -> tuple[str, str]:
        """Load client_id / client_secret — env vars take priority, then file fallback."""
        # 1. Direct env vars (set via .env)
        cid = os.environ.get("GOOGLE_CLIENT_ID", "")
        csec = os.environ.get("GOOGLE_CLIENT_SECRET", "")
        if cid and csec:
            return cid, csec

        # 2. OAuth credentials file (path from settings or well-known locations)
        candidates = [
            self._oauth_credentials,
            os.environ.get("GOOGLE_OAUTH_CREDENTIALS", ""),
            str(Path.home() / "Downloads" / "tagent.json"),
            str(Path.home() / ".tagent" / "gcp-oauth.keys.json"),
            str(Path.home() / ".config" / "google-calendar-mcp" / "gcp-oauth.keys.json"),
        ]
        for path in candidates:
            if not path:
                continue
            try:
                raw = json.loads(Path(path).read_text(encoding="utf-8"))
                installed = raw.get("installed") or raw.get("web") or {}
                cid = installed.get("client_id", "")
                csec = installed.get("client_secret", "")
                if cid and csec:
                    return cid, csec
            except Exception:
                continue
        return "", ""

    def _save_refreshed_token(self, refresh_token: str, new_data: dict) -> None:
        """Persist a refreshed access token back to the token file."""
        try:
            data = json.loads(_TOKEN_FILE.read_text(encoding="utf-8"))
            for val in data.values():
                if isinstance(val, dict) and val.get("refresh_token") == refresh_token:
                    val["access_token"] = new_data["access_token"]
                    val["expiry_date"] = int(time.time() * 1000) + new_data.get("expires_in", 3600) * 1000
                    break
            _TOKEN_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception:
            pass

    async def _get_access_token(self) -> str | None:
        tokens = self._load_tokens()
        if not tokens:
            return None

        # expiry_date is in milliseconds; keep a 2-minute safety buffer
        expiry_ms = tokens.get("expiry_date", 0)
        if expiry_ms > time.time() * 1000 + 120_000:
            return tokens["access_token"]

        # Attempt refresh
        client_id, client_secret = self._load_client_creds()
        refresh_token = tokens.get("refresh_token", "")
        if not (client_id and client_secret and refresh_token):
            return tokens.get("access_token")

        try:
            async with httpx.AsyncClient(timeout=10) as http:
                r = await http.post(_TOKEN_URL, data={
                    "grant_type": "refresh_token",
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "refresh_token": refresh_token,
                })
                if r.status_code == 200:
                    new_data = r.json()
                    self._save_refreshed_token(refresh_token, new_data)
                    return new_data["access_token"]
        except Exception:
            pass
        return tokens.get("access_token")

    # ── Public interface ──────────────────────────────────────────────────────

    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        if not _TOKEN_FILE.exists():
            return {
                "status": "not_configured",
                "message": (
                    "Google Calendar not authenticated. Run once in a terminal:\n"
                    "  $env:GOOGLE_OAUTH_CREDENTIALS='C:\\path\\to\\tagent.json'\n"
                    "  npx @cocal/google-calendar-mcp auth"
                ),
            }

        token = await self._get_access_token()
        if not token:
            return {"status": "not_configured", "message": "Could not obtain a Google access token."}

        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as http:
                if tool_name in ("list-events", "list_google_calendar_events"):
                    return await self._list_events(http, headers, arguments)
                elif tool_name in ("create-event", "create_google_calendar_event"):
                    return await self._create_event(http, headers, arguments)
                elif tool_name in ("search-events", "search_google_calendar_events"):
                    return await self._search_events(http, headers, arguments)
                else:
                    return {"status": "error", "message": f"Unknown tool: {tool_name}"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:300]}

    # ── API calls ─────────────────────────────────────────────────────────────

    async def _list_events(self, http: httpx.AsyncClient, headers: dict, args: dict) -> dict:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        time_min = now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        r = await http.get(
            f"{_CALENDAR_BASE}/calendars/primary/events",
            headers=headers,
            params={
                "timeMin": time_min,
                "maxResults": 20,
                "singleEvents": "true",
                "orderBy": "startTime",
            },
        )
        if r.status_code != 200:
            return {"status": "error", "message": r.text[:300]}
        items = r.json().get("items", [])
        events = [
            {
                "id": e.get("id"),
                "title": e.get("summary", "(no title)"),
                "start": (e.get("start") or {}).get("dateTime", (e.get("start") or {}).get("date", "")),
                "end": (e.get("end") or {}).get("dateTime", ""),
                "location": e.get("location", ""),
                "meet_link": e.get("hangoutLink", ""),
                "attendees": [a.get("email", "") for a in e.get("attendees", [])],
            }
            for e in items
        ]
        return {"status": "ok", "events": events, "total": len(events)}

    async def _create_event(self, http: httpx.AsyncClient, headers: dict, args: dict) -> dict:
        from datetime import datetime, timedelta

        start_str: str = args.get("start") or args.get("startTime", "")
        end_str: str = args.get("end") or args.get("endTime", "")

        if not end_str and start_str:
            try:
                end_str = (datetime.fromisoformat(start_str) + timedelta(hours=1)).isoformat()
            except Exception:
                end_str = start_str

        tz = "Asia/Kolkata"
        payload: dict[str, Any] = {
            "summary": args.get("summary") or args.get("title", "Meeting"),
            "start": {"dateTime": start_str, "timeZone": tz},
            "end":   {"dateTime": end_str,   "timeZone": tz},
        }
        if args.get("description"):
            payload["description"] = args["description"]

        attendees = args.get("attendees") or []
        if isinstance(attendees, list) and attendees:
            payload["attendees"] = [
                {"email": a} if isinstance(a, str) else a for a in attendees
            ]

        # Always request a Google Meet link
        payload["conferenceData"] = {
            "createRequest": {"requestId": f"tagent-{int(time.time())}"}
        }

        r = await http.post(
            f"{_CALENDAR_BASE}/calendars/primary/events",
            headers=headers,
            json=payload,
            params={"conferenceDataVersion": "1"},
        )
        if r.status_code not in (200, 201):
            return {"status": "error", "message": r.text[:300]}

        data = r.json()
        meet_link = data.get("hangoutLink", "")
        if not meet_link:
            for ep in data.get("conferenceData", {}).get("entryPoints", []):
                if ep.get("entryPointType") == "video":
                    meet_link = ep.get("uri", "")
                    break

        return {
            "status": "ok",
            "id": data.get("id"),
            "title": data.get("summary"),
            "start": (data.get("start") or {}).get("dateTime", ""),
            "end":   (data.get("end") or {}).get("dateTime", ""),
            "url": data.get("htmlLink", ""),
            "meet_link": meet_link,
            "attendees": [a.get("email") for a in data.get("attendees", [])],
        }

    async def _search_events(self, http: httpx.AsyncClient, headers: dict, args: dict) -> dict:
        from datetime import datetime, timezone
        now = datetime.now(timezone.utc)
        r = await http.get(
            f"{_CALENDAR_BASE}/calendars/primary/events",
            headers=headers,
            params={
                "q": args.get("query", ""),
                "timeMin": now.replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),
                "maxResults": 10,
                "singleEvents": "true",
            },
        )
        if r.status_code != 200:
            return {"status": "error", "message": r.text[:300]}
        items = r.json().get("items", [])
        return {"status": "ok", "events": items, "total": len(items)}


def get_google_calendar_mcp_adapter() -> GoogleCalendarMCPAdapter:
    from tagent.infrastructure.config.settings import Settings

    s = Settings()
    return GoogleCalendarMCPAdapter(
        oauth_credentials=s.gcal_mcp_oauth_credentials,
        timeout_seconds=s.gcal_mcp_timeout_seconds,
    )
