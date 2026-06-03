"""Meeting controller — handles meeting lifecycle events from Teams."""

from __future__ import annotations

from botbuilder.core import TurnContext


class MeetingController:
    """Handles meeting start/end events to trigger automatic summarization."""

    async def on_meeting_end(self, turn_context: TurnContext) -> None:
        """Triggered when a Teams meeting ends — starts auto-summarization flow."""
        # TODO: Extract meeting ID, trigger SummarizeMeetingUseCase
        pass

    async def on_meeting_start(self, turn_context: TurnContext) -> None:
        """Triggered when a Teams meeting starts — can set up note-taking."""
        # TODO: Register for transcript events
        pass
