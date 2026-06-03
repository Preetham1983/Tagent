"""User context model — stores per-user preferences and session data."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class UserContext:
    """Per-user context loaded at the start of each interaction."""

    user_id: str
    display_name: str = ""
    preferred_summary_style: str = "concise"
    approval_level: str = "confirm"
    working_hours_start: int = 9
    working_hours_end: int = 17
    timezone: str = "UTC"
    recent_meetings: list[str] = field(default_factory=list)
