"""Google Calendar tools for MCP — real Google Calendar API integration."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import httpx
from mcp.server import Server


def _get_gcal_config() -> dict:
    return {
        "client_id": os.environ.get("GOOGLE_CLIENT_ID", ""),
        "client_secret": os.environ.get("GOOGLE_CLIENT_SECRET", ""),
        "refresh_token": os.environ.get("GOOGLE_REFRESH_TOKEN", ""),
        "calendar_id": os.environ.get("GOOGLE_CALENDAR_ID", "primary"),
    }


async def _get_access_token(config: dict) -> str | None:
    """Exchange OAuth2 refresh token for a short-lived access token."""
    if not all([config["client_id"], config["client_secret"], config["refresh_token"]]):
        return None
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            r = await http.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": config["client_id"],
                    "client_secret": config["client_secret"],
                    "refresh_token": config["refresh_token"],
                    "grant_type": "refresh_token",
                },
            )
            if r.status_code == 200:
                return r.json().get("access_token")
    except Exception:
        pass
    return None


def register_google_calendar_tools(server: Server) -> None:
    """Register Google Calendar tools."""

    @server.tool()
    async def list_google_calendar_events(date: str = "", days: int = 1) -> dict:
        """List Google Calendar events for today or a specific date. date format: YYYY-MM-DD."""
        config = _get_gcal_config()
        token = await _get_access_token(config)
        if not token:
            return {
                "status": "not_configured",
                "message": (
                    "Google Calendar credentials not configured. "
                    "Set GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, and GOOGLE_REFRESH_TOKEN in settings."
                ),
            }

        if date:
            try:
                start_dt = datetime.fromisoformat(date).replace(tzinfo=timezone.utc)
            except ValueError:
                start_dt = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            start_dt = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)

        end_dt = start_dt + timedelta(days=max(1, days))

        try:
            async with httpx.AsyncClient(timeout=15) as http:
                r = await http.get(
                    f"https://www.googleapis.com/calendar/v3/calendars/{config['calendar_id']}/events",
                    headers={"Authorization": f"Bearer {token}"},
                    params={
                        "timeMin": start_dt.isoformat(),
                        "timeMax": end_dt.isoformat(),
                        "singleEvents": "true",
                        "orderBy": "startTime",
                        "maxResults": 20,
                    },
                )
                if r.status_code == 200:
                    events = []
                    for event in r.json().get("items", []):
                        start = event.get("start", {})
                        end = event.get("end", {})
                        events.append({
                            "id": event["id"],
                            "title": event.get("summary", "No title"),
                            "start": start.get("dateTime", start.get("date", "")),
                            "end": end.get("dateTime", end.get("date", "")),
                            "location": event.get("location", ""),
                            "attendees": [
                                a.get("email", "") for a in event.get("attendees", [])
                            ],
                            "meet_link": event.get("hangoutLink", ""),
                            "description": (event.get("description") or "")[:200],
                        })
                    return {
                        "status": "ok",
                        "date": start_dt.date().isoformat(),
                        "total": len(events),
                        "events": events,
                    }
                return {"status": "error", "message": r.text[:300]}
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:200]}

    @server.tool()
    async def create_google_calendar_event(
        title: str,
        start: str,
        end: str = "",
        description: str = "",
        attendees: str = "",
    ) -> dict:
        """Create a Google Calendar event. start format: 2024-01-15T10:00:00"""
        config = _get_gcal_config()
        token = await _get_access_token(config)
        if not token:
            return {
                "status": "not_configured",
                "message": "Google Calendar credentials not configured.",
            }

        if not end:
            try:
                end = (datetime.fromisoformat(start) + timedelta(hours=1)).isoformat()
            except ValueError:
                end = start

        payload: dict = {
            "summary": title,
            "start": {"dateTime": start, "timeZone": "UTC"},
            "end": {"dateTime": end, "timeZone": "UTC"},
        }
        if description:
            payload["description"] = description
        if attendees:
            payload["attendees"] = [{"email": e.strip()} for e in attendees.split(",")]

        try:
            async with httpx.AsyncClient(timeout=15) as http:
                r = await http.post(
                    f"https://www.googleapis.com/calendar/v3/calendars/{config['calendar_id']}/events",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if r.status_code == 200:
                    data = r.json()
                    return {
                        "status": "ok",
                        "id": data["id"],
                        "title": data.get("summary", ""),
                        "url": data.get("htmlLink", ""),
                    }
                return {"status": "error", "message": r.text[:300]}
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:200]}
