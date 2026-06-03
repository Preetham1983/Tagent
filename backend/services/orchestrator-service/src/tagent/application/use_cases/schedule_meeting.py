"""Schedule meeting use case."""

from __future__ import annotations

from datetime import datetime

from tagent.domain.entities.meeting import Meeting
from tagent.domain.interfaces.graph_api_port import GraphApiPort


class ScheduleMeetingUseCase:
    """Find available slots and book a meeting."""

    def __init__(self, graph_api: GraphApiPort) -> None:
        self._graph_api = graph_api

    async def find_slots(
        self,
        attendee_ids: list[str],
        start: datetime,
        end: datetime,
        duration_minutes: int = 30,
    ) -> list[datetime]:
        return await self._graph_api.find_free_slots(
            attendee_ids, start, end, duration_minutes
        )

    async def book(self, meeting: Meeting) -> Meeting:
        return await self._graph_api.create_calendar_event(meeting)
