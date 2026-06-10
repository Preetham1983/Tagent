"""Direct tool-call endpoint — bypasses LLM classification/planning."""

from __future__ import annotations

import asyncio
import json
import os

from fastapi import APIRouter, HTTPException

from tagent.api.schemas import DirectToolRequest
from tagent.application.services.tool_args_builder import build_tool_args
from tagent.application.services.tool_response_formatter import get_system_prompt

router = APIRouter()

_TOOL_TIMEOUT = 60  # seconds

_GCAL_TOOLS = {
    "list_google_calendar_events", "list-events",
    "create_google_calendar_event", "create-event",
    "search_google_calendar_events", "search-events",
}
_DACL_TOOLS = {"validate_business_rule", "list_available_policies"}

# Map tool names to intents for BRN validation
_TOOL_TO_INTENT = {
    "list_jira_issues": "query_tasks",
    "search_jira_issues": "query_tasks",
    "search_closed_issues": "query_tasks",
    "create_jira_issue": "create_task",
    "list_calendar_events": "query_calendar",
    "schedule_meeting": "schedule_meeting",
    "send_direct_message": "send_message",
    "get_user_info": "get_user_info",
    "search_user": "get_user_info",
    "list_google_calendar_events": "query_calendar",
    "create_google_calendar_event": "schedule_meeting",
    "search_google_calendar_events": "query_calendar",
    "validate_business_rule": "validate_rule",
    "list_available_policies": "validate_rule",
}


async def _validate_tool_with_brn(
    tool_name: str, 
    user_role: str = "authenticated_user",
    user_tier: str = "professional"
) -> dict:
    """Validate a tool call against BRN policy engine."""
    from tagent.agents.nodes.executor import _call_dacl_mcp_tool
    from tagent.domain.value_objects.intent import Intent
    
    # Map tool to intent
    intent_str = _TOOL_TO_INTENT.get(tool_name, "general_chat")
    
    # Build DACL query
    action_map = {
        "query_tasks": "search",
        "create_task": "create",
        "query_calendar": "read",
        "schedule_meeting": "schedule",
        "send_message": "notify",
        "get_user_info": "read",
        "validate_rule": "validate",
    }
    
    integration_map = {
        "query_tasks": "jira",
        "create_task": "jira",
        "query_calendar": "ms365_calendar",
        "schedule_meeting": "ms365_calendar",
        "send_message": "teams",
        "get_user_info": "ms_graph",
        "validate_rule": "dacl_engine",
    }
    
    action_type = action_map.get(intent_str, "read")
    integration = integration_map.get(intent_str, "memory")
    
    query = (
        f"user_role={user_role} "
        f"integration={integration} "
        f"action_type={action_type} "
        f"query_intent={intent_str} "
        f"mcp_tool={tool_name} "
        f"confidence=very_high "
        f"approval_level=auto "
        f"user_tier={user_tier} "
        f"context_turns=turns_1_3 "
        f"time_context=business_hours"
    )
    
    raw = await _call_dacl_mcp_tool(
        "validate_business_rule",
        {"domain": "agents", "query": query},
    )
    
    if raw is None or raw.get("status") == "error":
        # DACL unavailable — fail-open
        return {
            "enabled": False,
            "intent_check": {
                "passed": True,
                "policy_name": f"TAGENT_POLICY_{intent_str.upper()}_UNAVAILABLE",
                "allowed": "yes",
                "auto_execute": "yes",
            }
        }
    
    # Parse DACL response
    result: dict = {}
    output = raw.get("output", "")
    
    if isinstance(output, dict):
        result = output
    elif isinstance(output, str) and "|" in output:
        parts = output.split("|")
        if len(parts) >= 4:
            for kv in parts[3].split(","):
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    result[k.strip()] = v.strip()
    elif isinstance(raw, dict):
        result = {k: v for k, v in raw.items() if k != "status"}
    
    policy_name = result.get("policy_name", f"TAGENT_POLICY_{intent_str.upper()}")
    allowed = result.get("allowed", "yes")
    
    return {
        "enabled": True,
        "intent_check": {
            "passed": allowed == "yes",
            "policy_name": policy_name,
            "allowed": allowed,
            "auto_execute": result.get("auto_execute", "yes"),
        }
    }


@router.post("/tool/call")
async def call_tool_direct(req: DirectToolRequest) -> dict:
    """Call an MCP tool directly by name with BRN validation."""
    from tagent.infrastructure.adapters.llm_adapter import get_default_adapter
    from tagent.infrastructure.config.settings import Settings

    s = Settings()
    
    # Validate tool call with BRN
    brn_validation = await _validate_tool_with_brn(
        req.tool_name,
        user_role="authenticated_user",  # TODO: Pass from request
        user_tier="professional",        # TODO: Pass from request
    )
    
    # Block if BRN says no
    if not brn_validation["intent_check"]["passed"]:
        policy_name = brn_validation["intent_check"]["policy_name"]
        return {
            "status": "blocked",
            "tool": req.tool_name,
            "response": (
                f"🚫 **Action Blocked by BRN Policy**\n\n"
                f"Your request was blocked by the business rules network.\n\n"
                f"**Policy:** {policy_name}\n"
                f"**Tool:** {req.tool_name}\n\n"
                f"Please refine your request or contact an administrator for assistance."
            ),
            "brn_validation": brn_validation,
        }

    if req.tool_name in _GCAL_TOOLS:
        result = await _handle_gcal(req, s)
        result["brn_validation"] = brn_validation
        return result

    if req.tool_name in _DACL_TOOLS:
        result = await _handle_dacl(req, s)
        result["brn_validation"] = brn_validation
        return result

    result = await _handle_mcp(req, s)
    result["brn_validation"] = brn_validation
    return result


# ── Google Calendar ────────────────────────────────────────────────────────────

async def _handle_gcal(req: DirectToolRequest, s) -> dict:
    from tagent.infrastructure.adapters.google_calendar_mcp_adapter import get_google_calendar_mcp_adapter
    from tagent.infrastructure.adapters.llm_adapter import get_default_adapter

    gcal = get_google_calendar_mcp_adapter()
    llm = get_default_adapter()
    tool_name = req.tool_name

    if tool_name in ("list_google_calendar_events", "list-events"):
        args = {"timeMin": req.query} if req.query else {}
        result = await asyncio.wait_for(gcal.call_tool("list-events", args), timeout=_TOOL_TIMEOUT)
        _check_gcal_error(result)
        response = await llm.complete([
            {"role": "system", "content": (
                "You are Tagent. Format the Google Calendar events into a clean schedule. "
                "Show start time, title, location, and any Google Meet link. "
                "If no events, say the calendar is clear."
            )},
            {"role": "user", "content": f"Result:\n{json.dumps(result, indent=2)}"},
        ])
        return {"status": "ok", "tool": tool_name, "response": response, "raw": result}

    if tool_name in ("search_google_calendar_events", "search-events"):
        result = await asyncio.wait_for(
            gcal.call_tool("search-events", {"query": req.query or ""}), timeout=_TOOL_TIMEOUT
        )
        _check_gcal_error(result)
        response = await llm.complete([
            {"role": "system", "content": "You are Tagent. Format the Google Calendar search results into a readable list."},
            {"role": "user", "content": f"Result:\n{json.dumps(result, indent=2)}"},
        ])
        return {"status": "ok", "tool": tool_name, "response": response, "raw": result}

    # create-event
    gcal_args = _build_gcal_create_args(req)
    result = await asyncio.wait_for(gcal.call_tool("create-event", gcal_args), timeout=_TOOL_TIMEOUT)
    _check_gcal_error(result)
    response = await llm.complete([
        {"role": "system", "content": (
            "You are Tagent. Confirm the Google Calendar event was created. "
            "Show the title, time, attendees, and the Google Meet link if available."
        )},
        {"role": "user", "content": f"Result:\n{json.dumps(result, indent=2)}"},
    ])
    return {"status": "ok", "tool": tool_name, "response": response, "raw": result}


def _check_gcal_error(result: dict) -> None:
    if result.get("status") in ("not_configured", "error"):
        raise HTTPException(status_code=400, detail=result.get("message", "Google Calendar error"))


def _build_gcal_create_args(req: DirectToolRequest) -> dict:
    import re
    from datetime import datetime, timedelta

    raw = (req.query or "").strip()
    attendee_emails = re.findall(r"[\w.\-+]+@[\w.\-]+\.\w+", raw)

    time_match = re.search(
        r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)|\b(\d{2}):(\d{2})\b",
        raw, re.IGNORECASE,
    )
    now = datetime.now()
    if time_match:
        if time_match.group(4):
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
        h, m = now.hour + 1, 0

    start = now.replace(hour=h, minute=m, second=0, microsecond=0)
    end = start + timedelta(hours=1)

    title_raw = re.sub(r"[\w.\-+]+@[\w.\-]+\.\w+", "", raw)
    title_raw = re.sub(
        r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)|\b(\d{2}):(\d{2})\b", "", title_raw, flags=re.IGNORECASE
    )
    title_raw = re.sub(
        r"\b(schedule|meet|meeting|at|today|email|with|a)\b", "", title_raw, flags=re.IGNORECASE
    )
    title = (req.title or re.sub(r"[:\-]+", " ", title_raw).strip() or "Meeting").strip()[:100] or "Meeting"

    args: dict = {
        "summary": title,
        "start": start.strftime("%Y-%m-%dT%H:%M:%S"),
        "end": end.strftime("%Y-%m-%dT%H:%M:%S"),
        "attendees": attendee_emails,
        "conferenceData": True,
    }
    if req.description:
        args["description"] = req.description
    return args


# ── DACL Business Rules ────────────────────────────────────────────────────────

async def _handle_dacl(req: DirectToolRequest, s) -> dict:
    import re
    from mcp.client.session import ClientSession
    from mcp.client.sse import sse_client
    from tagent.infrastructure.adapters.llm_adapter import get_default_adapter

    llm = get_default_adapter()
    dacl_url = s.dacl_mcp_url or "http://localhost:8080/sse"
    dacl_key = s.dacl_mcp_api_key or ""
    headers: dict[str, str] = {}
    if dacl_key:
        headers["X-API-Key"] = dacl_key
    if "host.docker.internal" in dacl_url:
        from urllib.parse import urlparse
        p = urlparse(dacl_url)
        headers["Host"] = f"localhost:{p.port}" if p.port else "localhost"

    tool_args: dict = {}
    if req.tool_name == "validate_business_rule" and req.query:
        raw = req.query.strip()
        try:
            tool_args = json.loads(raw)
        except json.JSONDecodeError:
            for part in re.split(r"[,;]\s*", raw):
                kv = part.strip().split("=", 1)
                if len(kv) == 2:
                    k, v = kv[0].strip(), kv[1].strip()
                    tool_args[k] = int(v) if v.lstrip("-").isdigit() else v
            if not tool_args:
                tool_args = {"input": raw}

    async def _run() -> dict:
        async with sse_client(dacl_url, headers=headers) as (r, w):
            async with ClientSession(r, w) as sess:
                await sess.initialize()
                result = await sess.call_tool(req.tool_name, tool_args)
                parts = [
                    getattr(item, "text", None)
                    for item in result.content
                    if isinstance(getattr(item, "text", None), str)
                ]
                raw_output = "\n".join(p for p in parts if p.strip())
                return {"raw": raw_output or json.dumps(result.model_dump(), indent=2)}

    try:
        dacl_data = await asyncio.wait_for(_run(), timeout=30)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="DACL MCP server timed out.")
    except Exception as exc:
        error_msg = str(exc)
        if hasattr(exc, "exceptions"):
            error_msg += " | Sub-errors: " + ", ".join(str(e) for e in exc.exceptions)
        raise HTTPException(status_code=502, detail=f"DACL MCP error: {error_msg[:500]}")

    response = await llm.complete([
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
            "content": f"Tool: {req.tool_name}\nArgs: {json.dumps(tool_args)}\nResult:\n{dacl_data['raw']}",
        },
    ])
    return {"status": "ok", "tool": req.tool_name, "response": response, "raw": dacl_data["raw"]}


# ── Generic MCP subprocess ─────────────────────────────────────────────────────

async def _handle_mcp(req: DirectToolRequest, s) -> dict:
    from mcp.client.session import ClientSession
    from mcp.client.stdio import StdioServerParameters, stdio_client
    from tagent.infrastructure.adapters.external_mcp_adapter import get_external_mcp_adapter
    from tagent.infrastructure.adapters.llm_adapter import get_default_adapter

    if not s.mcp_external_enabled:
        raise HTTPException(status_code=503, detail="MCP tools not enabled.")

    adapter = get_external_mcp_adapter()
    if not adapter.enabled():
        raise HTTPException(status_code=503, detail="MCP adapter not configured.")

    args = build_tool_args(req)
    # search_jira_issues is the actual MCP tool name for list_jira_issues
    tool_name = "search_jira_issues" if req.tool_name == "list_jira_issues" else req.tool_name
    # same normalisation for search_closed_issues
    if req.tool_name == "search_closed_issues":
        tool_name = "search_jira_issues"

    params = StdioServerParameters(
        command=adapter._command,
        args=adapter._args,
        cwd=adapter._cwd,
        env=os.environ.copy(),
    )

    async def _run() -> dict:
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, args)
                parts = [
                    item.text
                    for item in result.content
                    if hasattr(item, "text") and item.text
                ]
                raw_text = "\n".join(parts)
                try:
                    return json.loads(raw_text)
                except json.JSONDecodeError:
                    return {"output": raw_text}

    try:
        mcp_data = await asyncio.wait_for(_run(), timeout=_TOOL_TIMEOUT)
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail=f"Tool '{tool_name}' timed out after {_TOOL_TIMEOUT}s. Try again.",
        )
    except HTTPException:
        raise
    except BaseException as exc:
        import traceback
        traceback.print_exc()
        cause = exc.exceptions[0] if hasattr(exc, "exceptions") and exc.exceptions else exc
        raise HTTPException(status_code=500, detail=f"Tool call failed: {str(cause)[:300]}")

    if mcp_data.get("status") == "not_configured":
        raise HTTPException(
            status_code=400,
            detail=mcp_data.get("message", "Credentials not configured. Open Settings in the UI."),
        )
    if mcp_data.get("status") == "error":
        raise HTTPException(
            status_code=400, detail=mcp_data.get("message", "Tool execution error")
        )

    llm = get_default_adapter()
    system_prompt = get_system_prompt(tool_name)
    response = await llm.complete([
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Tool: {tool_name}\nArgs: {json.dumps(args)}\nResult:\n{json.dumps(mcp_data, indent=2)}"},
    ])
    return {"status": "ok", "tool": tool_name, "response": response, "raw": mcp_data}
