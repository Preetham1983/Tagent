"""Builds MCP tool argument dicts from a DirectToolRequest.

Each tool has its own argument shape. This service maps the generic
request fields (query, title, description, priority, jql) to the
exact args the MCP tool expects, keeping that logic out of the route.
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timedelta

from tagent.api.schemas import DirectToolRequest


def build_tool_args(req: DirectToolRequest) -> dict:
    """Return the MCP args dict for the given tool request."""
    tool_name = req.tool_name
    jira_project = os.environ.get("JIRA_PROJECT_KEY", "ITP")

    # ── Jira ──────────────────────────────────────────────────────────────────
    if tool_name == "list_jira_projects":
        return {}

    if tool_name == "list_project_members":
        return {"project_key": req.query or jira_project}

    if tool_name == "list_jira_issues":
        return {"jql": f"project = {jira_project} ORDER BY created DESC"}

    if tool_name in ("search_jira_issues", "list_jira_issues"):
        raw = req.jql or req.query or ""
        if raw and "=" not in raw and "ORDER BY" not in raw.upper():
            jql = f'project = {jira_project} AND text ~ "{raw}" ORDER BY created DESC'
        elif raw:
            jql = raw
        else:
            jql = f"project = {jira_project} ORDER BY created DESC"
        return {"jql": jql}

    if tool_name == "search_closed_issues":
        return {"jql": f"project = {jira_project} AND status = Done ORDER BY updated DESC"}

    if tool_name == "create_jira_issue":
        return {
            "title": req.title or req.query or "New task",
            "description": req.description or req.query,
            "priority": req.priority,
        }

    # ── GitHub ─────────────────────────────────────────────────────────────────
    if tool_name == "list_github_repos":
        return {"owner": req.query or ""}

    if tool_name == "list_github_prs":
        return {"state": req.query or "open"}

    if tool_name == "list_github_issues":
        return {"state": req.query or "open"}

    if tool_name == "create_github_issue":
        return {
            "title": req.title or req.query or "New issue",
            "body": req.description or "",
            "labels": "",
        }

    # ── Notion ─────────────────────────────────────────────────────────────────
    if tool_name == "search_notion":
        return {"query": req.query or ""}

    if tool_name == "list_notion_pages":
        return {}

    if tool_name == "create_notion_page":
        return {
            "title": req.title or req.query or "New page",
            "content": req.description or "",
        }

    # ── Teams / Microsoft 365 ──────────────────────────────────────────────────
    if tool_name == "send_direct_message":
        raw = (req.query or "").strip()
        email_match = re.search(r"[\w.\-+]+@[\w.\-]+\.\w+", raw)
        if email_match:
            recipient = email_match.group(0)
            body = re.sub(r"[\w.\-+]+@[\w.\-]+\.\w+", "", raw).strip().lstrip("-").strip()
            msg_body = body or "Hello!"
        else:
            parts = re.split(r"\s*-\s*", raw, maxsplit=1)
            recipient = parts[0].strip()
            msg_body = parts[1].strip() if len(parts) > 1 else "Hello!"
        return {"recipient_email": recipient, "message": msg_body}

    if tool_name == "schedule_meeting":
        return _build_schedule_meeting_args(req)

    if tool_name == "list_calendar_events":
        return {}

    if tool_name == "get_user_info":
        return {}

    if tool_name == "search_user":
        return {"name": req.query or ""}

    if tool_name == "list_recent_chats":
        return {"top": 10}

    if tool_name == "read_chat_messages":
        return {"chat_id": req.query or "", "top": 20}

    if tool_name in ("get_meeting_attendance", "get_meeting_transcript", "analyze_meeting"):
        return {"meeting_subject": req.query or ""}

    if tool_name in ("get_daily_briefing", "generate_standup"):
        return {}

    if tool_name == "nudge_colleague":
        parts = [p.strip() for p in (req.query or "").split(",", 1)]
        return {
            "colleague_name": parts[0] if parts else "",
            "item_id": parts[1] if len(parts) > 1 else "Task",
        }

    if tool_name == "chat_to_jira":
        return {"colleague_name": req.query or ""}

    if tool_name == "negotiate_meeting":
        parts = [p.strip() for p in (req.query or "").split(",", 1)]
        return {
            "colleague_name": parts[0] if parts else "",
            "topic": parts[1] if len(parts) > 1 else "Quick Sync",
        }

    if tool_name == "smart_ooo_handoff":
        parts = [p.strip() for p in (req.query or "").split(",", 2)]
        return {
            "backup_colleague_name": parts[0] if parts else "",
            "start_date": parts[1] if len(parts) > 1 else "soon",
            "end_date": parts[2] if len(parts) > 2 else "later",
        }

    if tool_name == "analyze_onedrive_transcript":
        return {"meeting_name": req.query or ""}

    if tool_name == "join_meeting_as_bot":
        raw = req.query or ""
        url_match = re.search(r"(https?://teams\.microsoft\.com[^\s>\"']+)", raw)
        meeting_url = url_match.group(1) if url_match else raw
        return {"meeting_url": meeting_url, "duration_seconds": 30}

    # Default fallback
    return {"query": req.query} if req.query else {}


# ── Helpers ────────────────────────────────────────────────────────────────────

_MONTHS: dict[str, int] = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}


def _build_schedule_meeting_args(req: DirectToolRequest) -> dict:
    raw = req.query or ""
    raw_l = raw.lower()

    attendees = re.findall(r"[\w\.-]+@[\w\.-]+\.\w+", raw)

    # Title extraction
    title_match = re.search(
        r"(?:desc(?:ription)?|topic|subject|title)\s*[:\-]\s*(.+?)(?:\s*$|\n)",
        raw, re.IGNORECASE,
    )
    if title_match:
        title = title_match.group(1).strip()
    else:
        title = re.sub(r"[\w\.-]+@[\w\.-]+\.\w+", "", raw)
        title = re.sub(
            r"\b(?:at|on|pm|am|schedule|meet(?:ing)?|a|with|hey|desc|topic)\b",
            " ", title, flags=re.IGNORECASE,
        )
        title = " ".join(title.split()) or "Teams Meeting"

    # Start time extraction
    start_time = ""
    iso_match = re.search(r"(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?)", raw)
    if iso_match:
        start_time = iso_match.group(1)
        if start_time.count(":") == 1:
            start_time += ":00"
    else:
        tm = re.search(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)", raw_l)
        if tm:
            h = int(tm.group(1))
            m = int(tm.group(2) or 0)
            meridiem = tm.group(3)
            if meridiem == "pm" and h != 12:
                h += 12
            elif meridiem == "am" and h == 12:
                h = 0

            now = datetime.now()
            day, mon, yr = now.day, now.month, now.year
            month_pattern = "|".join(_MONTHS)
            dm = re.search(rf"(\d{{1,2}})(?:st|nd|rd|th)?\s+({month_pattern})", raw_l)
            md = re.search(rf"({month_pattern})\s+(\d{{1,2}})(?:st|nd|rd|th)?", raw_l)
            if dm:
                day, mon = int(dm.group(1)), _MONTHS[dm.group(2)]
            elif md:
                mon, day = _MONTHS[md.group(1)], int(md.group(2))
            try:
                cand = datetime(yr, mon, day, h, m)
                if cand < now:
                    cand = cand.replace(year=yr + 1)
                start_time = cand.strftime("%Y-%m-%dT%H:%M:%S")
            except ValueError:
                pass

    if not start_time:
        start_time = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

    return {
        "attendee_ids": attendees,
        "title": title,
        "start_time": start_time,
        "duration_minutes": 30,
    }
