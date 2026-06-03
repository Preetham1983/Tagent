"""Reviewer node — evaluate results and determine approval level."""

from __future__ import annotations

from tagent.agents.state import AgentState
from tagent.domain.value_objects.approval import ApprovalLevel, ApprovalRequest
from tagent.domain.value_objects.intent import Intent

# Map intents to required approval levels
_APPROVAL_LEVELS: dict[Intent, ApprovalLevel] = {
    Intent.SUMMARIZE_MEETING: ApprovalLevel.AUTO,
    Intent.GENERAL_CHAT: ApprovalLevel.AUTO,
    Intent.QUERY_TASKS: ApprovalLevel.AUTO,
    Intent.SCHEDULE_MEETING: ApprovalLevel.CONFIRM,
    Intent.CREATE_TASK: ApprovalLevel.CONFIRM,
    Intent.UPDATE_TASK: ApprovalLevel.CONFIRM,
    Intent.SEND_MESSAGE: ApprovalLevel.EXPLICIT,
}


async def review(state: AgentState) -> dict:
    """Review execution results and decide if human approval is needed."""
    intent = state.get("intent", Intent.UNKNOWN)
    level = _APPROVAL_LEVELS.get(intent, ApprovalLevel.CONFIRM)

    if level == ApprovalLevel.AUTO:
        return {"approval": None}

    tool_results = state.get("tool_results", [])
    last_result = tool_results[-1] if tool_results else {}
    description = last_result.get("output", "Perform action")

    approval = ApprovalRequest(
        action_description=description,
        level=level,
        user_id=state.get("user_id", ""),
    )
    return {"approval": approval}
