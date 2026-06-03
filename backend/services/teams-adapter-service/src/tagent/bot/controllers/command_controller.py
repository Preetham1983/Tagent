"""Command controller — handles slash commands and proactive triggers."""

from __future__ import annotations

import httpx
from botbuilder.core import TurnContext

from tagent.bot.views.cards import build_text_response


# Command-to-message mapping for clean routing through the orchestrator
_COMMAND_MAP: dict[str, str] = {
    "/summarize": "summarize today's standup meeting",
    "/tasks": "show my open Jira tasks",
    "/schedule": "schedule a meeting",
    "/help": "help",
}


class CommandController:
    """Handles explicit bot commands (e.g., /summarize, /tasks, /schedule)."""

    def __init__(self, orchestrator_base_url: str) -> None:
        self._orchestrator_base_url = orchestrator_base_url.rstrip("/")

    async def handle_command(self, turn_context: TurnContext, command: str, args: str) -> None:
        """Dispatch a slash command to the orchestrator as a natural language message."""
        cmd = command.lower().strip()

        if cmd == "/help":
            help_text = (
                "**Available Commands:**\n\n"
                "• `/summarize` — Summarize today's standup\n"
                "• `/tasks` — Show open Jira tasks\n"
                "• `/schedule <details>` — Schedule a meeting\n"
                "• `/help` — Show this help message\n\n"
                "You can also just mention me with natural language!"
            )
            await turn_context.send_activity(build_text_response(help_text))
            return

        # Convert command to a natural language message for the orchestrator
        base_message = _COMMAND_MAP.get(cmd, cmd)
        message = f"{base_message} {args}".strip() if args else base_message

        user_id = turn_context.activity.from_property.id
        thread_id = turn_context.activity.conversation.id

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self._orchestrator_base_url}/orchestrate",
                    json={
                        "user_id": user_id,
                        "thread_id": thread_id,
                        "message": message,
                    },
                )
                response.raise_for_status()
                result = response.json()

            response_text = result.get("response", "Done.")
            await turn_context.send_activity(build_text_response(response_text))
        except Exception as exc:
            await turn_context.send_activity(
                build_text_response(f"Command failed: {str(exc)[:200]}")
            )
