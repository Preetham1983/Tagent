"""Calendar tools for MCP — real MS Graph integration."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone

import httpx
from mcp.server import Server
from tagent.mcp.tools._token import get_graph_token as _get_graph_token


def register_calendar_tools(server: Server) -> None:
    """Register calendar tools (find slots, schedule, transcript)."""

    @server.tool()
    async def find_free_slots(user_ids: list[str], date: str, duration_minutes: int = 30) -> dict:
        """Find available meeting slots for a group of users on a given date."""
        token = await _get_graph_token()
        if not token:
            return {"status": "not_connected", "message": "No valid user session. Please sign in first."}

        # Use MS Graph findMeetingTimes API
        try:
            attendees = [
                {"type": "required", "emailAddress": {"address": uid}} for uid in user_ids
            ]
            payload = {
                "attendees": attendees,
                "timeConstraint": {
                    "timeslots": [
                        {
                            "start": {"dateTime": f"{date}T08:00:00", "timeZone": "UTC"},
                            "end": {"dateTime": f"{date}T18:00:00", "timeZone": "UTC"},
                        }
                    ]
                },
                "meetingDuration": f"PT{duration_minutes}M",
                "maxCandidates": 5,
            }
            async with httpx.AsyncClient(timeout=15) as http:
                r = await http.post(
                    "https://graph.microsoft.com/v1.0/me/findMeetingTimes",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json=payload,
                )
                if r.status_code == 200:
                    data = r.json()
                    suggestions = data.get("meetingTimeSuggestions", [])
                    slots = []
                    for s in suggestions[:5]:
                        ts = s.get("meetingTimeSlot", {})
                        slots.append({
                            "start": ts.get("start", {}).get("dateTime", ""),
                            "end": ts.get("end", {}).get("dateTime", ""),
                            "confidence": s.get("confidence", ""),
                        })
                    return {"status": "ok", "slots": slots, "date": date}
                return {"status": "error", "message": r.text[:200]}
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:200]}

    @server.tool()
    async def schedule_meeting(
        title: str, attendee_ids: list[str], start_time: str, duration_minutes: int = 30
    ) -> dict:
        """Schedule a new meeting on the calendar."""
        token = await _get_graph_token()
        if not token:
            return {"status": "not_connected", "message": "No valid user session. Please sign in first."}

        try:
            # Parse start time and calculate end time
            from datetime import timedelta
            if not start_time or not start_time.strip():
                return {"status": "error", "message": "start_time is required. Provide an ISO-8601 datetime (e.g. 2026-05-29T13:00:00)."}
            start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            end_dt = start_dt + timedelta(minutes=duration_minutes)

            attendees = [
                {
                    "emailAddress": {"address": aid},
                    "type": "required",
                }
                for aid in attendee_ids
            ]
            payload = {
                "subject": title,
                "start": {"dateTime": start_dt.isoformat(), "timeZone": "UTC"},
                "end": {"dateTime": end_dt.isoformat(), "timeZone": "UTC"},
                "attendees": attendees,
                "isOnlineMeeting": True,
                "onlineMeetingProvider": "teamsForBusiness",
            }
            async with httpx.AsyncClient(timeout=15) as http:
                r = await http.post(
                    "https://graph.microsoft.com/v1.0/me/events",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json=payload,
                )
                if r.status_code in (200, 201):
                    data = r.json()
                    return {
                        "status": "ok",
                        "event_id": data.get("id"),
                        "subject": data.get("subject"),
                        "web_link": data.get("webLink", ""),
                        "join_url": (data.get("onlineMeeting") or {}).get("joinUrl", ""),
                    }
                return {"status": "error", "message": r.text[:200]}
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:200]}

    @server.tool()
    async def list_calendar_events(date: str | None = None) -> dict:
        """List today's calendar events (meetings) in the user's local timezone."""
        token = await _get_graph_token()
        if not token:
            return {"status": "not_connected", "message": "No valid user session. Please sign in first."}

        # Windows timezone name → UTC offset in minutes
        _WIN_TZ_OFFSETS: dict[str, int] = {
            "India Standard Time": 330,
            "UTC": 0,
            "Eastern Standard Time": -300,
            "Eastern Daylight Time": -240,
            "Central Standard Time": -360,
            "Mountain Standard Time": -420,
            "Pacific Standard Time": -480,
            "GMT Standard Time": 0,
            "W. Europe Standard Time": 60,
            "Central Europe Standard Time": 60,
            "Romance Standard Time": 60,
            "E. Europe Standard Time": 120,
            "Arab Standard Time": 180,
            "Arabian Standard Time": 240,
            "Iran Standard Time": 210,
            "Pakistan Standard Time": 300,
            "Bangladesh Standard Time": 360,
            "SE Asia Standard Time": 420,
            "China Standard Time": 480,
            "Tokyo Standard Time": 540,
            "AUS Eastern Standard Time": 600,
            "New Zealand Standard Time": 720,
        }

        try:
            from datetime import timedelta

            async with httpx.AsyncClient(timeout=15) as http:
                # 1. Timezone resolution priority:
                #    a) user_preferences.json (set via Settings UI)
                #    b) /me/mailboxSettings (Exchange mailbox timezone)
                #    c) Hardcoded fallback: India Standard Time
                tz_name = "India Standard Time"
                tz_offset_mins = 330

                _prefs_file = os.path.join(os.path.expanduser("~"), ".tagent", "user_preferences.json")
                try:
                    with open(_prefs_file, "r", encoding="utf-8") as _pf:
                        _prefs = json.load(_pf)
                    if _prefs.get("calendar_timezone"):
                        tz_name = _prefs["calendar_timezone"]
                        tz_offset_mins = _WIN_TZ_OFFSETS.get(tz_name, 330)
                except (FileNotFoundError, Exception):
                    # Fall through to mailbox settings
                    tz_r = await http.get(
                        "https://graph.microsoft.com/v1.0/me/mailboxSettings",
                        headers={"Authorization": f"Bearer {token}"},
                        params={"$select": "timeZone"},
                    )
                    if tz_r.status_code == 200:
                        mb_tz = tz_r.json().get("timeZone", "")
                        # Only use mailbox value if it's not UTC/empty (trust our default over UTC)
                        if mb_tz and mb_tz != "UTC":
                            tz_name = mb_tz
                            tz_offset_mins = _WIN_TZ_OFFSETS.get(tz_name, 330)

                # 2. Compute "today" in the user's local timezone
                utc_now = datetime.now(timezone.utc)
                local_now = utc_now + timedelta(minutes=tz_offset_mins)

                if date:
                    local_date = datetime.fromisoformat(date.split("T")[0]).date()
                else:
                    local_date = local_now.date()

                # 3. Convert local midnight → UTC for calendarView range
                tz_delta = timedelta(minutes=tz_offset_mins)
                local_start = datetime(local_date.year, local_date.month, local_date.day, 0, 0, 0)
                local_end = datetime(local_date.year, local_date.month, local_date.day, 23, 59, 59)
                utc_start = (local_start - tz_delta).strftime("%Y-%m-%dT%H:%M:%SZ")
                utc_end = (local_end - tz_delta).strftime("%Y-%m-%dT%H:%M:%SZ")

                r = await http.get(
                    "https://graph.microsoft.com/v1.0/me/calendarView",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Prefer": f'outlook.timezone="{tz_name}"',
                    },
                    params={
                        "startDateTime": utc_start,
                        "endDateTime": utc_end,
                        "$select": "id,subject,start,end,location,attendees,isOnlineMeeting,onlineMeeting",
                        "$top": "20",
                    },
                )
                if r.status_code == 200:
                    events = r.json().get("value", [])

                    # Short display abbreviation for the user's timezone
                    _TZ_ABBR = {
                        "India Standard Time": "IST",
                        "UTC": "UTC",
                        "Eastern Standard Time": "EST",
                        "Central Standard Time": "CST",
                        "Mountain Standard Time": "MST",
                        "Pacific Standard Time": "PST",
                        "GMT Standard Time": "GMT",
                        "W. Europe Standard Time": "CET",
                        "China Standard Time": "CST",
                        "Tokyo Standard Time": "JST",
                        "AUS Eastern Standard Time": "AEST",
                        "New Zealand Standard Time": "NZST",
                    }
                    tz_abbr = _TZ_ABBR.get(tz_name, tz_name)

                    def _fmt(raw: str) -> str:
                        """Format a Graph naive-datetime string to '28 May 2026, 02:30 PM IST'."""
                        try:
                            clean = raw.split(".")[0]  # strip sub-seconds
                            dt = datetime.fromisoformat(clean)
                            return dt.strftime("%d %b %Y, %I:%M %p") + f" {tz_abbr}"
                        except Exception:
                            return raw

                    return {
                        "status": "ok",
                        "timezone": tz_abbr,
                        "date": str(local_date),
                        "events": [
                            {
                                "id": e.get("id"),
                                "subject": e.get("subject"),
                                "start": _fmt((e.get("start") or {}).get("dateTime", "")),
                                "end": _fmt((e.get("end") or {}).get("dateTime", "")),
                                "location": (e.get("location") or {}).get("displayName", ""),
                                "is_online": e.get("isOnlineMeeting", False),
                                "join_url": (e.get("onlineMeeting") or {}).get("joinUrl", ""),
                            }
                            for e in events
                        ],
                    }
                return {"status": "error", "message": r.text[:200]}
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:200]}

    @server.tool()
    async def get_meeting_transcript(meeting_subject: str = "") -> dict:
        """Fetch the transcript of a recent Teams meeting you attended.
        Optionally filter by meeting_subject keyword."""
        token = await _get_graph_token()
        if not token:
            return {"status": "not_connected", "message": "No valid user session. Please sign in first."}

        try:
            from datetime import timedelta

            async with httpx.AsyncClient(timeout=30) as http:
                # 1. Get recent online meetings from calendar (last 7 days)
                now = datetime.now(timezone.utc)
                start = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
                end = now.strftime("%Y-%m-%dT%H:%M:%SZ")

                events_r = await http.get(
                    "https://graph.microsoft.com/v1.0/me/calendarView",
                    headers={"Authorization": f"Bearer {token}"},
                    params={
                        "startDateTime": start,
                        "endDateTime": end,
                        "$select": "id,subject,start,end,isOnlineMeeting,onlineMeeting",
                        "$top": "20",
                    },
                )
                if events_r.status_code != 200:
                    return {"status": "error", "message": f"Could not fetch calendar: {events_r.text[:200]}"}

                events = [e for e in events_r.json().get("value", []) if e.get("isOnlineMeeting")]
                if not events:
                    return {"status": "ok", "message": "No Teams online meetings found in the past 7 days."}

                # Filter by subject keyword if provided
                if meeting_subject:
                    matched = [e for e in events if meeting_subject.lower() in (e.get("subject") or "").lower()]
                    if not matched:
                        subjects = [e.get("subject") for e in events]
                        return {"status": "ok", "message": f"No meeting matched '{meeting_subject}'. Recent meetings: {subjects}"}
                    events = matched

                # Try the most recent matching meeting first
                for target in reversed(events):
                    join_url = (target.get("onlineMeeting") or {}).get("joinUrl", "")
                    if not join_url:
                        continue

                    # 2. Look up the onlineMeeting object by joinWebUrl
                    import urllib.parse
                    filter_url = f"joinWebUrl eq '{join_url}'"
                    om_r = await http.get(
                        "https://graph.microsoft.com/v1.0/me/onlineMeetings",
                        headers={"Authorization": f"Bearer {token}"},
                        params={"$filter": filter_url},
                    )
                    if om_r.status_code != 200 or not om_r.json().get("value"):
                        continue

                    om_id = om_r.json()["value"][0]["id"]

                    # 3. List transcripts for this meeting
                    tr_r = await http.get(
                        f"https://graph.microsoft.com/v1.0/me/onlineMeetings/{om_id}/transcripts",
                        headers={"Authorization": f"Bearer {token}"},
                    )
                    if tr_r.status_code == 403:
                        return {
                            "status": "permission_error",
                            "message": (
                                "Transcript access requires 'OnlineMeetingTranscript.Read.All' permission. "
                                "Please re-run trigger_login.py to grant the new scope, or ask your Teams admin to enable it."
                            ),
                            "meeting": target.get("subject"),
                        }
                    if tr_r.status_code != 200:
                        continue

                    transcripts = tr_r.json().get("value", [])
                    if not transcripts:
                        return {
                            "status": "ok",
                            "message": "Meeting found but no transcript exists. Transcription must be started during the meeting.",
                            "meeting": target.get("subject"),
                            "start": (target.get("start") or {}).get("dateTime", ""),
                        }

                    # 4. Download the latest transcript (VTT format)
                    tid = transcripts[-1]["id"]
                    content_r = await http.get(
                        f"https://graph.microsoft.com/v1.0/me/onlineMeetings/{om_id}/transcripts/{tid}/content",
                        headers={"Authorization": f"Bearer {token}", "Accept": "text/vtt"},
                    )
                    if content_r.status_code != 200:
                        return {"status": "error", "message": f"Could not download transcript ({content_r.status_code})."}

                    # Parse VTT → plain text (strip timestamps/headers)
                    lines = []
                    for line in content_r.text.splitlines():
                        line = line.strip()
                        if not line or line.startswith("WEBVTT") or "-->" in line or line.isdigit():
                            continue
                        # VTT speaker tags look like: <v Speaker Name>text
                        if line.startswith("<v "):
                            parts = line.split(">", 1)
                            speaker = parts[0][3:] if len(parts) > 1 else ""
                            text = parts[1].strip() if len(parts) > 1 else line
                            lines.append(f"{speaker}: {text}" if speaker else text)
                        else:
                            lines.append(line)

                    return {
                        "status": "ok",
                        "meeting": target.get("subject"),
                        "start": (target.get("start") or {}).get("dateTime", ""),
                        "transcript": "\n".join(lines)[:8000],
                    }

                return {
                    "status": "ok",
                    "message": "No transcript could be retrieved. Either transcription was not started, or the OnlineMeetings.Read permission is missing.",
                }
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:300]}
