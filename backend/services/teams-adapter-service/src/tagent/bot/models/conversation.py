"""Conversation model — tracks conversation state between turns."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConversationState:
    """Tracks the state of an ongoing conversation with the bot."""

    thread_id: str
    user_id: str
    active_graph_thread: str | None = None
    pending_approval_id: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
