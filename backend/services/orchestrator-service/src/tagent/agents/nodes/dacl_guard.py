"""DACL Guard node — validate every user action against the business rule engine.

This node sits between the classifier and the planner in the LangGraph graph.
It translates the classified intent into a DACL validation query, calls the
DACL MCP server, and sets `dacl_result` on state.

Routing after this node (handled in graph.py):
  - allowed=no          → END (blocked response returned to UI)
  - allowed=yes         → plan  (normal path; reviewer uses auto_execute flag)
  - allowed=conditional → END  (user needs tier upgrade / explicit approval)
  - dacl_unavailable    → plan  (fail-open; DACL server not reachable)
"""

from __future__ import annotations

import datetime
from typing import Any

from tagent.agents.state import AgentState
from tagent.domain.value_objects.intent import Intent


# ── Intent → DACL dimension mappings ─────────────────────────────────────────

_INTENT_TO_ACTION: dict[Intent, str] = {
    Intent.SUMMARIZE_MEETING: "summarize",
    Intent.SCHEDULE_MEETING: "schedule",
    Intent.CREATE_TASK: "create",
    Intent.UPDATE_TASK: "update",
    Intent.QUERY_TASKS: "search",
    Intent.QUERY_CALENDAR: "read",
    Intent.SEND_MESSAGE: "notify",
    Intent.GET_USER_INFO: "read",
    Intent.VALIDATE_RULE: "validate",
    Intent.GENERAL_CHAT: "read",
    Intent.UNKNOWN: "read",
}

_INTENT_TO_INTEGRATION: dict[Intent, str] = {
    Intent.SUMMARIZE_MEETING: "teams",
    Intent.SCHEDULE_MEETING: "ms365_calendar",
    Intent.CREATE_TASK: "jira",
    Intent.UPDATE_TASK: "jira",
    Intent.QUERY_TASKS: "jira",
    Intent.QUERY_CALENDAR: "ms365_calendar",
    Intent.SEND_MESSAGE: "teams",
    Intent.GET_USER_INFO: "ms_graph",
    Intent.VALIDATE_RULE: "dacl_engine",
    Intent.GENERAL_CHAT: "memory",
    Intent.UNKNOWN: "memory",
}

_INTENT_TO_MCP_TOOL: dict[Intent, str] = {
    Intent.SUMMARIZE_MEETING: "briefing_tool",
    Intent.SCHEDULE_MEETING: "ms365_calendar_tool",
    Intent.CREATE_TASK: "jira_tool",
    Intent.UPDATE_TASK: "jira_tool",
    Intent.QUERY_TASKS: "jira_tool",
    Intent.QUERY_CALENDAR: "ms365_calendar_tool",
    Intent.SEND_MESSAGE: "teams_tool",
    Intent.GET_USER_INFO: "memory_tool",
    Intent.VALIDATE_RULE: "dacl_tool",
    Intent.GENERAL_CHAT: "memory_tool",
    Intent.UNKNOWN: "memory_tool",
}


def _time_context() -> str:
    """Derive DACL time_context from the current local hour."""
    hour = datetime.datetime.now().hour
    weekday = datetime.datetime.now().weekday()  # 0=Mon … 6=Sun
    if weekday >= 5:
        return "weekend"
    if 9 <= hour < 18:
        return "business_hours"
    return "after_hours"


def _context_turns(messages: list[Any]) -> str:
    n = len(messages)
    if n <= 3:
        return "turns_1_3"
    if n <= 10:
        return "turns_4_10"
    if n <= 30:
        return "turns_11_30"
    return "turns_31_plus"


def _build_query(
    intent: Intent,
    messages: list[Any],
    user_role: str = "authenticated_user",
    user_tier: str = "professional",
) -> str:
    # Infer confidence from role/tier — enterprise admins get very_high,
    # professionals get high, everyone else gets medium.
    if user_role == "admin" or user_tier == "enterprise":
        confidence = "very_high"
    elif user_tier == "professional":
        confidence = "high"
    else:
        confidence = "medium"

    # Write actions always start with confirm approval so rules can override up/down
    action = _INTENT_TO_ACTION[intent]
    approval = "auto" if action in ("read", "search", "summarize", "validate") else "confirm"

    return (
        f"user_role={user_role} "
        f"integration={_INTENT_TO_INTEGRATION[intent]} "
        f"action_type={action} "
        f"query_intent={intent.value} "
        f"mcp_tool={_INTENT_TO_MCP_TOOL[intent]} "
        f"confidence={confidence} "
        f"approval_level={approval} "
        f"user_tier={user_tier} "
        f"context_turns={_context_turns(messages)} "
        f"time_context={_time_context()}"
    )


async def dacl_guard(state: AgentState) -> dict:
    """Validate the classified intent against DACL before planning.

    Sets `dacl_result` on state.  The graph routes on `dacl_result["allowed"]`.
    """
    # Import here to avoid circular import (executor also imports from state)
    from tagent.agents.nodes.executor import _call_dacl_mcp_tool

    intent: Intent = state.get("intent", Intent.UNKNOWN)
    messages: list = state.get("messages", [])
    user_role: str = state.get("user_role") or "authenticated_user"
    user_tier: str = state.get("user_tier") or "professional"

    # For general chat and unknown intents, skip DACL entirely and allow.
    if intent in (Intent.GENERAL_CHAT, Intent.UNKNOWN):
        return {
            "dacl_result": {
                "allowed": "yes",
                "auto_execute": "yes",
                "dacl_available": False,
            }
        }

    query = _build_query(intent, messages, user_role, user_tier)

    raw = await _call_dacl_mcp_tool(
        "validate_business_rule",
        {"domain": "agents", "query": query},
    )

    if raw is None or raw.get("status") == "error":
        # DACL server unavailable — fail-open, let the graph proceed
        return {
            "dacl_result": {
                "allowed": "yes",
                "auto_execute": "no",
                "requires_approval": "confirm",
                "dacl_available": False,
                "raw": raw,
            }
        }

    # Parse the DACL response.  The MCP server may return either a
    # structured dict or a pipe-delimited rule string in "output".
    result: dict[str, Any] = {}
    output = raw.get("output", "")

    if isinstance(output, dict):
        result = output
    elif isinstance(output, str) and "|" in output:
        # Parse pipe-delimited Tagent rule output
        parts = output.split("|")
        if len(parts) >= 4:
            for kv in parts[3].split(","):
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    result[k.strip()] = v.strip()
    elif isinstance(raw, dict):
        # Server returned flat JSON directly
        result = {k: v for k, v in raw.items() if k != "status"}

    # Derive the policy name: use what the engine returned, or fall back to the
    # intent-based default so the intent router always has a named policy.
    policy_name = (
        result.get("policy_name")
        or f"TAGENT_POLICY_{intent.value.upper()}"
    )

    return {
        "dacl_result": {
            "allowed": result.get("allowed", "yes"),
            "auto_execute": result.get("auto_execute", "no"),
            "requires_approval": result.get("requires_approval", "confirm"),
            "fallback_action": result.get("fallback_action", "use_alternative_tool"),
            "log_level": result.get("log_level", "info"),
            "policy_name": policy_name,
            "dacl_available": True,
            "raw": result,
        }
    }
