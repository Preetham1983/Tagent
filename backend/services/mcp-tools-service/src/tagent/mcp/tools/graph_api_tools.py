"""Microsoft Graph API tools for MCP."""

from __future__ import annotations

import json
import os
import time

import httpx
from mcp.server import Server
from tagent.mcp.tools._token import get_graph_token as _get_graph_token


def register_graph_api_tools(server: Server) -> None:
    """Register Graph API tools (user lookup, mail, presence)."""

    @server.tool()
    async def get_user_info(query: str = "") -> dict:
        """Return the currently signed-in user profile (name, email, job title)."""
        token = await _get_graph_token()
        if not token:
            return {
                "status": "not_connected",
                "message": "No valid user session found. Please sign in via device-code flow first.",
            }

        try:
            async with httpx.AsyncClient(timeout=10) as http:
                r = await http.get(
                    "https://graph.microsoft.com/v1.0/me",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"$select": "displayName,mail,userPrincipalName,jobTitle,department"},
                )
                if r.status_code == 400:
                    # Fallback for app-only token
                    r = await http.get(
                        "https://graph.microsoft.com/v1.0/users",
                        headers={"Authorization": f"Bearer {token}"},
                        params={"$top": "1", "$select": "displayName,mail,userPrincipalName,jobTitle,department"},
                    )
                    if r.status_code == 200:
                        data = r.json()
                        users = data.get("value", [])
                        if users:
                            data = users[0]
                            return {
                                "status": "ok",
                                "name": data.get("displayName", ""),
                                "email": data.get("mail") or data.get("userPrincipalName", ""),
                                "job_title": data.get("jobTitle", "N/A"),
                                "department": data.get("department", "N/A"),
                            }

                if r.status_code == 200:
                    data = r.json()
                    manager_name = "N/A"
                    manager_email = "N/A"
                    mgr_r = await http.get(
                        "https://graph.microsoft.com/v1.0/me/manager",
                        headers={"Authorization": f"Bearer {token}"},
                        params={"$select": "displayName,mail,userPrincipalName"},
                    )
                    if mgr_r.status_code == 200:
                        mgr = mgr_r.json()
                        manager_name = mgr.get("displayName", "N/A")
                        manager_email = mgr.get("mail") or mgr.get("userPrincipalName", "N/A")
                    return {
                        "status": "ok",
                        "name": data.get("displayName", ""),
                        "email": data.get("mail") or data.get("userPrincipalName", ""),
                        "job_title": data.get("jobTitle", "N/A"),
                        "department": data.get("department", "N/A"),
                        "manager_name": manager_name,
                        "manager_email": manager_email,
                    }
        except Exception:
            pass

        return {
            "status": "not_connected",
            "message": "No valid user session found. Please sign in via device-code flow first.",
        }

    @server.tool()
    async def send_email(to: str, subject: str, body: str) -> dict:
        """Send an email via Microsoft Graph."""
        # TODO: Implement real mail sending logic
        return {"to": to, "subject": subject, "status": "not_implemented"}

    @server.tool()
    async def search_user(name: str) -> dict:
        """Search for a colleague by name and return their email and profile."""
        token = await _get_graph_token()
        if not token:
            return {"status": "not_connected", "message": "No valid user session found."}

        try:
            # ConsistencyLevel: eventual must be an HTTP header (not a query param) for $search
            search_headers = {
                "Authorization": f"Bearer {token}",
                "ConsistencyLevel": "eventual",
            }
            async with httpx.AsyncClient(timeout=10) as http:
                r = await http.get(
                    "https://graph.microsoft.com/v1.0/users",
                    headers=search_headers,
                    params={
                        "$search": f'"displayName:{name}"',
                        "$select": "displayName,mail,userPrincipalName,jobTitle,department",
                        "$top": "10",
                        "$count": "true",
                    },
                )
                if r.status_code != 200:
                    # Fallback: $filter startswith on the first token of the name
                    first_token = name.split()[0] if name.split() else name
                    r = await http.get(
                        "https://graph.microsoft.com/v1.0/users",
                        headers=search_headers,
                        params={
                            "$filter": f"startswith(displayName,'{first_token}') or startswith(mail,'{first_token}')",
                            "$select": "displayName,mail,userPrincipalName,jobTitle,department",
                            "$top": "10",
                        },
                    )
                if r.status_code == 200:
                    users = r.json().get("value", [])
                    if not users:
                        return {"status": "ok", "message": f"No users found matching '{name}'."}
                    return {
                        "status": "ok",
                        "results": [
                            {
                                "name": u.get("displayName", ""),
                                "email": u.get("mail") or u.get("userPrincipalName", ""),
                                "job_title": u.get("jobTitle", "N/A"),
                                "department": u.get("department", "N/A"),
                            }
                            for u in users
                        ],
                    }
                return {"status": "error", "message": r.text[:200]}
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:200]}

    @server.tool()
    async def list_recent_chats(top: int = 10) -> dict:
        """List your most recent Teams chats and the last message preview."""
        token = await _get_graph_token()
        if not token:
            return {"status": "not_connected", "message": "No valid user session found."}

        try:
            async with httpx.AsyncClient(timeout=15) as http:
                r = await http.get(
                    "https://graph.microsoft.com/v1.0/me/chats",
                    headers={"Authorization": f"Bearer {token}"},
                    params={
                        "$expand": "lastMessagePreview,members",
                        "$top": str(top),
                        "$orderby": "lastMessagePreview/createdDateTime desc",
                    },
                )
                if r.status_code == 200:
                    chats = r.json().get("value", [])
                    results = []
                    for c in chats:
                        members = c.get("members", [])
                        # For 1:1 chats, show the other person's name
                        other_names = [
                            m.get("displayName", "")
                            for m in members
                            if m.get("displayName")
                        ]
                        preview = c.get("lastMessagePreview") or {}
                        results.append({
                            "chat_id": c.get("id", ""),
                            "type": c.get("chatType", ""),
                            "topic": c.get("topic") or ", ".join(other_names),
                            "last_message": (preview.get("body") or {}).get("content", "")[:120],
                            "last_message_time": preview.get("createdDateTime", ""),
                        })
                    return {"status": "ok", "chats": results}
                return {"status": "error", "message": r.text[:200]}
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:200]}

    @server.tool()
    async def read_chat_messages(chat_id: str, top: int = 20) -> dict:
        """Read recent messages from a Teams chat by chat ID."""
        token = await _get_graph_token()
        if not token:
            return {"status": "not_connected", "message": "No valid user session found."}

        try:
            async with httpx.AsyncClient(timeout=15) as http:
                r = await http.get(
                    f"https://graph.microsoft.com/v1.0/me/chats/{chat_id}/messages",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"$top": str(top), "$orderby": "createdDateTime desc"},
                )
                if r.status_code == 200:
                    messages = r.json().get("value", [])
                    return {
                        "status": "ok",
                        "messages": [
                            {
                                "from": (m.get("from") or {}).get("user", {}).get("displayName", "Unknown"),
                                "content": (m.get("body") or {}).get("content", "")[:500],
                                "time": m.get("createdDateTime", ""),
                            }
                            for m in reversed(messages)
                            if (m.get("body") or {}).get("content", "").strip()
                        ],
                    }
                return {"status": "error", "message": r.text[:200]}
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:200]}

    @server.tool()
    async def get_meeting_attendance(meeting_subject: str = "") -> dict:
        """Get attendance report for a recent Teams online meeting."""
        token = await _get_graph_token()
        if not token:
            return {"status": "not_connected", "message": "No valid user session found."}

        try:
            from datetime import datetime, timezone, timedelta
            async with httpx.AsyncClient(timeout=20) as http:
                now = datetime.now(timezone.utc)
                start = (now - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
                end = now.strftime("%Y-%m-%dT%H:%M:%SZ")

                # Get recent calendar events
                ev_r = await http.get(
                    "https://graph.microsoft.com/v1.0/me/calendarView",
                    headers={"Authorization": f"Bearer {token}"},
                    params={
                        "startDateTime": start, "endDateTime": end,
                        "$select": "id,subject,isOnlineMeeting,onlineMeeting",
                        "$top": "20",
                    },
                )
                if ev_r.status_code != 200:
                    return {"status": "error", "message": ev_r.text[:200]}

                events = [e for e in ev_r.json().get("value", []) if e.get("isOnlineMeeting")]
                if meeting_subject:
                    events = [e for e in events if meeting_subject.lower() in (e.get("subject") or "").lower()]
                if not events:
                    return {"status": "ok", "message": "No matching online meetings found in the past 7 days."}

                target = events[-1]
                join_url = (target.get("onlineMeeting") or {}).get("joinUrl", "")
                if not join_url:
                    return {"status": "ok", "message": "Meeting has no Teams join URL."}

                # Look up online meeting
                om_r = await http.get(
                    "https://graph.microsoft.com/v1.0/me/onlineMeetings",
                    headers={"Authorization": f"Bearer {token}"},
                    params={"$filter": f"joinWebUrl eq '{join_url}'"},
                )
                if om_r.status_code != 200 or not om_r.json().get("value"):
                    return {"status": "error", "message": "Could not retrieve online meeting object. OnlineMeetings.Read may be needed."}

                om_id = om_r.json()["value"][0]["id"]

                # Get attendance reports
                att_r = await http.get(
                    f"https://graph.microsoft.com/v1.0/me/onlineMeetings/{om_id}/attendanceReports",
                    headers={"Authorization": f"Bearer {token}"},
                )
                if att_r.status_code == 403:
                    return {
                        "status": "error",
                        "message": (
                            "Attendance reports require the OnlineMeetingArtifact.Read.All permission, "
                            "which needs admin consent. Please ask your Azure/Teams admin to grant this "
                            "permission to the app registration in the Azure portal."
                        ),
                    }
                if att_r.status_code != 200:
                    return {"status": "error", "message": f"Could not fetch attendance ({att_r.status_code}): {att_r.text[:200]}"}

                reports = att_r.json().get("value", [])
                if not reports:
                    return {"status": "ok", "meeting": target.get("subject"), "message": "No attendance report available yet."}

                # Get the latest report's attendee records
                report_id = reports[-1]["id"]
                rec_r = await http.get(
                    f"https://graph.microsoft.com/v1.0/me/onlineMeetings/{om_id}/attendanceReports/{report_id}/attendanceRecords",
                    headers={"Authorization": f"Bearer {token}"},
                )
                if rec_r.status_code != 200:
                    return {"status": "error", "message": rec_r.text[:200]}

                records = rec_r.json().get("value", [])
                return {
                    "status": "ok",
                    "meeting": target.get("subject"),
                    "total_attendees": len(records),
                    "attendees": [
                        {
                            "name": rec.get("identity", {}).get("displayName", "Unknown"),
                            "email": rec.get("identity", {}).get("id", ""),
                            "duration_minutes": round((rec.get("totalAttendanceInSeconds") or 0) / 60),
                            "role": rec.get("role", ""),
                        }
                        for rec in records
                    ],
                }
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:300]}
