"""Shared constants for the Tagent CLI."""

from __future__ import annotations

import os
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ORCHESTRATOR_DIR = PROJECT_ROOT / "backend" / "services" / "orchestrator-service"
MCP_TOOLS_DIR = PROJECT_ROOT / "backend" / "services" / "mcp-tools-service"
TEAMS_ADAPTER_DIR = PROJECT_ROOT / "backend" / "services" / "teams-adapter-service"
FRONTEND_DIR = PROJECT_ROOT / "frontend"
PIDFILE_DIR = Path(os.path.expanduser("~")) / ".tagent" / "pids"

# ── Service config ─────────────────────────────────────────────────────────────
ORCHESTRATOR_PORT = 8001
FRONTEND_PORT = 5173
TEAMS_PORT = 3978

ORCHESTRATOR_URL = f"http://localhost:{ORCHESTRATOR_PORT}"
HEALTH_URL = f"{ORCHESTRATOR_URL}/health"
TOOLS_URL = f"{ORCHESTRATOR_URL}/tool/call"
SETTINGS_URL = f"{ORCHESTRATOR_URL}/settings/status"
ORCHESTRATE_URL = f"{ORCHESTRATOR_URL}/orchestrate"

# ── ASCII art ──────────────────────────────────────────────────────────────────
TAGENT_BANNER = r"""
 ████████╗ █████╗  ██████╗ ███████╗███╗   ██╗████████╗
 ╚══██╔══╝██╔══██╗██╔════╝ ██╔════╝████╗  ██║╚══██╔══╝
    ██║   ███████║██║  ███╗█████╗  ██╔██╗ ██║   ██║   
    ██║   ██╔══██║██║   ██║██╔══╝  ██║╚██╗██║   ██║   
    ██║   ██║  ██║╚██████╔╝███████╗██║ ╚████║   ██║   
    ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝  ╚═══╝   ╚═╝   
"""

# ── Tool registry ─────────────────────────────────────────────────────────────
TOOLS_REGISTRY = {
    "github": {
        "icon": "🐙",
        "name": "GitHub",
        "tools": ["create_github_issue", "list_github_issues", "get_github_repo"],
        "description": "Create issues, PRs, read repos",
    },
    "jira": {
        "icon": "📋",
        "name": "Jira",
        "tools": ["search_jira_issues", "create_jira_issue", "list_jira_issues", "search_closed_issues"],
        "description": "Create/update tickets, search issues",
    },
    "notion": {
        "icon": "📝",
        "name": "Notion",
        "tools": ["search_notion_pages", "create_notion_page"],
        "description": "Read/write pages and databases",
    },
    "google_calendar": {
        "icon": "📅",
        "name": "Google Calendar",
        "tools": ["list_google_calendar_events", "create_google_calendar_event", "search_google_calendar_events"],
        "description": "Create events, check availability",
    },
    "teams": {
        "icon": "👥",
        "name": "Microsoft Teams",
        "tools": ["send_direct_message", "list_teams_channels"],
        "description": "Send messages, manage channels",
    },
    "graph_api": {
        "icon": "📊",
        "name": "Microsoft Graph",
        "tools": ["get_user_info", "search_user", "list_calendar_events"],
        "description": "Users, emails, files via Graph",
    },
    "meetings": {
        "icon": "🎯",
        "name": "Meetings",
        "tools": ["schedule_meeting", "join_meeting_as_bot"],
        "description": "Schedule, summarize, join meetings",
    },
    "memory": {
        "icon": "🧠",
        "name": "Memory",
        "tools": ["store_memory", "recall_memory"],
        "description": "Persistent agent memory across sessions",
    },
    "playwright": {
        "icon": "🤖",
        "name": "Playwright Bot",
        "tools": ["join_meeting_as_bot"],
        "description": "Browser automation and web scraping",
    },
    "automation": {
        "icon": "⚡",
        "name": "Automation",
        "tools": ["run_workflow", "list_workflows"],
        "description": "Custom workflow automation",
    },
    "briefing": {
        "icon": "📣",
        "name": "Briefing",
        "tools": ["generate_daily_briefing"],
        "description": "Generate daily/weekly briefings",
    },
    "dacl": {
        "icon": "⚖️",
        "name": "DACL Rules",
        "tools": ["validate_business_rule", "list_available_policies"],
        "description": "Business rule validation engine",
    },
}
