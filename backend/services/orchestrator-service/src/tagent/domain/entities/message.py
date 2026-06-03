from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Message:
    id: str
    sender_id: str
    content: str
    channel_id: str | None = None
    chat_id: str | None = None
    timestamp: datetime | None = None
    is_from_bot: bool = False
