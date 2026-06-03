from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Meeting:
    id: str
    title: str
    organizer_id: str
    attendee_ids: list[str] = field(default_factory=list)
    start_time: datetime | None = None
    end_time: datetime | None = None
    transcript: str | None = None
    summary: str | None = None
    action_items: list[str] = field(default_factory=list)
    channel_id: str | None = None
    chat_id: str | None = None
