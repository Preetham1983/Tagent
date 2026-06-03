"""Route intent use case — classify and dispatch user messages."""

from __future__ import annotations

from tagent.domain.interfaces.llm_port import LLMPort
from tagent.domain.value_objects.intent import Intent


class RouteIntentUseCase:
    """Use LLM to classify user intent when keyword matching is insufficient."""

    def __init__(self, llm: LLMPort) -> None:
        self._llm = llm

    async def classify(self, message: str) -> Intent:
        messages = [
            {
                "role": "system",
                "content": (
                    "Classify the user's intent into one of these categories:\n"
                    "- summarize_meeting\n"
                    "- schedule_meeting\n"
                    "- create_task\n"
                    "- update_task\n"
                    "- query_tasks\n"
                    "- send_message\n"
                    "- general_chat\n"
                    "Respond with only the category name."
                ),
            },
            {"role": "user", "content": message},
        ]

        result = await self._llm.complete(messages)
        intent_str = result.strip().lower()

        try:
            return Intent(intent_str)
        except ValueError:
            return Intent.GENERAL_CHAT
