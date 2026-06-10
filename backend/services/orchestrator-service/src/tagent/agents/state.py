"""LangGraph agent state definition."""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph.message import add_messages

from tagent.domain.value_objects.approval import ApprovalRequest
from tagent.domain.value_objects.intent import Intent


class AgentState(TypedDict):
    """The shared state passed between all LangGraph nodes."""

    # Conversation messages (LangGraph reducer: append-only)
    messages: Annotated[list[dict[str, Any]], add_messages]

    # Classified intent for the current turn
    intent: Intent | None

    # Plan: ordered list of steps the planner produced
    plan: list[str]

    # Current step index in the plan
    current_step: int

    # Results collected from tool executions
    tool_results: list[dict[str, Any]]

    # DACL gate result — set by dacl_guard before planning
    # Keys: allowed, auto_execute, requires_approval, fallback_action, dacl_available, raw
    dacl_result: dict[str, Any] | None

    # Step-level DACL results — set by step_dacl_guard after planning
    # List of per-step dicts: {step, allowed, auto_execute, requires_approval, dacl_available, raw}
    step_dacl_results: list[dict[str, Any]] | None

    # Human-in-the-loop approval state
    approval: ApprovalRequest | None

    # User/thread context
    user_id: str
    thread_id: str

    # User identity for DACL rule matching (passed in from the API layer)
    # user_role: admin | authenticated_user | agent | colleague
    # user_tier: free | basic | professional | enterprise
    user_role: str
    user_tier: str

    # Persistent memory snippets loaded for this conversation
    memory: list[str]
