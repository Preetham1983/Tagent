"""Summarize meeting use case."""

from __future__ import annotations

from tagent.domain.interfaces.graph_api_port import GraphApiPort
from tagent.domain.interfaces.llm_port import LLMPort


class SummarizeMeetingUseCase:
    """Fetch a meeting transcript and produce a structured summary."""

    def __init__(self, graph_api: GraphApiPort, llm: LLMPort) -> None:
        self._graph_api = graph_api
        self._llm = llm

    async def execute(self, meeting_id: str) -> dict[str, str | list[str]]:
        transcript = await self._graph_api.get_meeting_transcript(meeting_id)

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a meeting summarizer. Given a transcript, produce:\n"
                    "1. A concise summary (3-5 sentences)\n"
                    "2. Key decisions made\n"
                    "3. Action items with owners\n"
                    "Format as JSON with keys: summary, decisions, action_items"
                ),
            },
            {"role": "user", "content": transcript},
        ]

        schema = {
            "name": "meeting_summary",
            "schema": {
                "type": "object",
                "properties": {
                    "summary": {"type": "string"},
                    "decisions": {"type": "array", "items": {"type": "string"}},
                    "action_items": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["summary", "decisions", "action_items"],
            },
        }

        result = await self._llm.structured_output(messages, schema)
        return result
