from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from tagent.domain.entities.meeting import Meeting
from tagent.domain.entities.user import User


class GraphApiPort(ABC):
    @abstractmethod
    async def get_user(self, user_id: str) -> User: ...

    @abstractmethod
    async def get_meeting_transcript(self, meeting_id: str) -> str: ...

    @abstractmethod
    async def send_mail(self, to: str, subject: str, body: str) -> None: ...

    @abstractmethod
    async def get_calendar_events(
        self, user_id: str, start: datetime, end: datetime
    ) -> list[Meeting]: ...

    @abstractmethod
    async def create_calendar_event(self, meeting: Meeting) -> Meeting: ...

    @abstractmethod
    async def find_free_slots(
        self, user_ids: list[str], start: datetime, end: datetime, duration_minutes: int = 30
    ) -> list[datetime]: ...
