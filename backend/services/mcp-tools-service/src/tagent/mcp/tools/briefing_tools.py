"""Smart Daily Briefing and Standup Generator — parallel multi-integration fetch."""

from __future__ import annotations

import asyncio
import base64
import json
import os
from datetime import date, datetime, timedelta, timezone

import httpx
from mcp.server import Server

from tagent.mcp.tools._token import get_graph_token as _get_graph_token


# ── Shared timezone helpers ───────────────────────────────────────────────────

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

_WIN_TZ_ABBRS: dict[str, str] = {
    "India Standard Time": "IST",
    "UTC": "UTC",
    "Eastern Standard Time": "EST",
    "Eastern Daylight Time": "EDT",
    "Central Standard Time": "CST",
    "Mountain Standard Time": "MST",
    "Pacific Standard Time": "PST",
    "GMT Standard Time": "GMT",
    "W. Europe Standard Time": "CET",
    "Central Europe Standard Time": "CET",
    "Arab Standard Time": "AST",
    "Arabian Standard Time": "GST",
    "Pakistan Standard Time": "PKT",
    "Bangladesh Standard Time": "BST",
    "SE Asia Standard Time": "WIB",
    "China Standard Time": "CST",
    "Tokyo Standard Time": "JST",
    "AUS Eastern Standard Time": "AEST",
    "New Zealand Standard Time": "NZST",
}


def _get_tz_settings() -> tuple[str, int, str]:
    """Return (windows_tz_name, offset_minutes, abbreviation)."""
    prefs_file = os.path.join(os.path.expanduser("~"), ".tagent", "user_preferences.json")
    tz_name = "India Standard Time"
    try:
        with open(prefs_file, "r", encoding="utf-8") as f:
            prefs = json.load(f)
        if prefs.get("calendar_timezone"):
            tz_name = prefs["calendar_timezone"]
    except (FileNotFoundError, Exception):
        pass
    offset_mins = _WIN_TZ_OFFSETS.get(tz_name, 330)
    abbr = _WIN_TZ_ABBRS.get(tz_name, "IST")
    return tz_name, offset_mins, abbr


def _fmt_naive(raw: str, abbr: str) -> str:
    """Format a Graph naive-datetime string (already in local tz via Prefer header) to '9:30 AM IST'."""
    try:
        clean = raw.split(".")[0]
        dt = datetime.fromisoformat(clean)
        hour = dt.hour % 12 or 12
        ampm = "AM" if dt.hour < 12 else "PM"
        return f"{hour}:{dt.minute:02d} {ampm} {abbr}"
    except Exception:
        return raw[:16]


# ── Per-integration fetch helpers (all handle missing config gracefully) ───────

async def _fetch_my_profile(token: str) -> dict:
    if not token:
        return {}
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            r = await http.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {token}"},
                params={"$select": "displayName,mail,userPrincipalName,jobTitle,department"},
            )
            if r.status_code == 200:
                d = r.json()
                return {
                    "name": d.get("displayName", ""),
                    "email": d.get("mail") or d.get("userPrincipalName", ""),
                    "title": d.get("jobTitle", ""),
                    "department": d.get("department", ""),
                }
    except Exception:
        pass
    return {}


async def _fetch_calendar_events(token: str, tz_name: str, offset_mins: int, abbr: str) -> list[dict]:
    if not token:
        return []
    try:
        tz_delta = timedelta(minutes=offset_mins)
        utc_now = datetime.now(timezone.utc)
        local_now = utc_now + tz_delta
        local_date = local_now.date()

        local_start = datetime(local_date.year, local_date.month, local_date.day, 0, 0, 0)
        local_end = datetime(local_date.year, local_date.month, local_date.day, 23, 59, 59)
        utc_start = (local_start - tz_delta).strftime("%Y-%m-%dT%H:%M:%SZ")
        utc_end = (local_end - tz_delta).strftime("%Y-%m-%dT%H:%M:%SZ")

        async with httpx.AsyncClient(timeout=15) as http:
            r = await http.get(
                "https://graph.microsoft.com/v1.0/me/calendarView",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Prefer": f'outlook.timezone="{tz_name}"',
                },
                params={
                    "startDateTime": utc_start,
                    "endDateTime": utc_end,
                    "$select": "subject,start,end,isOnlineMeeting,onlineMeeting,attendees",
                    "$top": "20",
                },
            )
            if r.status_code != 200:
                return []
            events = r.json().get("value", [])
            result = []
            for e in events:
                start_raw = (e.get("start") or {}).get("dateTime", "")
                end_raw = (e.get("end") or {}).get("dateTime", "")
                attendees = [
                    a.get("emailAddress", {}).get("name", "")
                    for a in (e.get("attendees") or [])[:4]
                ]
                result.append({
                    "subject": e.get("subject", "Untitled"),
                    "start": _fmt_naive(start_raw, abbr),
                    "end": _fmt_naive(end_raw, abbr),
                    "is_online": e.get("isOnlineMeeting", False),
                    "join_url": (e.get("onlineMeeting") or {}).get("joinUrl", ""),
                    "attendees": attendees,
                })
            return result
    except Exception:
        return []


async def _fetch_jira_issues(jql: str) -> list[dict]:
    base_url = os.environ.get("JIRA_BASE_URL", "").rstrip("/")
    email = os.environ.get("JIRA_EMAIL", "")
    api_token = os.environ.get("JIRA_API_TOKEN", "")
    if not base_url or not email or not api_token:
        return []
    credentials = f"{email}:{api_token}"
    encoded = base64.b64encode(credentials.encode()).decode()
    headers = {
        "Authorization": f"Basic {encoded}",
        "Accept": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=15) as http:
            r = await http.get(
                f"{base_url}/rest/api/3/search",
                headers=headers,
                params={"jql": jql, "maxResults": 15, "fields": "summary,status,priority,assignee"},
            )
            if r.status_code != 200:
                return []
            return [
                {
                    "key": i.get("key", ""),
                    "summary": i.get("fields", {}).get("summary", ""),
                    "status": (i.get("fields", {}).get("status") or {}).get("name", ""),
                    "priority": (i.get("fields", {}).get("priority") or {}).get("name", ""),
                }
                for i in r.json().get("issues", [])
            ]
    except Exception:
        return []


async def _fetch_github_prs(state: str = "open") -> list[dict]:
    token = os.environ.get("GITHUB_TOKEN", "")
    if not token:
        return []
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        # Resolve authenticated user's login
        async with httpx.AsyncClient(timeout=10) as http:
            me_r = await http.get("https://api.github.com/user", headers=headers)
            if me_r.status_code != 200:
                return []
            username = me_r.json().get("login", "")
        if not username:
            return []

        # Search ALL open PRs authored by this user across every repo
        async with httpx.AsyncClient(timeout=15) as http:
            r = await http.get(
                "https://api.github.com/search/issues",
                headers=headers,
                params={
                    "q": f"is:pr is:{state} author:{username}",
                    "sort": "updated",
                    "order": "desc",
                    "per_page": 10,
                },
            )
            if r.status_code != 200:
                return []
            return [
                {
                    "number": item.get("number"),
                    "title": item.get("title", ""),
                    "author": username,
                    "repo": item.get("repository_url", "").split("/repos/")[-1],
                    "draft": item.get("draft", False),
                    "url": item.get("html_url", ""),
                }
                for item in r.json().get("items", [])
            ]
    except Exception:
        return []


async def _fetch_recent_chats(token: str) -> list[dict]:
    if not token:
        return []
    import re as _re
    try:
        # Get current user's ID so we can exclude ourselves from member lists
        my_id = ""
        async with httpx.AsyncClient(timeout=10) as http:
            me_r = await http.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {token}"},
                params={"$select": "id"},
            )
            if me_r.status_code == 200:
                my_id = me_r.json().get("id", "")

        async with httpx.AsyncClient(timeout=15) as http:
            r = await http.get(
                "https://graph.microsoft.com/v1.0/me/chats",
                headers={"Authorization": f"Bearer {token}"},
                params={
                    "$top": "8",
                    "$expand": "members,lastMessagePreview",
                    "$orderby": "lastMessagePreview/createdDateTime desc",
                },
            )
            if r.status_code != 200:
                return []
            results = []
            for c in r.json().get("value", [])[:5]:
                chat_type = c.get("chatType", "")
                topic = (c.get("topic") or "").strip()
                members = c.get("members", [])

                # Determine display name
                if topic:
                    display_name = topic
                elif chat_type == "oneOnOne":
                    # Find the other person by excluding our own userId
                    other = next(
                        (m.get("displayName", "") for m in members
                         if m.get("userId", "") != my_id and m.get("displayName")),
                        "Unknown",
                    )
                    display_name = other
                else:
                    # Group with no topic — list other members' first names
                    names = [
                        m.get("displayName", "").split()[0]
                        for m in members
                        if m.get("userId", "") != my_id and m.get("displayName")
                    ]
                    display_name = ", ".join(names[:4]) if names else "Group Chat"

                # Get message preview (requires $expand=lastMessagePreview)
                preview_obj = c.get("lastMessagePreview") or {}
                raw_msg = (preview_obj.get("body") or {}).get("content", "")
                msg = _re.sub(r"<[^>]+>", "", raw_msg).strip()[:80]

                results.append({"with": display_name, "preview": msg or "(no recent message)"})
            return results
    except Exception:
        return []


# ── Tool registration ─────────────────────────────────────────────────────────

def register_briefing_tools(server: Server) -> None:
    """Register smart briefing tools."""

    @server.tool()
    async def get_daily_briefing() -> dict:
        """
        Generate a personalised Smart Daily Briefing by fetching from every connected
        integration in parallel: MS 365 calendar meetings, open Jira issues assigned to
        you, open GitHub pull requests, and your recent Teams chats. Returns a structured
        summary ready for display.
        """
        token = await _get_graph_token()
        tz_name, offset_mins, abbr = _get_tz_settings()

        jira_project = os.environ.get("JIRA_PROJECT_KEY", "")
        proj_clause = f"project = {jira_project} AND " if jira_project else ""
        my_issues_jql = (
            f"{proj_clause}assignee = currentUser() AND status != Done "
            "ORDER BY priority ASC, updated DESC"
        )

        # Fire every integration simultaneously
        profile, meetings, jira_issues, github_prs, recent_chats = await asyncio.gather(
            _fetch_my_profile(token),
            _fetch_calendar_events(token, tz_name, offset_mins, abbr),
            _fetch_jira_issues(my_issues_jql),
            _fetch_github_prs("open"),
            _fetch_recent_chats(token),
            return_exceptions=True,
        )

        # Coerce exceptions to empty values
        if isinstance(profile, Exception): profile = {}
        if isinstance(meetings, Exception): meetings = []
        if isinstance(jira_issues, Exception): jira_issues = []
        if isinstance(github_prs, Exception): github_prs = []
        if isinstance(recent_chats, Exception): recent_chats = []

        github_configured = bool(os.environ.get("GITHUB_TOKEN"))
        today_str = date.today().strftime("%A, %d %B %Y")

        return {
            "status": "ok",
            "date": today_str,
            "timezone": abbr,
            "profile": profile,
            "meetings": meetings,
            "total_meetings": len(meetings),
            "jira_issues": jira_issues,
            "total_jira_issues": len(jira_issues),
            "github_prs": github_prs,
            "total_github_prs": len(github_prs),
            "github_configured": github_configured,
            "recent_chats": recent_chats,
        }

    @server.tool()
    async def generate_standup() -> dict:
        """
        Auto-generate a daily standup update by fetching from Jira and MS 365 in parallel:
        - Jira issues you completed yesterday (status = Done AND updated >= -1d)
        - Jira issues currently In Progress assigned to you
        - Jira issues labelled 'blocked' assigned to you
        - Today's calendar meetings
        - Open GitHub PRs in the default repo
        Returns structured data ready for LLM formatting as a standup message.
        """
        token = await _get_graph_token()
        tz_name, offset_mins, abbr = _get_tz_settings()

        jira_project = os.environ.get("JIRA_PROJECT_KEY", "")
        proj_clause = f"project = {jira_project} AND " if jira_project else ""

        done_yesterday_jql = (
            f"{proj_clause}assignee = currentUser() AND status changed to Done during (-1d, now()) "
            "ORDER BY updated DESC"
        )
        in_progress_jql = (
            f"{proj_clause}assignee = currentUser() AND status = 'In Progress' "
            "ORDER BY priority ASC"
        )
        blocked_jql = (
            f"{proj_clause}assignee = currentUser() AND (labels = blocked OR status = Blocked) "
            "ORDER BY priority ASC"
        )

        done_yesterday, in_progress, blocked, meetings, open_prs = await asyncio.gather(
            _fetch_jira_issues(done_yesterday_jql),
            _fetch_jira_issues(in_progress_jql),
            _fetch_jira_issues(blocked_jql),
            _fetch_calendar_events(token, tz_name, offset_mins, abbr),
            _fetch_github_prs("open"),
            return_exceptions=True,
        )

        if isinstance(done_yesterday, Exception): done_yesterday = []
        if isinstance(in_progress, Exception): in_progress = []
        if isinstance(blocked, Exception): blocked = []
        if isinstance(meetings, Exception): meetings = []
        if isinstance(open_prs, Exception): open_prs = []

        today_str = date.today().strftime("%A, %d %B %Y")

        return {
            "status": "ok",
            "date": today_str,
            "timezone": abbr,
            "done_yesterday": done_yesterday,
            "in_progress_today": in_progress,
            "blockers": blocked,
            "meetings_today": meetings,
            "open_prs": open_prs,
        }
