"""Step-level DACL guard — validate the LLM's plan with a single DACL call.

This node sits between the planner and the executor in the LangGraph graph.
Rather than calling the DACL engine once per planned step (expensive), it
identifies the *highest-risk* step in the plan and submits ONE validation
request that represents the worst-case action the plan will perform.

This keeps the total DACL calls per query at exactly 2:
  1. dacl_guard      — intent-level check (before planning)
  2. step_dacl_guard — plan-level check   (highest-risk step, after planning)

Flow position:  plan → step_dacl_guard → execute   (or END if blocked)

Routing after this node (handled in graph.py):
  blocked      → END      (highest-risk step returned allowed=no)
  allowed      → execute  (plan cleared; safe to proceed)
  unavailable  → execute  (fail-open; DACL server not reachable)
"""

from __future__ import annotations

import datetime
from typing import Any

from tagent.agents.state import AgentState


# ── Step → DACL dimension mappings ───────────────────────────────────────────

_STEP_TO_ACTION: dict[str, str] = {
    "fetch_transcript": "read",
    "summarize_transcript": "summarize",
    "post_summary": "create",
    "resolve_attendees": "read",
    "find_free_slots": "read",
    "propose_time": "read",
    "book_meeting": "schedule",
    "extract_task_details": "read",
    "create_jira_issue": "create",
    "confirm_creation": "read",
    "identify_task": "read",
    "apply_updates": "update",
    "confirm_update": "read",
    "build_query": "search",
    "search_issues": "search",
    "format_results": "read",
    "fetch_calendar_events": "read",
    "format_calendar_response": "read",
    "compose_message": "read",
    "send_message": "notify",
    "fetch_user_details": "read",
    "format_user_details": "read",
    "generate_response": "read",
    "extract_validation_params": "read",
    "validate_rule": "validate",
    "format_validation_result": "read",
    "list_policies": "read",
}

_STEP_TO_INTEGRATION: dict[str, str] = {
    "fetch_transcript": "teams",
    "summarize_transcript": "teams",
    "post_summary": "teams",
    "resolve_attendees": "ms_graph",
    "find_free_slots": "ms365_calendar",
    "propose_time": "ms365_calendar",
    "book_meeting": "ms365_calendar",
    "extract_task_details": "jira",
    "create_jira_issue": "jira",
    "confirm_creation": "jira",
    "identify_task": "jira",
    "apply_updates": "jira",
    "confirm_update": "jira",
    "build_query": "jira",
    "search_issues": "jira",
    "format_results": "jira",
    "fetch_calendar_events": "ms365_calendar",
    "format_calendar_response": "ms365_calendar",
    "compose_message": "teams",
    "send_message": "teams",
    "fetch_user_details": "ms_graph",
    "format_user_details": "ms_graph",
    "generate_response": "memory",
    "extract_validation_params": "dacl_engine",
    "validate_rule": "dacl_engine",
    "format_validation_result": "dacl_engine",
    "list_policies": "dacl_engine",
}

_STEP_TO_MCP_TOOL: dict[str, str] = {
    "fetch_transcript": "briefing_tool",
    "summarize_transcript": "briefing_tool",
    "post_summary": "briefing_tool",
    "resolve_attendees": "memory_tool",
    "find_free_slots": "ms365_calendar_tool",
    "propose_time": "ms365_calendar_tool",
    "book_meeting": "ms365_calendar_tool",
    "extract_task_details": "jira_tool",
    "create_jira_issue": "jira_tool",
    "confirm_creation": "jira_tool",
    "identify_task": "jira_tool",
    "apply_updates": "jira_tool",
    "confirm_update": "jira_tool",
    "build_query": "jira_tool",
    "search_issues": "jira_tool",
    "format_results": "jira_tool",
    "fetch_calendar_events": "ms365_calendar_tool",
    "format_calendar_response": "ms365_calendar_tool",
    "compose_message": "teams_tool",
    "send_message": "teams_tool",
    "fetch_user_details": "memory_tool",
    "format_user_details": "memory_tool",
    "generate_response": "memory_tool",
    "extract_validation_params": "dacl_tool",
    "validate_rule": "dacl_tool",
    "format_validation_result": "dacl_tool",
    "list_policies": "dacl_tool",
}

# Steps with write/mutating actions that always require explicit approval
_WRITE_ACTIONS = {"create", "update", "schedule", "notify"}


def _time_context() -> str:
    hour = datetime.datetime.now().hour
    weekday = datetime.datetime.now().weekday()  # 0=Mon … 6=Sun
    if weekday >= 5:
        return "weekend"
    if 9 <= hour < 18:
        return "business_hours"
    return "after_hours"


# Action risk ranking — higher index = higher risk
_ACTION_RISK: list[str] = ["read", "search", "summarize", "validate", "notify", "update", "create", "schedule"]


def _riskiest_step(plan: list[str]) -> str:
    """Return the step in the plan that maps to the highest-risk DACL action."""
    return max(
        plan,
        key=lambda s: _ACTION_RISK.index(_STEP_TO_ACTION.get(s, "read"))
        if _STEP_TO_ACTION.get(s, "read") in _ACTION_RISK
        else 0,
    )


def _build_plan_query(
    step: str,
    user_role: str,
    user_tier: str,
    messages: list[Any],
) -> str:
    """Build a single DACL query representing the highest-risk step in the plan."""
    action = _STEP_TO_ACTION.get(step, "read")
    integration = _STEP_TO_INTEGRATION.get(step, "memory")
    mcp_tool = _STEP_TO_MCP_TOOL.get(step, "memory_tool")

    if user_role == "admin" or user_tier == "enterprise":
        confidence = "very_high"
    elif user_tier == "professional":
        confidence = "high"
    else:
        confidence = "medium"

    approval = "confirm" if action in _WRITE_ACTIONS else "auto"

    n = len(messages)
    if n <= 3:
        turns = "turns_1_3"
    elif n <= 10:
        turns = "turns_4_10"
    elif n <= 30:
        turns = "turns_11_30"
    else:
        turns = "turns_31_plus"

    return (
        f"user_role={user_role} "
        f"integration={integration} "
        f"action_type={action} "
        f"query_intent=plan_{step} "
        f"mcp_tool={mcp_tool} "
        f"confidence={confidence} "
        f"approval_level={approval} "
        f"user_tier={user_tier} "
        f"context_turns={turns} "
        f"time_context={_time_context()}"
    )


def _parse_dacl_response(raw: dict) -> dict[str, Any]:
    """Parse a DACL MCP response into a flat result dict."""
    result: dict[str, Any] = {}
    output = raw.get("output", "")

    if isinstance(output, dict):
        result = output
    elif isinstance(output, str) and "|" in output:
        # Pipe-delimited Tagent rule output
        parts = output.split("|")
        if len(parts) >= 4:
            for kv in parts[3].split(","):
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    result[k.strip()] = v.strip()
    elif isinstance(raw, dict):
        result = {k: v for k, v in raw.items() if k != "status"}

    return result


async def step_dacl_guard(state: AgentState) -> dict:
    """Validate the LLM plan with a single DACL call against the highest-risk step.

    Instead of calling the DACL engine once per step (O(N) calls), this node
    picks the riskiest action in the plan and submits ONE ``validate_business_rule``
    request.  Total DACL calls per query is always exactly 2:
      dacl_guard (intent) + step_dacl_guard (plan worst-case).

    State mutations:
      step_dacl_results — list with one record: the plan-level verdict
    """
    from tagent.agents.nodes.executor import _call_dacl_mcp_tool

    plan: list[str] = state.get("plan") or []
    messages: list = state.get("messages", [])
    user_role: str = state.get("user_role") or "authenticated_user"
    user_tier: str = state.get("user_tier") or "professional"

    if not plan:
        return {"step_dacl_results": []}

    # Pick the single highest-risk step to represent the entire plan
    critical_step = _riskiest_step(plan)
    query = _build_plan_query(critical_step, user_role, user_tier, messages)

    raw = await _call_dacl_mcp_tool(
        "validate_business_rule",
        {"domain": "agents", "query": query},
    )

    if raw is None or raw.get("status") == "error":
        # DACL server unreachable — fail-open
        return {
            "step_dacl_results": [{
                "step": critical_step,
                "plan": plan,
                "allowed": "yes",
                "dacl_available": False,
                "raw": raw,
            }]
        }

    result = _parse_dacl_response(raw)
    policy_name = (
        result.get("policy_name")
        or f"TAGENT_POLICY_PLAN_{critical_step.upper()}"
    )

    return {
        "step_dacl_results": [{
            "step": critical_step,
            "plan": plan,
            "allowed": result.get("allowed", "yes"),
            "auto_execute": result.get("auto_execute", "no"),
            "requires_approval": result.get("requires_approval", "confirm"),
            "fallback_action": result.get("fallback_action", "use_alternative_tool"),
            "log_level": result.get("log_level", "info"),
            "policy_name": policy_name,
            "dacl_available": True,
            "raw": result,
        }]
    }
