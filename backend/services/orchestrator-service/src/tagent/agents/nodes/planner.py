"""Planner node — break the task into actionable steps based on intent."""

from __future__ import annotations

from tagent.agents.state import AgentState
from tagent.domain.value_objects.intent import Intent

# Static plan templates per intent (sensible defaults)
_PLAN_TEMPLATES: dict[Intent, list[str]] = {
    Intent.SUMMARIZE_MEETING: [
        "fetch_transcript",
        "summarize_transcript",
        "post_summary",
    ],
    Intent.SCHEDULE_MEETING: [
        "resolve_attendees",
        "find_free_slots",
        "propose_time",
        "book_meeting",
    ],
    Intent.CREATE_TASK: [
        "extract_task_details",
        "create_jira_issue",
        "confirm_creation",
    ],
    Intent.UPDATE_TASK: [
        "identify_task",
        "apply_updates",
        "confirm_update",
    ],
    Intent.QUERY_TASKS: [
        "build_query",
        "search_issues",
        "format_results",
    ],
    Intent.QUERY_CALENDAR: [
        "fetch_calendar_events",
        "format_calendar_response",
    ],
    Intent.SEND_MESSAGE: [
        "compose_message",
        "send_message",
    ],
    Intent.GET_USER_INFO: [
        "fetch_user_details",
        "format_user_details",
    ],
    Intent.VALIDATE_RULE: [
        "extract_validation_params",
        "validate_rule",
        "format_validation_result",
    ],
    Intent.GENERAL_CHAT: [
        "generate_response",
    ],
    Intent.UNKNOWN: [
        "generate_response",
    ],
}


async def plan(state: AgentState) -> dict:
    """Generate an execution plan based on the classified intent."""
    intent = state.get("intent", Intent.UNKNOWN)
    steps = _PLAN_TEMPLATES.get(intent, ["generate_response"])
    return {"plan": steps, "current_step": 0}
