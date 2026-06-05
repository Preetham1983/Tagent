from __future__ import annotations

import asyncio
import json as _json
import os
import time
from datetime import timedelta
from pathlib import Path

import httpx
from dotenv import load_dotenv
load_dotenv()

from fastapi import HTTPException, Request
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from tagent.agents.graph import build_agent_graph

app = FastAPI(title="tagent-orchestrator-service")

_raw_origins = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# Build the graph once at startup
_graph = build_agent_graph()


class OrchestrateRequest(BaseModel):
    user_id: str
    thread_id: str
    message: str = Field(min_length=1)


class ApproveRequest(BaseModel):
    thread_id: str
    approved: bool
    user_id: str = ""


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "orchestrator"}


@app.post("/orchestrate")
async def orchestrate(req: OrchestrateRequest) -> dict:
    state = {
        "messages": [{"role": "user", "content": req.message}],
        "intent": None,
        "plan": [],
        "current_step": 0,
        "tool_results": [],
        "approval": None,
        "user_id": req.user_id,
        "thread_id": req.thread_id,
        "memory": [],
    }
    result = await _graph.ainvoke(state, config={"configurable": {"thread_id": req.thread_id}})

    tool_results = result.get("tool_results", [])
    # The final step output is the user-facing response
    response_text = tool_results[-1]["output"] if tool_results else "I'm here to help — ask me anything."

    approval = result.get("approval")
    return {
        "response": response_text,
        "thread_id": req.thread_id,
        "intent": result.get("intent", {}).value if result.get("intent") else None,
        "tool_results": tool_results,
        "approval": {
            "required": bool(approval),
            "description": approval.action_description if approval else None,
            "level": approval.level.value if approval else None,
            "status": approval.status.value if approval else None,
        },
    }


@app.post("/approve")
async def approve(req: ApproveRequest) -> dict:
    """Resume a paused LangGraph workflow after human approval/rejection."""
    from tagent.domain.value_objects.approval import ApprovalStatus

    try:
        # Get the current graph state for this thread
        config = {"configurable": {"thread_id": req.thread_id}}
        current_state = await _graph.aget_state(config)

        if not current_state or not current_state.values:
            raise HTTPException(status_code=404, detail="No paused workflow found for this thread.")

        # Update the approval status
        approval = current_state.values.get("approval")
        if not approval:
            raise HTTPException(status_code=400, detail="No pending approval in this workflow.")

        new_status = ApprovalStatus.APPROVED if req.approved else ApprovalStatus.REJECTED
        approval.status = new_status

        # Resume the graph with updated state
        await _graph.aupdate_state(config, {"approval": approval})
        result = await _graph.ainvoke(None, config=config)

        tool_results = result.get("tool_results", [])
        response_text = tool_results[-1]["output"] if tool_results else "Action completed."

        return {
            "response": response_text,
            "thread_id": req.thread_id,
            "status": "approved" if req.approved else "rejected",
            "tool_results": tool_results,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to resume workflow: {str(exc)[:200]}")


# ── Settings ─────────────────────────────────────────────────────────────────

class JiraSettingsRequest(BaseModel):
    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = ""


def _update_env_file(updates: dict[str, str]) -> None:
    """Update specific keys in the .env file without touching other values."""
    env_path = Path(".env")
    if not env_path.exists():
        with open(env_path, "a", encoding="utf-8") as f:
            for key, value in updates.items():
                f.write(f"{key}={value}\n")
        return

    lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)
    updated_keys: set[str] = set()
    new_lines: list[str] = []

    for line in lines:
        stripped = line.strip()
        if "=" in stripped and not stripped.startswith("#"):
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                new_lines.append(f"{key}={updates[key]}\n")
                updated_keys.add(key)
                continue
        new_lines.append(line)

    for key, value in updates.items():
        if key not in updated_keys:
            new_lines.append(f"{key}={value}\n")

    env_path.write_text("".join(new_lines), encoding="utf-8")


class GoogleCalendarSettingsRequest(BaseModel):
    credentials_path: str = ""


@app.post("/settings/google-calendar")
async def save_google_calendar_settings(req: GoogleCalendarSettingsRequest) -> dict:
    """Save Google Calendar MCP credentials path at runtime."""
    path = req.credentials_path.strip()
    os.environ["GCAL_MCP_OAUTH_CREDENTIALS"] = path
    _update_env_file({"GCAL_MCP_OAUTH_CREDENTIALS": path})
    return {"status": "ok", "message": "Google Calendar credentials path saved"}


# ── Microsoft Teams device-code auth ─────────────────────────────────────────

_MS_TOKEN_CACHE = os.path.join(os.path.expanduser("~"), ".tagent", "ms_graph_token_cache.json")
_MS_SCOPES = "User.Read Chat.ReadWrite Chat.Read ChannelMessage.Send offline_access"


@app.post("/auth/teams/start")
async def start_teams_auth() -> dict:
    """Begin Microsoft device-code flow. Returns user_code + verification_uri for the UI."""
    from tagent.infrastructure.config.settings import Settings
    s = Settings()

    if not s.ms_client_id or not s.ms_tenant_id:
        raise HTTPException(
            status_code=400,
            detail="MS_CLIENT_ID and MS_TENANT_ID must be set in the orchestrator .env before signing in.",
        )

    async with httpx.AsyncClient(timeout=15) as http:
        r = await http.post(
            f"https://login.microsoftonline.com/{s.ms_tenant_id}/oauth2/v2.0/devicecode",
            data={"client_id": s.ms_client_id, "scope": _MS_SCOPES},
        )

    if r.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Azure AD error: {r.text[:300]}")

    data = r.json()
    return {
        "user_code": data["user_code"],
        "verification_uri": data["verification_uri"],
        "expires_in": data.get("expires_in", 900),
        "interval": data.get("interval", 5),
        "device_code": data["device_code"],
    }


@app.post("/auth/teams/poll")
async def poll_teams_auth(req: Request) -> dict:
    """Poll Azure AD to check if the user completed the device-code sign-in."""
    from tagent.infrastructure.config.settings import Settings
    s = Settings()

    body = await req.json()
    device_code = (body.get("device_code") or "").strip()
    if not device_code:
        raise HTTPException(status_code=400, detail="device_code is required")

    async with httpx.AsyncClient(timeout=15) as http:
        r = await http.post(
            f"https://login.microsoftonline.com/{s.ms_tenant_id}/oauth2/v2.0/token",
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
                "device_code": device_code,
                "client_id": s.ms_client_id,
            },
        )

    data = r.json()
    error = data.get("error", "")

    if error in ("authorization_pending", "slow_down"):
        return {"status": "pending"}
    if error:
        return {"status": "error", "message": data.get("error_description", error)[:200]}

    if "access_token" in data:
        cache = {
            "access_token": data["access_token"],
            "refresh_token": data.get("refresh_token", ""),
            "token_expiry": time.time() + data.get("expires_in", 3600),
            "tenant_id": s.ms_tenant_id,
            "client_id": s.ms_client_id,
            "scopes": data.get("scope", _MS_SCOPES),
            "updated_at": int(time.time()),
        }
        os.makedirs(os.path.dirname(_MS_TOKEN_CACHE), exist_ok=True)
        with open(_MS_TOKEN_CACHE, "w", encoding="utf-8") as f:
            _json.dump(cache, f, indent=2)
        return {"status": "ok", "message": "Microsoft Teams connected successfully!"}

    return {"status": "error", "message": "Unexpected response from Azure AD"}


@app.post("/settings/jira")
async def save_jira_settings(req: JiraSettingsRequest) -> dict:
    """Save Jira credentials at runtime so the MCP subprocess inherits them."""
    os.environ["JIRA_BASE_URL"] = req.jira_base_url.rstrip("/")
    os.environ["JIRA_EMAIL"] = req.jira_email
    os.environ["JIRA_API_TOKEN"] = req.jira_api_token
    os.environ["JIRA_PROJECT_KEY"] = req.jira_project_key

    _update_env_file(
        {
            "JIRA_BASE_URL": req.jira_base_url.rstrip("/"),
            "JIRA_EMAIL": req.jira_email,
            "JIRA_API_TOKEN": req.jira_api_token,
            "JIRA_PROJECT_KEY": req.jira_project_key,
        }
    )
    return {"status": "ok", "message": "Jira credentials saved"}


@app.get("/settings/status")
async def get_settings_status() -> dict:
    """Return integration connection status (no secrets exposed)."""
    from tagent.infrastructure.config.settings import Settings

    s = Settings()

    jira_configured = bool(
        os.environ.get("JIRA_BASE_URL") and
        os.environ.get("JIRA_EMAIL") and
        os.environ.get("JIRA_API_TOKEN")
    )

    teams_configured = bool(s.ms_tenant_id and s.ms_client_id and s.ms_client_secret)
    tenant_preview = (s.ms_tenant_id[:8] + "…") if s.ms_tenant_id else ""
    teams_session_active = os.path.isfile(_MS_TOKEN_CACHE)
    # can_auth = app creds set so device-code flow is available
    teams_can_auth = bool(s.ms_tenant_id and s.ms_client_id)

    return {
        "jira": {
            "configured": jira_configured,
            "base_url": os.environ.get("JIRA_BASE_URL", s.jira_base_url),
            "email": os.environ.get("JIRA_EMAIL", s.jira_email),
            "project_key": os.environ.get("JIRA_PROJECT_KEY", s.jira_project_key),
        },
        "teams": {
            "configured": teams_configured,
            "session_active": teams_session_active,
            "can_auth": teams_can_auth,
            "tenant_id": tenant_preview,
        },
        "calendar": {
            "configured": teams_configured,
            "timezone": _load_user_prefs().get("calendar_timezone", "India Standard Time"),
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
            "configured": bool(s.gcal_mcp_oauth_credentials and os.path.isfile(s.gcal_mcp_oauth_credentials)),
            "calendar_id": os.environ.get("GOOGLE_CALENDAR_ID", "primary"),
        },
    }


# ── User preferences (timezone etc.) ─────────────────────────────────────────

def _prefs_path() -> str:
    return os.path.join(os.path.expanduser("~"), ".tagent", "user_preferences.json")


def _load_user_prefs() -> dict:
    try:
        import json as _json
        with open(_prefs_path(), "r", encoding="utf-8") as f:
            return _json.load(f)
    except (FileNotFoundError, Exception):
        return {}


def _save_user_prefs(updates: dict) -> None:
    import json as _json
    prefs = _load_user_prefs()
    prefs.update(updates)
    os.makedirs(os.path.dirname(_prefs_path()), exist_ok=True)
    with open(_prefs_path(), "w", encoding="utf-8") as f:
        _json.dump(prefs, f, indent=2)


class CalendarSettingsRequest(BaseModel):
    timezone: str


@app.post("/settings/calendar")
async def save_calendar_settings(req: CalendarSettingsRequest) -> dict:
    """Save the user's preferred calendar timezone."""
    _save_user_prefs({"calendar_timezone": req.timezone})
    return {"status": "ok", "timezone": req.timezone}


@app.get("/settings/calendar")
async def get_calendar_settings() -> dict:
    """Return the saved calendar timezone preference."""
    tz = _load_user_prefs().get("calendar_timezone", "India Standard Time")
    return {"timezone": tz}


# ── Direct tool call (bypasses LLM classification) ───────────────────────────

class DirectToolRequest(BaseModel):
    tool_name: str
    query: str = ""
    jql: str = ""
    title: str = ""
    description: str = ""
    priority: str = "Medium"
    user_id: str = ""


@app.post("/tool/call")
async def call_tool_direct(req: DirectToolRequest) -> dict:
    """Call an MCP tool directly by name, bypassing classification/planning."""
    import json

    _TOOL_TIMEOUT = 60  # seconds
    import re as _re

    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client

    from tagent.infrastructure.adapters.external_mcp_adapter import get_external_mcp_adapter
    from tagent.infrastructure.adapters.llm_adapter import get_default_adapter
    from tagent.infrastructure.config.settings import Settings

    s = Settings()
    tool_name = req.tool_name

    # ── Google Calendar — handled independently, no mcp_external_enabled needed ───
    if tool_name in ("list_google_calendar_events", "list-events",
                     "create_google_calendar_event", "create-event",
                     "search_google_calendar_events", "search-events"):
        from tagent.infrastructure.adapters.google_calendar_mcp_adapter import get_google_calendar_mcp_adapter
        gcal = get_google_calendar_mcp_adapter()
        llm = get_default_adapter()

        if tool_name in ("list_google_calendar_events", "list-events"):
            gcal_args: dict = {}
            if req.query:
                gcal_args["timeMin"] = req.query
            mcp_result = await asyncio.wait_for(gcal.call_tool("list-events", gcal_args), timeout=_TOOL_TIMEOUT)
            if mcp_result.get("status") in ("not_configured", "error"):
                raise HTTPException(status_code=400, detail=mcp_result.get("message", "Google Calendar error"))
            formatted = await llm.complete([
                {"role": "system", "content": (
                    "You are Tagent. Format the Google Calendar events into a clean schedule. "
                    "Show start time, title, location, and any Google Meet link. "
                    "If no events, say the calendar is clear."
                )},
                {"role": "user", "content": f"Result:\n{json.dumps(mcp_result, indent=2)}"},
            ])
            return {"status": "ok", "tool": tool_name, "response": formatted, "raw": mcp_result}

        elif tool_name in ("search_google_calendar_events", "search-events"):
            mcp_result = await asyncio.wait_for(gcal.call_tool("search-events", {"query": req.query or ""}), timeout=_TOOL_TIMEOUT)
            if mcp_result.get("status") in ("not_configured", "error"):
                raise HTTPException(status_code=400, detail=mcp_result.get("message", "Google Calendar error"))
            formatted = await llm.complete([
                {"role": "system", "content": "You are Tagent. Format the Google Calendar search results into a readable list."},
                {"role": "user", "content": f"Result:\n{json.dumps(mcp_result, indent=2)}"},
            ])
            return {"status": "ok", "tool": tool_name, "response": formatted, "raw": mcp_result}

        else:  # create-event
            from datetime import datetime, timedelta
            raw_q = (req.query or "").strip()

            # Extract attendee emails
            attendee_emails = _re.findall(r'[\w.\-+]+@[\w.\-]+\.\w+', raw_q)

            # Extract time (e.g. "11 am", "2:30pm", "14:00")
            time_match = _re.search(
                r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)|\b(\d{2}):(\d{2})\b',
                raw_q, _re.IGNORECASE
            )
            now = datetime.now()
            if time_match:
                if time_match.group(4):  # 24h format
                    h, m = int(time_match.group(4)), int(time_match.group(5))
                else:
                    h = int(time_match.group(1))
                    m = int(time_match.group(2) or 0)
                    meridiem = (time_match.group(3) or "").lower()
                    if meridiem == "pm" and h != 12:
                        h += 12
                    elif meridiem == "am" and h == 12:
                        h = 0
            else:
                h, m = now.hour + 1, 0  # default: next hour

            start_dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
            end_dt = start_dt + timedelta(hours=1)
            start_iso = start_dt.strftime("%Y-%m-%dT%H:%M:%S")
            end_iso = end_dt.strftime("%Y-%m-%dT%H:%M:%S")

            # Build title: strip email and time text
            title_raw = _re.sub(r'[\w.\-+]+@[\w.\-]+\.\w+', '', raw_q)
            title_raw = _re.sub(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)|\b(\d{2}):(\d{2})\b', '', title_raw, flags=_re.IGNORECASE)
            title_raw = _re.sub(r'\b(schedule|meet|meeting|at|today|email|with|a)\b', '', title_raw, flags=_re.IGNORECASE)
            title_raw = _re.sub(r'[:\-]+', ' ', title_raw).strip()
            title = (req.title or title_raw or "Meeting").strip()[:100] or "Meeting"

            gcal_args = {
                "summary": title,
                "start": start_iso,
                "end": end_iso,
                "attendees": attendee_emails,
                "conferenceData": True,  # creates Google Meet link
            }
            if req.description:
                gcal_args["description"] = req.description

            mcp_result = await asyncio.wait_for(gcal.call_tool("create-event", gcal_args), timeout=_TOOL_TIMEOUT)
            if mcp_result.get("status") in ("not_configured", "error"):
                raise HTTPException(status_code=400, detail=mcp_result.get("message", "Google Calendar error"))
            formatted = await llm.complete([
                {"role": "system", "content": (
                    "You are Tagent. Confirm the Google Calendar event was created. "
                    "Show the title, time, attendees, and the Google Meet link if available."
                )},
                {"role": "user", "content": f"Result:\n{json.dumps(mcp_result, indent=2)}"},
            ])
            return {"status": "ok", "tool": tool_name, "response": formatted, "raw": mcp_result}

    # ── DACL Business Rules — external SSE MCP at localhost:8080 ─────────────
    _DACL_TOOLS = {"validate_business_rule", "list_available_policies"}
    if tool_name in _DACL_TOOLS:
        from mcp.client.sse import sse_client
        from mcp.client.session import ClientSession as _SSEClientSession

        llm = get_default_adapter()
        dacl_url = s.dacl_mcp_url or "http://localhost:8080/sse"
        dacl_key = s.dacl_mcp_api_key or ""
        dacl_headers: dict[str, str] = {}
        if dacl_key:
            dacl_headers["X-API-Key"] = dacl_key
        # When routing through host.docker.internal the server sees the wrong Host header
        # and returns 421 Misdirected Request — override it to what the server expects.
        if "host.docker.internal" in dacl_url:
            from urllib.parse import urlparse as _urlparse
            _p = _urlparse(dacl_url)
            dacl_headers["Host"] = f"localhost:{_p.port}" if _p.port else "localhost"

        # Build arguments from req.query
        tool_args: dict = {}
        if tool_name == "validate_business_rule" and req.query:
            raw_q = req.query.strip()
            # Support JSON input: {"age": 24, "tier": "BASIC", ...}
            try:
                tool_args = json.loads(raw_q)
            except json.JSONDecodeError:
                # Support key=value pairs: age=24, tier=BASIC, conditions=0
                import re as _re
                for part in _re.split(r"[,;]\s*", raw_q):
                    kv = part.strip().split("=", 1)
                    if len(kv) == 2:
                        k, v = kv[0].strip(), kv[1].strip()
                        # Coerce obvious integers
                        tool_args[k] = int(v) if v.lstrip("-").isdigit() else v
                if not tool_args:
                    tool_args = {"input": raw_q}

        async def _run_dacl() -> dict:
            async with sse_client(dacl_url, headers=dacl_headers) as (r, w):
                async with _SSEClientSession(r, w) as sess:
                    await sess.initialize()
                    mcp_res = await sess.call_tool(tool_name, tool_args)
                    
                    # Try to get text content
                    parts = []
                    for item in mcp_res.content:
                        text = getattr(item, "text", None)
                        if isinstance(text, str) and text.strip():
                            parts.append(text.strip())
                    
                    # If we have structured content but no text, use that
                    raw_output = "\n".join(parts)
                    if not raw_output and hasattr(mcp_res, "isError") and not mcp_res.isError:
                        # Fallback for tools that return structured data (like list_available_policies)
                        # The SDK result might have a model_dump()
                        data = mcp_res.model_dump()
                        if data.get("content"):
                             pass # already tried
                        elif tool_name == "list_available_policies":
                             # Specific fallback for this tool if needed
                             pass
                    
                    return {"raw": raw_output or json.dumps(mcp_res.model_dump(), indent=2)}

        try:
            dacl_data = await asyncio.wait_for(_run_dacl(), timeout=30)
        except asyncio.TimeoutError:
            raise HTTPException(status_code=504, detail="DACL MCP server timed out.")
        except Exception as exc:
            # Handle ExceptionGroup (Python 3.11+) to reveal sub-exceptions
            error_msg = str(exc)
            if hasattr(exc, "exceptions"):
                sub_errors = [str(e) for e in exc.exceptions]
                error_msg = f"{error_msg} | Sub-errors: {', '.join(sub_errors)}"
            
            raise HTTPException(status_code=502, detail=f"DACL MCP error: {error_msg[:500]}")

        formatted = await llm.complete([
            {
                "role": "system",
                "content": (
                    "You are Tagent, an enterprise AI assistant. "
                    "The user just called the DACL business rule engine. "
                    "Format the result clearly: show the calculated premium, "
                    "the tier, any conditions applied, and what the result means in plain English. "
                    "If it is a policy list, format it as a clean numbered or bulleted list."
                ),
            },
            {
                "role": "user",
                "content": f"Tool: {tool_name}\nArgs: {json.dumps(tool_args)}\nResult:\n{dacl_data['raw']}",
            },
        ])
        return {"status": "ok", "tool": tool_name, "response": formatted, "raw": dacl_data["raw"]}

    if not s.mcp_external_enabled:
        raise HTTPException(status_code=503, detail="MCP tools not enabled.")

    adapter = get_external_mcp_adapter()
    if not adapter.enabled():
        raise HTTPException(status_code=503, detail="MCP adapter not configured.")

    jira_project = os.environ.get("JIRA_PROJECT_KEY", "ITP")
    tool_name = req.tool_name

    # Build MCP tool arguments
    args: dict = {}
    if tool_name == "list_jira_projects":
        args = {}
    elif tool_name == "list_project_members":
        args = {"project_key": req.query or jira_project}
    elif tool_name == "list_jira_issues":
        tool_name = "search_jira_issues"
        args = {"jql": f"project = {jira_project} ORDER BY created DESC"}
    elif tool_name == "search_jira_issues":
        raw_query = req.jql or req.query or ""
        # If it looks like free text rather than JQL, wrap it
        if raw_query and "=" not in raw_query and "ORDER BY" not in raw_query.upper():
            jql = f'project = {jira_project} AND text ~ "{raw_query}" ORDER BY created DESC'
        elif raw_query:
            jql = raw_query
        else:
            jql = f"project = {jira_project} ORDER BY created DESC"
        args = {"jql": jql}
    elif tool_name == "search_closed_issues":
        tool_name = "search_jira_issues"
        args = {"jql": f"project = {jira_project} AND status = Done ORDER BY updated DESC"}
    elif tool_name == "create_jira_issue":
        args = {
            "title": req.title or req.query or "New task",
            "description": req.description or req.query,
            "priority": req.priority,
        }
    # ── GitHub ──────────────────────────────────────────────────────────────
    elif tool_name == "list_github_repos":
        args = {"owner": req.query or ""}
    elif tool_name == "list_github_prs":
        args = {"state": req.query or "open"}
    elif tool_name == "list_github_issues":
        args = {"state": req.query or "open"}
    elif tool_name == "create_github_issue":
        args = {
            "title": req.title or req.query or "New issue",
            "body": req.description or "",
            "labels": "",
        }
    # ── Notion ───────────────────────────────────────────────────────────────
    elif tool_name == "search_notion":
        args = {"query": req.query or ""}
    elif tool_name == "list_notion_pages":
        args = {}
    elif tool_name == "create_notion_page":
        args = {
            "title": req.title or req.query or "New page",
            "content": req.description or "",
        }
    # ── Teams / Microsoft 365 ────────────────────────────────────────────────
    elif tool_name == "send_direct_message":
        # Accept formats: "email - message", "name - message", or just "email"
        import re as _re
        raw_query = (req.query or "").strip()
        email_match = _re.search(r'[\w.\-+]+@[\w.\-]+\.\w+', raw_query)
        if email_match:
            recipient = email_match.group(0)
            rest = _re.sub(r'[\w.\-+]+@[\w.\-]+\.\w+', "", raw_query).strip().lstrip("-").strip()
            msg_body = rest if rest else "Hello!"
        else:
            # No email — split on first " - " to separate name from message
            parts = _re.split(r'\s*-\s*', raw_query, maxsplit=1)
            recipient = parts[0].strip()  # could be a display name
            msg_body = parts[1].strip() if len(parts) > 1 else "Hello!"
        args = {
            "recipient_email": recipient,  # tool now accepts name OR email
            "message": msg_body,
        }
    elif tool_name == "schedule_meeting":
        raw = req.query or ""
        # Extract attendee emails
        import re as _re
        from datetime import datetime as _dt
        _attendees = _re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', raw)
        # Extract title from desc:/topic:/subject: keyword
        _title_m = _re.search(r'(?:desc(?:ription)?|topic|subject|title)\s*[:\-]\s*(.+?)(?:\s*$|\n)', raw, _re.IGNORECASE)
        _title = _title_m.group(1).strip() if _title_m else ""
        if not _title:
            # Fallback: strip emails, time phrases, keywords → leftover is title
            _title = _re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '', raw)
            _title = _re.sub(r'\b(?:at|on|pm|am|schedule|meet(?:ing)?|a|with|hey|desc|topic)\b', ' ', _title, flags=_re.IGNORECASE)
            _title = " ".join(_title.split()) or "Teams Meeting"
        # Parse start time from natural language
        _raw_l = raw.lower()
        _start_time = ""
        # ISO passthrough
        _iso_m = _re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?)', raw)
        if _iso_m:
            _start_time = _iso_m.group(1)
            if _start_time.count(":") == 1:
                _start_time += ":00"
        else:
            _tm = _re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', _raw_l)
            if _tm:
                _h, _m, _mer = int(_tm.group(1)), int(_tm.group(2) or 0), _tm.group(3)
                if _mer == "pm" and _h != 12: _h += 12
                elif _mer == "am" and _h == 12: _h = 0
                _MONTHS = {"jan":1,"feb":2,"mar":3,"apr":4,"may":5,"jun":6,"jul":7,"aug":8,"sep":9,"oct":10,"nov":11,"dec":12,
                           "january":1,"february":2,"march":3,"april":4,"june":6,"july":7,"august":8,"september":9,"october":10,"november":11,"december":12}
                _now = _dt.now()
                _day, _mon, _yr = _now.day, _now.month, _now.year
                _dm = _re.search(r'(\d{1,2})(?:st|nd|rd|th)?\s+(' + '|'.join(_MONTHS) + r')', _raw_l)
                _md = _re.search(r'(' + '|'.join(_MONTHS) + r')\s+(\d{1,2})(?:st|nd|rd|th)?', _raw_l)
                if _dm:
                    _day, _mon = int(_dm.group(1)), _MONTHS[_dm.group(2)]
                elif _md:
                    _mon, _day = _MONTHS[_md.group(1)], int(_md.group(2))
                try:
                    _cand = _dt(_yr, _mon, _day, _h, _m)
                    if _cand < _now: _cand = _cand.replace(year=_yr + 1)
                    _start_time = _cand.strftime("%Y-%m-%dT%H:%M:%S")
                except ValueError:
                    pass
        if not _start_time:
            _start_time = _dt.now().strftime("%Y-%m-%dT%H:%M:%S")
        args = {
            "attendee_ids": _attendees,
            "title": _title,
            "start_time": _start_time,
            "duration_minutes": 30,
        }
    elif tool_name == "list_calendar_events":
        args = {}
    elif tool_name == "get_user_info":
        args = {}
    elif tool_name == "search_user":
        args = {"name": req.query or ""}
    elif tool_name == "list_recent_chats":
        args = {"top": 10}
    elif tool_name == "read_chat_messages":
        args = {"chat_id": req.query or "", "top": 20}
    elif tool_name == "get_meeting_attendance":
        args = {"meeting_subject": req.query or ""}
    elif tool_name == "get_meeting_transcript":
        args = {"meeting_subject": req.query or ""}
    elif tool_name == "analyze_meeting":
        args = {"meeting_subject": req.query or ""}
    elif tool_name == "get_daily_briefing":
        args = {}
    elif tool_name == "generate_standup":
        args = {}
    elif tool_name == "nudge_colleague":
        parts = [p.strip() for p in (req.query or "").split(",", 1)]
        args = {
            "colleague_name": parts[0] if parts else "",
            "item_id": parts[1] if len(parts) > 1 else "Task"
        }
    elif tool_name == "chat_to_jira":
        args = {"colleague_name": req.query or ""}
    elif tool_name == "negotiate_meeting":
        parts = [p.strip() for p in (req.query or "").split(",", 1)]
        args = {
            "colleague_name": parts[0] if parts else "",
            "topic": parts[1] if len(parts) > 1 else "Quick Sync"
        }
    elif tool_name == "smart_ooo_handoff":
        parts = [p.strip() for p in (req.query or "").split(",", 2)]
        args = {
            "backup_colleague_name": parts[0] if parts else "",
            "start_date": parts[1] if len(parts) > 1 else "soon",
            "end_date": parts[2] if len(parts) > 2 else "later"
        }
    elif tool_name == "analyze_onedrive_transcript":
        args = {"meeting_name": req.query or ""}
    else:
        args = {"query": req.query} if req.query else {}

    # Call the MCP subprocess directly
    # Give enough time for: uv process boot (~5s) + Jira/GCal HTTP call (~10s) + LLM format (~10s)
    env = os.environ.copy()
    params = StdioServerParameters(
        command=adapter._command,
        args=adapter._args,
        cwd=adapter._cwd,
        env=env,
    )

    async def _run_mcp_and_format() -> dict:
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(
                    tool_name,
                    args,
                )
                parts = [
                    item.text
                    for item in result.content
                    if hasattr(item, "text") and item.text
                ]
                raw_text = "\n".join(parts)
                try:
                    mcp_data = json.loads(raw_text)
                except json.JSONDecodeError:
                    mcp_data = {"output": raw_text}

        if mcp_data.get("status") == "not_configured":
            msg = mcp_data.get("message", "Credentials not configured. Open Settings in the UI.")
            raise HTTPException(status_code=400, detail=msg)
        if mcp_data.get("status") == "error":
            raise HTTPException(status_code=400, detail=mcp_data.get("message", "Tool execution error"))

        # Format the raw tool data into a human-readable response
        llm = get_default_adapter()
        if tool_name == "get_daily_briefing":
            system = (
                "You are Tagent, a smart enterprise AI assistant. "
                "The user has requested their Smart Daily Briefing. Format the JSON data below into a beautiful, "
                "personalised morning briefing using rich markdown.\n"
                "Structure it exactly like this:\n"
                "1. Start with a warm greeting using the person's first name and today's date (bold the date).\n"
                "2. ## 📅 Today's Schedule — list each meeting as `HH:MM AM/PM – Title` on its own line. "
                "If it has a Teams link mark it with 🔗. If no meetings, say 'You have a clear schedule today — make the most of it! ✨'\n"
                "3. ## 🎯 Your Jira Issues — group by status (In Progress first). Show key + summary. "
                "If none, say 'No open Jira issues — inbox zero! 🎉'\n"
                "4. ## 🔀 Pull Requests — "
                "If github_configured is false, write: 'GitHub not connected — add your token in Settings ⚙️'. "
                "If github_configured is true but no PRs, write: 'No open pull requests — all clear! ✅'. "
                "Otherwise list each PR as: #N **title** (draft if applicable) by author\n"
                "5. ## 💬 Recent Teams Chats — show the last 3-5 conversations with a short preview. "
                "If none, skip this section.\n"
                "6. End with a short motivational one-liner.\n"
                "Be warm, concise, and professional. Only include sections that have data."
            )
        elif tool_name == "generate_standup":
            system = (
                "You are Tagent. Format the JSON data below into a clean daily standup message "
                "ready to copy-paste into Teams or Slack.\n"
                "Use EXACTLY this structure:\n"
                "**Yesterday** \n"
                "- List each completed Jira issue as: [KEY] Summary\n"
                "- If no issues, write: No tickets closed yesterday\n\n"
                "**Today** \n"
                "- List each In Progress Jira issue as: [KEY] Summary\n"
                "- List today's meetings as: 📅 HH:MM AM/PM – Meeting title\n"
                "- List open PRs as: 🔀 #N PR title\n"
                "- If nothing, write: No active work items\n\n"
                "**Blockers** \n"
                "- List blocked issues. If none, write: None\n\n"
                "Keep it SHORT and scannable. No extra commentary. "
                "People should be able to read this in under 10 seconds."
            )
        elif tool_name == "analyze_meeting":
            system = (
                "You are Tagent, an enterprise AI assistant that analyzes meetings. "
                "The user asked you to analyze a Teams meeting. You have been given meeting metadata "
                "(subject, time, attendees) AND the meeting chat messages that were sent during the meeting.\n\n"
                "Generate a comprehensive, well-structured meeting analysis using this format:\n\n"
                "## 🧠 Meeting Analysis: [Subject]\n"
                "**Date**: [formatted date] | **Duration**: [calculated] | **Organizer**: [name]\n\n"
                "### 👥 Participants ([count])\n"
                "List each attendee with their response status (✅ accepted, ❌ declined, ❓ tentative)\n\n"
                "### 📋 Agenda\n"
                "If agenda/body text exists, summarize it. If not, say 'No formal agenda was set.'\n\n"
                "### 💬 Discussion Summary\n"
                "Analyze the chat messages and write a coherent summary of what was discussed. "
                "Group by topic if possible. Include who said what for key points.\n\n"
                "### 🎯 Key Decisions\n"
                "Extract any decisions that were made (or say 'No explicit decisions captured in chat')\n\n"
                "### ✅ Action Items\n"
                "Extract any action items, tasks, or follow-ups mentioned. Format as:\n"
                "- [ ] **[Person]**: [action item]\n\n"
                "### 📊 Meeting Health\n"
                "Give a brief assessment: was the meeting productive based on the chat activity? "
                "Mention message count, participation level, etc.\n\n"
                "If there are no chat messages, mention that the discussion likely happened via voice/video "
                "and only metadata is available. Still provide what analysis you can from attendees and agenda.\n"
                "Be professional, factual, and insightful. Only report what the data supports."
            )
        elif tool_name == "nudge_colleague":
            system = (
                "You are Tagent. The user asked to nudge a colleague. "
                "If the action succeeded, reply with a short, celebratory message confirming the DM was sent. "
                "If it failed, explain the error clearly."
            )
        elif tool_name == "negotiate_meeting":
            system = (
                "You are Tagent. The user asked to find a gap and negotiate a meeting with a colleague. "
                "If it succeeded, summarize the proposed time that was found and sent to the colleague. "
                "If it failed, explain why."
            )
        elif tool_name == "chat_to_jira":
            system = (
                "You are Tagent. The user wants to convert a recent chat with a colleague into a Jira Ticket.\n"
                "You are given the 'chat_context' which contains recent messages.\n"
                "Analyze the chat and generate a PERFECT, ready-to-use Jira ticket format using Markdown.\n\n"
                "## 🎫 Suggested Jira Ticket\n"
                "**Title**: [A concise, professional title based on the chat]\n"
                "**Issue Type**: [Task/Story/Bug]\n\n"
                "**Description**:\n"
                "[A well-written professional description synthesizing what was discussed]\n\n"
                "**Acceptance Criteria**:\n"
                "- [ ] [Criteria 1]\n"
                "- [ ] [Criteria 2]\n\n"
                "**Priority**: [Infer from chat]\n\n"
                "Add a small note at the end saying: *'If this looks good, tell me to create this ticket!'*\n"
                "Note: Do not actually create the ticket, just propose the format."
            )
        elif tool_name == "smart_ooo_handoff":
            system = (
                "You are Tagent. The user asked to hand off their active Jira tickets to a colleague for OOO coverage.\n"
                "If it succeeded, list out the tickets that were handed off and confirm the DM was sent.\n"
                "If it failed, explain the error clearly."
            )
        elif tool_name == "analyze_onedrive_transcript":
            system = (
                "You are Tagent, an enterprise AI assistant. "
                "You have been provided with the raw transcript text of a meeting downloaded directly from OneDrive.\n\n"
                "Generate a comprehensive, well-structured meeting analysis using this format:\n\n"
                "## 🧠 Transcript Analysis: [Meeting Name]\n"
                "**Source**: [File Name]\n\n"
                "### 💬 Detailed Summary\n"
                "Write a highly detailed summary of the meeting based purely on the spoken words in the transcript. "
                "Group by topic discussed.\n\n"
                "### 🎯 Key Decisions\n"
                "Extract any explicitly stated decisions.\n\n"
                "### ✅ Action Items\n"
                "Extract any action items, tasks, or follow-ups mentioned. Format as:\n"
                "- [ ] **[Person]**: [action item]\n\n"
                "If the transcript is empty or could not be found, explain the error cleanly."
            )
        else:
            system = (
                "You are Tagent, an enterprise AI assistant. "
                "Format the following live API result into a clean, concise, and helpful response. "
                "Use markdown where appropriate (bolding, bullet lists). Be factual — only report what is in the data."
            )
        formatted = await llm.complete([
            {"role": "system", "content": system},
            {
                "role": "user",
                "content": f"Tool: {tool_name}\nArgs: {json.dumps(args)}\nResult:\n{json.dumps(mcp_data, indent=2)}",
            },
        ])
        return {"status": "ok", "tool": tool_name, "response": formatted, "raw": mcp_data}

    try:
        return await asyncio.wait_for(_run_mcp_and_format(), timeout=_TOOL_TIMEOUT)
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"Tool '{tool_name}' timed out after {_TOOL_TIMEOUT}s. The MCP service may be slow to start — try again.",
        )
    except HTTPException:
        raise
    except BaseException as exc:
        import traceback as _tb
        _tb.print_exc()
        # Unwrap ExceptionGroup / BaseExceptionGroup to get the real cause
        cause = exc
        if hasattr(exc, "exceptions") and exc.exceptions:
            cause = exc.exceptions[0]
        raise HTTPException(status_code=500, detail=f"Tool call failed: {str(cause)[:300]}")

