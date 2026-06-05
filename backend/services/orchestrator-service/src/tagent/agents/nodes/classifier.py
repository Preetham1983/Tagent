"""Classifier node — detect user intent from the latest message using LLM."""

from __future__ import annotations

import json

from tagent.agents.state import AgentState
from tagent.domain.value_objects.intent import Intent
from tagent.infrastructure.adapters.llm_adapter import get_default_adapter

# Fallback keyword map used when LLM classification fails
# NOTE: order matters — more specific patterns first
_KEYWORD_MAP: dict[str, Intent] = {
    "summarize": Intent.SUMMARIZE_MEETING,
    "summary": Intent.SUMMARIZE_MEETING,
    "standup": Intent.SUMMARIZE_MEETING,
    "schedule": Intent.SCHEDULE_MEETING,
    "book": Intent.SCHEDULE_MEETING,
    "create task": Intent.CREATE_TASK,
    "create ticket": Intent.CREATE_TASK,
    "create issue": Intent.CREATE_TASK,
    "new task": Intent.CREATE_TASK,
    "new ticket": Intent.CREATE_TASK,
    "update task": Intent.UPDATE_TASK,
    "update ticket": Intent.UPDATE_TASK,
    "update issue": Intent.UPDATE_TASK,
    "list issues": Intent.QUERY_TASKS,
    "list tasks": Intent.QUERY_TASKS,
    "show issues": Intent.QUERY_TASKS,
    "show tasks": Intent.QUERY_TASKS,
    "search issues": Intent.QUERY_TASKS,
    "search jira": Intent.QUERY_TASKS,
    "my issues": Intent.QUERY_TASKS,
    "my tasks": Intent.QUERY_TASKS,
    "issues in": Intent.QUERY_TASKS,
    "query": Intent.QUERY_TASKS,
    "jira": Intent.QUERY_TASKS,
    "issue": Intent.QUERY_TASKS,
    "tasks": Intent.QUERY_TASKS,
    "tickets": Intent.QUERY_TASKS,
    "calendar": Intent.QUERY_CALENDAR,
    "meetings": Intent.QUERY_CALENDAR,
    "schedule today": Intent.QUERY_CALENDAR,
    "events": Intent.QUERY_CALENDAR,
    "meeting": Intent.SCHEDULE_MEETING,
    "validate": Intent.VALIDATE_RULE,
    "validate rule": Intent.VALIDATE_RULE,
    "validate premium": Intent.VALIDATE_RULE,
    "validate policy": Intent.VALIDATE_RULE,
    "business rule": Intent.VALIDATE_RULE,
    "rule check": Intent.VALIDATE_RULE,
    "insurance": Intent.VALIDATE_RULE,
    "premium": Intent.VALIDATE_RULE,
    "policy check": Intent.VALIDATE_RULE,
    "list policies": Intent.VALIDATE_RULE,
    "available policies": Intent.VALIDATE_RULE,
    "user info": Intent.GET_USER_INFO,
    "my details": Intent.GET_USER_INFO,
    "who am i": Intent.GET_USER_INFO,
    "profile": Intent.GET_USER_INFO,
    "send": Intent.SEND_MESSAGE,
    "message": Intent.SEND_MESSAGE,
    "post": Intent.SEND_MESSAGE,
}

_VALID_INTENTS = {i.value for i in Intent}

_CLASSIFICATION_PROMPT = """\
You are an intent classifier for an enterprise AI assistant called Tagent.
Tagent is integrated with Microsoft Teams, Jira, and Microsoft 365 Calendar.

Given the user's message, classify it into exactly ONE of these intents:
- summarize_meeting: Summarize a meeting, standup, or transcript
- schedule_meeting: Schedule, book, or find time for a meeting
- create_task: Create a new Jira issue or task
- update_task: Update an existing Jira issue or task
- query_tasks: Search, list, or query Jira issues
- query_calendar: Show today's schedule, list meetings, or check calendar
- send_message: Send a message to a Teams channel or person
- get_user_info: Get the signed-in user's profile, name, email, or who they are
- validate_rule: Validate a business rule, check a premium, policy, or insurance eligibility
- general_chat: General question, greeting, help, or anything else

Respond with ONLY the intent string, nothing else. For example: general_chat
"""


async def classify(state: AgentState) -> dict:
    """Classify the user's intent from the latest message using LLM with keyword fallback."""
    messages = state.get("messages", [])
    if not messages:
        return {"intent": Intent.GENERAL_CHAT}

    last_message = messages[-1]
    if isinstance(last_message, dict):
        content = last_message.get("content", "")
    elif hasattr(last_message, "content"):
        content = last_message.content or ""
    else:
        content = ""

    if not content.strip():
        return {"intent": Intent.GENERAL_CHAT}

    # Try LLM-based classification
    try:
        llm = get_default_adapter()
        llm_messages = [
            {"role": "system", "content": _CLASSIFICATION_PROMPT},
            {"role": "user", "content": content},
        ]
        raw = await llm.complete(llm_messages)
        intent_str = raw.strip().lower().replace('"', "").replace("'", "")

        if intent_str in _VALID_INTENTS:
            return {"intent": Intent(intent_str)}
    except Exception:
        pass

    # Fallback to keyword matching
    content_lower = content.lower()
    for keyword, intent in _KEYWORD_MAP.items():
        if keyword in content_lower:
            return {"intent": intent}

    return {"intent": Intent.GENERAL_CHAT}
