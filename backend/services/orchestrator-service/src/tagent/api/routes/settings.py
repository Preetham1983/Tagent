"""Settings endpoints — Jira, calendar, Google Calendar, integration status."""

from __future__ import annotations

import os

from fastapi import APIRouter

from tagent.api.schemas import (
    CalendarSettingsRequest,
    GoogleCalendarSettingsRequest,
    JiraSettingsRequest,
)
from tagent.infrastructure.config.env_file import load_user_prefs, save_user_prefs, update_env_file

router = APIRouter(prefix="/settings")

_MS_TOKEN_CACHE = os.path.join(os.path.expanduser("~"), ".tagent", "ms_graph_token_cache.json")


@router.post("/jira")
async def save_jira_settings(req: JiraSettingsRequest) -> dict:
    """Save Jira credentials at runtime so the MCP subprocess inherits them."""
    os.environ["JIRA_BASE_URL"] = req.jira_base_url.rstrip("/")
    os.environ["JIRA_EMAIL"] = req.jira_email
    os.environ["JIRA_API_TOKEN"] = req.jira_api_token
    os.environ["JIRA_PROJECT_KEY"] = req.jira_project_key
    update_env_file(
        {
            "JIRA_BASE_URL": req.jira_base_url.rstrip("/"),
            "JIRA_EMAIL": req.jira_email,
            "JIRA_API_TOKEN": req.jira_api_token,
            "JIRA_PROJECT_KEY": req.jira_project_key,
        }
    )
    return {"status": "ok", "message": "Jira credentials saved"}


@router.post("/google-calendar")
async def save_google_calendar_settings(req: GoogleCalendarSettingsRequest) -> dict:
    """Save Google Calendar MCP credentials path at runtime."""
    path = req.credentials_path.strip()
    os.environ["GCAL_MCP_OAUTH_CREDENTIALS"] = path
    update_env_file({"GCAL_MCP_OAUTH_CREDENTIALS": path})
    return {"status": "ok", "message": "Google Calendar credentials path saved"}


@router.post("/calendar")
async def save_calendar_settings(req: CalendarSettingsRequest) -> dict:
    """Save the user's preferred calendar timezone."""
    save_user_prefs({"calendar_timezone": req.timezone})
    return {"status": "ok", "timezone": req.timezone}


@router.get("/calendar")
async def get_calendar_settings() -> dict:
    """Return the saved calendar timezone preference."""
    tz = load_user_prefs().get("calendar_timezone", "India Standard Time")
    return {"timezone": tz}


@router.get("/status")
async def get_settings_status() -> dict:
    """Return integration connection status — no secrets are exposed."""
    from tagent.infrastructure.config.settings import Settings

    s = Settings()

    jira_configured = bool(
        os.environ.get("JIRA_BASE_URL")
        and os.environ.get("JIRA_EMAIL")
        and os.environ.get("JIRA_API_TOKEN")
    )
    teams_configured = bool(s.ms_tenant_id and s.ms_client_id and s.ms_client_secret)
    tenant_preview = (s.ms_tenant_id[:8] + "…") if s.ms_tenant_id else ""

    return {
        "jira": {
            "configured": jira_configured,
            "base_url": os.environ.get("JIRA_BASE_URL", s.jira_base_url),
            "email": os.environ.get("JIRA_EMAIL", s.jira_email),
            "project_key": os.environ.get("JIRA_PROJECT_KEY", s.jira_project_key),
        },
        "teams": {
            "configured": teams_configured,
            "session_active": os.path.isfile(_MS_TOKEN_CACHE),
            "can_auth": bool(s.ms_tenant_id and s.ms_client_id),
            "tenant_id": tenant_preview,
        },
        "calendar": {
            "configured": teams_configured,
            "timezone": load_user_prefs().get("calendar_timezone", "India Standard Time"),
        },
        "github": {
            "configured": bool(os.environ.get("GITHUB_TOKEN")),
            "owner": os.environ.get("GITHUB_DEFAULT_OWNER", ""),
            "repo": os.environ.get("GITHUB_DEFAULT_REPO", ""),
        },
        "notion": {
            "configured": bool(os.environ.get("NOTION_TOKEN")),
            "database_id": os.environ.get("NOTION_DATABASE_ID", ""),
        },
        "google_calendar": {
            "configured": bool(
                s.gcal_mcp_oauth_credentials and os.path.isfile(s.gcal_mcp_oauth_credentials)
            ),
            "calendar_id": os.environ.get("GOOGLE_CALENDAR_ID", "primary"),
        },
    }
