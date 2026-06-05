"""Executor node — execute the current step using MCP tools + LLM reasoning."""

from __future__ import annotations

import json

from tagent.agents.state import AgentState
from tagent.infrastructure.adapters.llm_adapter import get_default_adapter

# Per-step system instructions for LLM steps
_STEP_HINTS: dict[str, str] = {
    "fetch_transcript": (
        "If live meeting data is provided below, format it clearly with participants, "
        "key updates, blockers, and action items. If no live data is available, ask the "
        "user to share notes/transcript and do not invent meeting facts."
    ),
    "summarize_transcript": (
        "Produce a clear, concise meeting summary with sections: "
        "Attendees, Key Updates, Blockers, and Action Items."
    ),
    "post_summary": (
        "Confirm that the meeting summary has been posted to the relevant Teams channel "
        "and notify the participants."
    ),
    "resolve_attendees": (
        "Identify and resolve the attendees for the requested meeting. "
        "Output the list of their email addresses clearly."
    ),
    "find_free_slots": "Find available time slots that work for all attendees based on their calendars.",
    "propose_time": (
        "Propose the best meeting time based on attendee availability. "
        "Include the start time in ISO format (YYYY-MM-DDTHH:MM:SS) in your response."
    ),
    "book_meeting": "Confirm the meeting has been scheduled and send calendar invites to all attendees.",
    "extract_task_details": "Extract task title, description, priority, and assignee from the user's request.",
    "create_jira_issue": "Confirm the Jira issue has been created with the extracted details and provide the ticket ID.",
    "confirm_creation": "Provide a summary of the created task including the Jira ticket link.",
    "identify_task": "Identify the Jira task referenced by the user.",
    "apply_updates": "Apply the requested updates to the identified Jira task.",
    "confirm_update": "Confirm the task has been updated and summarize the changes.",
    "build_query": (
        "Build the JQL query for Jira based on the user's request. "
        "Output ONLY the raw JQL string, no explanation or markdown. "
        "IMPORTANT: do NOT use currentUser() — it does not work with API token auth. "
        "Use explicit project keys or field values instead. "
        "Example outputs: 'project = ITP ORDER BY created DESC'  or  'project is not EMPTY ORDER BY created DESC'"
    ),
    "search_issues": "Return matching Jira issues with their status, priority, and assignees.",
    "format_results": "Format the query results in a clean, readable list for the user.",
    "fetch_calendar_events": "Fetch the user's calendar events for today from Microsoft Graph.",
    "format_calendar_response": "Format the fetched calendar events into a clear schedule for the user. If no meetings are found, state that clearly.",
    "compose_message": (
        "Identify the recipient email and compose the message content. "
        "Output a JSON object with 'recipient_email' and 'message' keys. "
        "Example: {'recipient_email': 'user@example.com', 'message': 'Hello'}"
    ),
    "send_message": "Send the direct message using the extracted recipient and content.",
    "fetch_user_details": "Fetch the currently signed-in user's profile information from Microsoft Graph.",
    "format_user_details": "Format the user's profile details into a friendly greeting and summary. Mention they are connected to Tagent.",
    "generate_response": (
        "Answer the user's question helpfully and concisely as an enterprise AI assistant "
        "integrated with Microsoft Teams, Jira, and calendar systems."
    ),
    # DACL business rule validation steps
    "extract_validation_params": (
        "Extract business rule validation parameters from the user's message. "
        "Output ONLY a valid JSON object with these keys: "
        "age (integer), tier (string, e.g. BASIC/STANDARD/PREMIUM), "
        "pre_existing_conditions (integer), product (string, e.g. health_insurance). "
        'Example: {"age": 24, "tier": "BASIC", "pre_existing_conditions": 0, "product": "health_insurance"}'
    ),
    "validate_rule": (
        "Call the DACL business rule engine to validate the extracted parameters "
        "and return the calculated premium or validation result."
    ),
    "format_validation_result": (
        "Format the business rule validation result into a clear, friendly response for the user. "
        "Include the calculated premium percentage/amount, the tier, age, and any conditions. "
        "Explain what the result means in plain English."
    ),
}

# Steps that should call the external DACL MCP server via SSE
_STEP_TO_DACL_TOOL: dict[str, str] = {
    "validate_rule": "validate_business_rule",
    "list_policies": "list_available_policies",
}

# Steps that should directly call an MCP tool and use the result
_STEP_TO_MCP_TOOL: dict[str, str] = {
    "fetch_transcript": "summarize_meeting_notes",
    "summarize_transcript": "summarize_meeting_notes",
    "create_jira_issue": "create_jira_issue",
    "search_issues": "search_jira_issues",
    "fetch_calendar_events": "list_calendar_events",
    "find_free_slots": "find_free_slots",
    "book_meeting": "schedule_meeting",
    "send_message": "send_direct_message",
    "fetch_user_details": "get_user_info",
}

_SYSTEM_BASE = (
    "You are Tagent, an enterprise AI assistant integrated with Microsoft Teams, "
    "Jira, and Microsoft 365 calendar. You help users manage meetings, tasks, and communications. "
    "Be professional, concise, and actionable."
)


async def _call_mcp_tool(tool_name: str, arguments: dict) -> dict | None:
    """Call an MCP tool via the external MCP adapter and return the parsed result."""
    from tagent.infrastructure.config.settings import Settings

    s = Settings()
    if not s.mcp_external_enabled:
        return None

    from tagent.infrastructure.adapters.external_mcp_adapter import get_external_mcp_adapter

    adapter = get_external_mcp_adapter()
    if not adapter.enabled():
        return None

    try:
        # Use the adapter's stdio client to call the tool directly
        from mcp.client.stdio import StdioServerParameters, stdio_client
        from mcp.client.session import ClientSession
        import os

        # Build env dict so the MCP subprocess inherits current Jira creds
        env = os.environ.copy()

        params = StdioServerParameters(
            command=adapter._command,
            args=adapter._args,
            cwd=adapter._cwd,
            env=env,
        )
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)

                # Extract text content from the result
                parts = []
                for item in result.content:
                    text = getattr(item, "text", None)
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())

                if parts:
                    combined = "\n".join(parts)
                    try:
                        return json.loads(combined)
                    except json.JSONDecodeError:
                        return {"status": "ok", "output": combined}

                return {"status": "ok", "output": "Tool returned no content."}
    except Exception as exc:
        return {"status": "error", "output": f"MCP tool call failed: {str(exc)[:200]}"}


async def _call_dacl_mcp_tool(tool_name: str, arguments: dict) -> dict | None:
    """Call the external DACL MCP server via SSE transport and return the parsed result."""
    from tagent.infrastructure.config.settings import Settings

    s = Settings()
    url = s.dacl_mcp_url or "http://localhost:8080/sse"
    api_key = s.dacl_mcp_api_key or ""

    headers: dict[str, str] = {}
    if api_key:
        headers["X-API-Key"] = api_key
    # When routing through host.docker.internal the server sees the wrong Host header
    # and returns 421 Misdirected Request — override it to what the server expects.
    if "host.docker.internal" in url:
        from urllib.parse import urlparse as _urlparse
        _p = _urlparse(url)
        headers["Host"] = f"localhost:{_p.port}" if _p.port else "localhost"

    try:
        from mcp.client.sse import sse_client
        from mcp.client.session import ClientSession

        async with sse_client(url, headers=headers) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(tool_name, arguments)

                parts = []
                for item in result.content:
                    text = getattr(item, "text", None)
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())

                if parts:
                    combined = "\n".join(parts)
                    try:
                        return json.loads(combined)
                    except json.JSONDecodeError:
                        return {"status": "ok", "output": combined}

                # Fallback for structured content
                if not parts and hasattr(result, "isError") and not result.isError:
                    return {"status": "ok", "output": json.dumps(result.model_dump(), indent=2)}

                return {"status": "ok", "output": "DACL tool returned no content."}
    except Exception as exc:
        error_msg = str(exc)
        if hasattr(exc, "exceptions"):
            sub_errors = [str(e) for e in exc.exceptions]
            error_msg = f"{error_msg} | Sub-errors: {', '.join(sub_errors)}"
        return {"status": "error", "output": f"DACL MCP tool call failed: {error_msg[:500]}"}


def _parse_meeting_datetime(text: str) -> str:
    """
    Extract a meeting start time from natural-language text and return an ISO-8601 string.
    Handles formats like '1 pm on 29th may', '9:30 AM June 1', '2026-05-29T13:00:00', etc.
    Returns '' if nothing can be parsed.
    """
    import re
    from datetime import datetime, date as _date

    text_l = text.lower()

    # Already ISO — return as-is
    iso = re.search(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(?::\d{2})?)', text)
    if iso:
        return iso.group(1) if iso.group(1).count(":") == 2 else iso.group(1) + ":00"

    # --- extract hour / minute ---
    # Matches: "1 pm", "1:30 pm", "13:00", "9am"
    time_match = re.search(
        r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)',
        text_l,
    )
    if not time_match:
        # 24-hour notation: "13:00", "09:30"
        time_match24 = re.search(r'\b(\d{1,2}):(\d{2})\b', text_l)
        if not time_match24:
            return ""
        hour = int(time_match24.group(1))
        minute = int(time_match24.group(2))
    else:
        hour = int(time_match.group(1))
        minute = int(time_match.group(2) or 0)
        meridiem = time_match.group(3)
        if meridiem == "pm" and hour != 12:
            hour += 12
        elif meridiem == "am" and hour == 12:
            hour = 0

    # --- extract day / month ---
    _MONTH_MAP = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        "january": 1, "february": 2, "march": 3, "april": 4, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10,
        "november": 11, "december": 12,
    }

    now = datetime.now()
    day = now.day
    month = now.month
    year = now.year

    # "29th may", "may 29", "1st june", "june 1"
    day_month = re.search(
        r'(\d{1,2})(?:st|nd|rd|th)?\s+(' + '|'.join(_MONTH_MAP) + r')',
        text_l,
    )
    month_day = re.search(
        r'(' + '|'.join(_MONTH_MAP) + r')\s+(\d{1,2})(?:st|nd|rd|th)?',
        text_l,
    )
    if day_month:
        day = int(day_month.group(1))
        month = _MONTH_MAP[day_month.group(2)]
    elif month_day:
        month = _MONTH_MAP[month_day.group(1)]
        day = int(month_day.group(2))

    # Advance year if the resulting date is in the past
    try:
        candidate = datetime(year, month, day, hour, minute)
        if candidate < now:
            candidate = candidate.replace(year=year + 1)
        return candidate.strftime("%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return ""


def _extract_meeting_title(text: str) -> str:
    """Extract a meeting title/description from keywords like 'desc:', 'about:', 'topic:'."""
    import re
    m = re.search(
        r'(?:desc(?:ription)?|about|topic|subject|title)\s*[:\-]\s*(.+?)(?:\s*$|\n)',
        text,
        re.IGNORECASE,
    )
    if m:
        return m.group(1).strip()
    return ""


async def _fetch_graph_data(step_name: str) -> str | None:
    """
    For steps that need real Microsoft Graph data, fetch it and return as a
    formatted string to inject into the LLM prompt.
    """
    from tagent.infrastructure.config.settings import Settings

    s = Settings()
    if (s.graph_mode or "off").lower() == "off":
        return None

    if not s.ms_tenant_id or not s.ms_client_id or not s.ms_client_secret:
        return None

    from tagent.infrastructure.adapters.ms_graph_adapter import get_graph_adapter

    graph = get_graph_adapter()

    try:
        if step_name == "fetch_transcript":
            me = await graph.get_me()
            user_id = me.get("id", "")
            if not user_id:
                return None

            ctx = await graph.get_standup_context(user_id)
            meetings = ctx.get("meetings", [])
            transcript = ctx.get("transcript", "")

            lines = [f"User: {me.get('displayName')} <{me.get('mail')}>"]
            lines.append(f"Today's meetings ({len(meetings)} found):")
            for m in meetings:
                subj = m.get("subject", "(no subject)")
                start = (m.get("start") or {}).get("dateTime", "")[:16]
                end = (m.get("end") or {}).get("dateTime", "")[:16]
                attendees = [
                    (a.get("emailAddress") or {}).get("name", "")
                    for a in (m.get("attendees") or [])
                ]
                lines.append(f"  • {subj} [{start} → {end}] — Attendees: {', '.join(attendees) or 'N/A'}")

            if transcript:
                lines.append("\n--- TRANSCRIPT ---")
                lines.append(transcript[:4000])
            else:
                lines.append("\n(No transcript available yet — summarising from calendar data only)")

            return "\n".join(lines)
        
        if step_name == "fetch_calendar_events":
            me = await graph.get_me()
            user_id = me.get("id", "")
            meetings = await graph.get_today_meetings(user_id)
            lines = [f"Calendar for {me.get('displayName')} today:"]
            if not meetings:
                lines.append("  (No meetings found)")
            for m in meetings:
                subj = m.get("subject", "(no subject)")
                start = (m.get("start") or {}).get("dateTime", "")[:16]
                lines.append(f"  • {subj} at {start}")
            return "\n".join(lines)

        if step_name in ("resolve_attendees", "find_free_slots"):
            users = await graph.list_users(top=10)
            lines = ["Tenant users (for attendee resolution):"]
            for u in users:
                lines.append(f"  • {u.get('displayName')} <{u.get('mail')}> — {u.get('jobTitle', '')}")
            return "\n".join(lines)

    except Exception:
        return None

    return None


async def _fetch_mcp_context(step_name: str, user_message: str) -> str | None:
    """Fetch context from the MCP tool server for enrichment."""
    if step_name not in ("fetch_transcript", "summarize_transcript", "generate_response", "get_user_info"):
        return None

    from tagent.infrastructure.config.settings import Settings

    s = Settings()
    if not s.mcp_external_enabled:
        return None

    _STEP_MCP_TOOL: dict[str, str] = {
        "get_user_info": "get_user_info",
        "fetch_transcript": "summarize_meeting_notes",
        "summarize_transcript": "summarize_meeting_notes",
    }

    from tagent.infrastructure.adapters.external_mcp_adapter import get_external_mcp_adapter

    adapter = get_external_mcp_adapter()
    if not adapter.enabled():
        return None

    prefer = _STEP_MCP_TOOL.get(step_name, "")
    return await adapter.summarize_from_query(user_message, prefer_tool=prefer)


async def execute(state: AgentState) -> dict:
    """Execute ALL plan steps sequentially — MCP tools first, then LLM for reasoning."""
    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)
    tool_results = list(state.get("tool_results", []))
    messages = state.get("messages", [])
    intent = state.get("intent")

    if current_step >= len(plan):
        return {"tool_results": tool_results}

    last = messages[-1] if messages else None
    if isinstance(last, dict):
        user_message = last.get("content", "")
    elif last is not None and hasattr(last, "content"):
        user_message = last.content or ""
    else:
        user_message = ""

    intent_label = intent.value if intent else "unknown"

    # Load Jira project key once for prompt enrichment
    import os as _os
    _jira_project_key = _os.environ.get("JIRA_PROJECT_KEY", "")

    # Iterate through ALL remaining plan steps
    while current_step < len(plan):
        step_name = plan[current_step]

        step_hint = _STEP_HINTS.get(
            step_name,
            f"Execute the step '{step_name}' as part of handling the user's request.",
        )

        # For build_query: inject the real project key so the LLM avoids currentUser()
        if step_name == "build_query" and _jira_project_key:
            step_hint = (
                f"{step_hint} "
                f"The configured Jira project key is '{_jira_project_key}'. "
                f"Use this key in your JQL unless the user asks for a different project."
            )

        # ── Try DACL SSE MCP tool call for business rule steps ──────
        dacl_tool_name = _STEP_TO_DACL_TOOL.get(step_name)
        dacl_direct_result = None

        if dacl_tool_name:
            args: dict = {}
            if dacl_tool_name == "validate_business_rule":
                # Parse params from the prior extract_validation_params LLM output
                prior = next((r for r in tool_results if r["step"] == "extract_validation_params"), None)
                if prior:
                    raw = prior["output"]
                    if isinstance(raw, str):
                        import re as _re
                        # Strip markdown fences if present
                        clean = _re.sub(r"```[a-z]*", "", raw).strip().rstrip("`").strip()
                        try:
                            args = json.loads(clean)
                        except json.JSONDecodeError:
                            # Best-effort: pass the raw message
                            args = {"input": user_message}
                    elif isinstance(raw, dict):
                        args = raw
                else:
                    args = {"input": user_message}
            elif dacl_tool_name == "list_available_policies":
                args = {}

            dacl_direct_result = await _call_dacl_mcp_tool(dacl_tool_name, args)
            if dacl_direct_result:
                output = dacl_direct_result.get("output", str(dacl_direct_result))
                tool_results.append({
                    "step": step_name,
                    "tool": dacl_tool_name,
                    "output": output,
                    "status": dacl_direct_result.get("status", "ok"),
                    "source": "dacl_mcp",
                })

        # ── Try direct MCP tool call for actionable steps ───────────
        mcp_tool_name = _STEP_TO_MCP_TOOL.get(step_name)
        mcp_direct_result = None

        # Special case: if user asks about "projects" during a QUERY_TASKS flow,
        # call list_jira_projects instead of search_jira_issues
        if step_name == "search_issues":
            msg_lower = user_message.lower()
            if "project" in msg_lower and ("list" in msg_lower or "show" in msg_lower or "what" in msg_lower or "all" in msg_lower):
                mcp_tool_name = "list_jira_projects"

        if mcp_tool_name:
            # Build arguments from user message and prior step outputs
            args: dict = {}
            if mcp_tool_name == "summarize_meeting_notes":
                args = {"notes": user_message}
            elif mcp_tool_name == "list_jira_projects":
                args = {}
            elif mcp_tool_name == "create_jira_issue":
                prior = next((r for r in tool_results if r["step"] == "extract_task_details"), None)
                if prior:
                    try:
                        details = json.loads(prior["output"]) if isinstance(prior["output"], str) else prior["output"]
                        args = {
                            "title": details.get("title", user_message[:80]),
                            "description": details.get("description", user_message),
                            "priority": details.get("priority", "Medium"),
                            "assignee": details.get("assignee", ""),
                        }
                    except (json.JSONDecodeError, AttributeError):
                        args = {"title": user_message[:80], "description": user_message}
                else:
                    args = {"title": user_message[:80], "description": user_message}
            elif mcp_tool_name == "search_jira_issues":
                prior = next((r for r in tool_results if r["step"] == "build_query"), None)
                jql = prior["output"] if prior else f"project is not EMPTY ORDER BY created DESC"
                args = {"jql": jql}
            elif mcp_tool_name == "list_calendar_events":
                args = {} # Defaults to today
            elif mcp_tool_name == "find_free_slots":
                prior = next((r for r in tool_results if r["step"] == "resolve_attendees"), None)
                attendees = []
                if prior:
                    import re
                    attendees = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', prior["output"])
                
                # If no emails found in resolve_attendees, fallback to history
                if not attendees:
                    import re
                    # Look through all messages in current state
                    all_text = " ".join([
                        (m.content if hasattr(m, "content") else (m.get("content", "") if isinstance(m, dict) else ""))
                        for m in messages
                    ])
                    attendees = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', all_text)

                from datetime import datetime
                today = datetime.now().strftime("%Y-%m-%d")
                args = {"user_ids": attendees, "date": today}
            elif mcp_tool_name == "schedule_meeting":
                # Get attendees from resolve_attendees or history
                prior_att = next((r for r in tool_results if r["step"] == "resolve_attendees"), None)
                attendees = []
                if prior_att:
                    import re
                    attendees = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', prior_att["output"])

                if not attendees:
                    import re
                    all_text = " ".join([
                        (m.content if hasattr(m, "content") else (m.get("content", "") if isinstance(m, dict) else ""))
                        for m in messages
                    ])
                    attendees = re.findall(r'[\w\.-]+@[\w\.-]+\.\w+', all_text)

                # Resolve start_time: user message first (most reliable), then propose_time LLM output
                start_time = _parse_meeting_datetime(user_message)
                if not start_time:
                    prior_time = next((r for r in tool_results if r["step"] == "propose_time"), None)
                    if prior_time:
                        start_time = _parse_meeting_datetime(str(prior_time["output"]))
                if not start_time:
                    from datetime import datetime as _dt
                    start_time = _dt.now().strftime("%Y-%m-%dT%H:%M:%S")

                # Build a meaningful title (prefer explicit desc/topic, else truncate user message)
                custom_title = _extract_meeting_title(user_message)
                title = custom_title if custom_title else user_message[:60].strip()

                args = {
                    "title": title,
                    "attendee_ids": attendees,
                    "start_time": start_time,
                    "duration_minutes": 30,
                }
            elif mcp_tool_name == "send_direct_message":
                prior = next((r for r in tool_results if r["step"] == "compose_message"), None)
                recipient = ""
                msg = user_message

                if prior:
                    try:
                        output_str = prior["output"]
                        if "```" in output_str:
                            output_str = output_str.split("```")[1].replace("json", "").strip()
                        details = json.loads(output_str)
                        recipient = details.get("recipient_email", "")
                        msg = details.get("message", user_message)
                    except Exception:
                        import re
                        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', prior["output"])
                        if email_match:
                            recipient = email_match.group(0)
                        msg = prior["output"]
                
                if not recipient:
                    import re
                    all_text = " ".join([
                        (m.content if hasattr(m, "content") else (m.get("content", "") if isinstance(m, dict) else ""))
                        for m in messages
                    ])
                    email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', all_text)
                    if email_match:
                        recipient = email_match.group(0)

                args = {"recipient_email": recipient, "message": msg}

            # Execute the tool
            mcp_direct_result = await _call_mcp_tool(mcp_tool_name, args)
            if mcp_direct_result:
                output = mcp_direct_result.get("output", str(mcp_direct_result))
                tool_results.append({
                    "step": step_name,
                    "tool": mcp_tool_name,
                    "output": output,
                    "status": mcp_direct_result.get("status", "ok")
                })
        
        # ── Otherwise use LLM reasoning for the step ────────────────
        if not mcp_direct_result and not dacl_direct_result:
            # Context enrichment
            graph_context = await _fetch_graph_data(step_name)
            mcp_context = await _fetch_mcp_context(step_name, user_message)

            system_prompt = (
                f"{_SYSTEM_BASE}\n\n"
                f"Current Intent: {intent_label}\n"
                f"Current Step: {step_name}\n"
                f"Step Goal: {step_hint}\n\n"
            )
            
            if tool_results:
                system_prompt += "Prior tool outputs:\n"
                for r in tool_results:
                    src = f" [{r.get('source', r.get('tool', 'llm'))}]" if r.get("source") else ""
                    system_prompt += f"- {r['step']}{src}: {r['output']}\n"
            
            if graph_context:
                system_prompt += f"\nRelevant Microsoft Graph Data:\n{graph_context}\n"
            if mcp_context:
                system_prompt += f"\nRelevant Knowledge/Context:\n{mcp_context}\n"

            llm = get_default_adapter()
            response = await llm.complete([
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ])

            tool_results.append({
                "step": step_name,
                "tool": "llm_reasoning",
                "output": response,
                "status": "ok"
            })

        current_step += 1

    return {
        "tool_results": tool_results,
        "current_step": current_step,
        "messages": messages # Preserve state
    }
