"""Jira tools for MCP — real Jira REST API integration."""

from __future__ import annotations

import base64
import os

import httpx
from mcp.server import Server


def _get_jira_config() -> dict:
    """Load Jira credentials from environment."""
    return {
        "base_url": os.getenv("JIRA_BASE_URL", "").rstrip("/"),
        "email": os.getenv("JIRA_EMAIL", ""),
        "api_token": os.getenv("JIRA_API_TOKEN", ""),
        "project_key": os.getenv("JIRA_PROJECT_KEY", ""),
    }


def _get_jira_headers(config: dict) -> dict:
    """Build auth headers for Jira Cloud REST API."""
    credentials = f"{config['email']}:{config['api_token']}"
    encoded = base64.b64encode(credentials.encode()).decode()
    return {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def register_jira_tools(server: Server) -> None:
    """Register Jira tools (create, update, query issues)."""

    @server.tool()
    async def create_jira_issue(
        title: str, description: str = "", assignee: str = "", priority: str = "Medium"
    ) -> dict:
        """Create a new Jira issue."""
        config = _get_jira_config()
        if not config["base_url"] or not config["email"] or not config["api_token"]:
            return {
                "status": "not_configured",
                "message": "Jira credentials not configured. Set JIRA_BASE_URL, JIRA_EMAIL, JIRA_API_TOKEN.",
                "title": title,
            }

        try:
            payload = {
                "fields": {
                    "project": {"key": config["project_key"] or "PROJ"},
                    "summary": title,
                    "description": {
                        "type": "doc",
                        "version": 1,
                        "content": [
                            {
                                "type": "paragraph",
                                "content": [{"type": "text", "text": description or title}],
                            }
                        ],
                    },
                    "issuetype": {"name": "Task"},
                    "priority": {"name": priority},
                }
            }

            if assignee:
                payload["fields"]["assignee"] = {"accountId": assignee}

            async with httpx.AsyncClient(timeout=15) as http:
                r = await http.post(
                    f"{config['base_url']}/rest/api/3/issue",
                    headers=_get_jira_headers(config),
                    json=payload,
                )
                if r.status_code in (200, 201):
                    data = r.json()
                    return {
                        "status": "ok",
                        "key": data.get("key"),
                        "id": data.get("id"),
                        "url": f"{config['base_url']}/browse/{data.get('key')}",
                    }
                return {"status": "error", "message": r.text[:300]}
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:200]}

    @server.tool()
    async def search_jira_issues(jql: str) -> dict:
        """Search Jira issues using JQL."""
        config = _get_jira_config()
        if not config["base_url"] or not config["email"] or not config["api_token"]:
            return {
                "status": "not_configured",
                "message": "Jira credentials not configured.",
                "jql": jql,
                "results": [],
            }

        try:
            async with httpx.AsyncClient(timeout=15) as http:
                r = await http.post(
                    f"{config['base_url']}/rest/api/3/search/jql",
                    headers=_get_jira_headers(config),
                    json={
                        "jql": jql,
                        "maxResults": 20,
                        "fields": ["summary", "status", "priority", "assignee", "created", "updated"],
                    },
                )
                if r.status_code == 200:
                    data = r.json()
                    issues = []
                    for issue in data.get("issues", []):
                        fields = issue.get("fields", {})
                        issues.append({
                            "key": issue.get("key"),
                            "summary": fields.get("summary", ""),
                            "status": (fields.get("status") or {}).get("name", ""),
                            "priority": (fields.get("priority") or {}).get("name", ""),
                            "assignee": (fields.get("assignee") or {}).get("displayName", "Unassigned"),
                        })
                    return {"status": "ok", "total": data.get("total", 0), "results": issues}
                return {"status": "error", "message": r.text[:300]}
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:200]}

    @server.tool()
    async def update_jira_issue(jira_key: str, updates: dict) -> dict:
        """Update an existing Jira issue (summary, status, priority, assignee)."""
        config = _get_jira_config()
        if not config["base_url"] or not config["email"] or not config["api_token"]:
            return {
                "status": "not_configured",
                "message": "Jira credentials not configured.",
                "jira_key": jira_key,
            }

        try:
            fields: dict = {}
            if "summary" in updates:
                fields["summary"] = updates["summary"]
            if "priority" in updates:
                fields["priority"] = {"name": updates["priority"]}
            if "assignee" in updates:
                fields["assignee"] = {"accountId": updates["assignee"]}

            if not fields:
                return {"status": "error", "message": "No valid fields to update."}

            async with httpx.AsyncClient(timeout=15) as http:
                r = await http.put(
                    f"{config['base_url']}/rest/api/3/issue/{jira_key}",
                    headers=_get_jira_headers(config),
                    json={"fields": fields},
                )
                if r.status_code in (200, 204):
                    return {"status": "ok", "jira_key": jira_key, "updated_fields": list(fields.keys())}
                return {"status": "error", "message": r.text[:300]}
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:200]}

    @server.tool()
    async def list_jira_projects() -> dict:
        """List all accessible Jira projects in the workspace."""
        config = _get_jira_config()
        if not config["base_url"] or not config["email"] or not config["api_token"]:
            return {
                "status": "not_configured",
                "message": "Jira credentials not configured.",
                "projects": [],
            }

        try:
            async with httpx.AsyncClient(timeout=15) as http:
                r = await http.get(
                    f"{config['base_url']}/rest/api/3/project",
                    headers=_get_jira_headers(config),
                )
                if r.status_code == 200:
                    data = r.json()
                    projects = []
                    for proj in data:
                        projects.append({
                            "key": proj.get("key"),
                            "name": proj.get("name"),
                            "style": proj.get("style", ""),
                            "lead": (proj.get("lead") or {}).get("displayName", ""),
                        })
                    return {"status": "ok", "total": len(projects), "projects": projects}
                return {"status": "error", "message": r.text[:300]}
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:200]}

    @server.tool()
    async def list_project_members(project_key: str) -> dict:
        """List all users who can be assigned to issues in a Jira project."""
        config = _get_jira_config()
        if not config["base_url"] or not config["email"] or not config["api_token"]:
            return {
                "status": "not_configured",
                "message": "Jira credentials not configured.",
                "members": [],
            }

        try:
            async with httpx.AsyncClient(timeout=15) as http:
                r = await http.get(
                    f"{config['base_url']}/rest/api/3/user/assignable/search",
                    headers=_get_jira_headers(config),
                    params={"project": project_key, "maxResults": 50},
                )
                if r.status_code == 200:
                    data = r.json()
                    members = []
                    for user in data:
                        members.append({
                            "accountId": user.get("accountId"),
                            "displayName": user.get("displayName", ""),
                            "emailAddress": user.get("emailAddress", ""),
                            "active": user.get("active", True),
                            "avatarUrl": (user.get("avatarUrls") or {}).get("48x48", ""),
                        })
                    return {"status": "ok", "project": project_key, "total": len(members), "members": members}
                return {"status": "error", "message": r.text[:300]}
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:200]}
