"""Message controller — handles incoming Teams messages and routes to agent."""

from __future__ import annotations

import re

import httpx
from botbuilder.core import TurnContext
from botbuilder.schema import ActivityTypes

from tagent.bot.views.cards import build_approval_card, build_text_response


class MessageController:
    """MVC Controller: receives Teams activities and dispatches to the agent graph."""

    def __init__(self, orchestrator_base_url: str) -> None:
        self._orchestrator_base_url = orchestrator_base_url.rstrip("/")

    async def on_turn(self, turn_context: TurnContext) -> None:
        if turn_context.activity.type == ActivityTypes.message:
            await self._handle_message(turn_context)
        elif turn_context.activity.type == ActivityTypes.invoke:
            await self._handle_card_action(turn_context)

    def _strip_bot_mention(self, text: str, turn_context: TurnContext) -> str:
        """Remove the bot @mention from the message text."""
        if not text:
            return ""

        # Remove XML-style mention tags: <at>BotName</at>
        cleaned = re.sub(r"<at>.*?</at>", "", text).strip()

        # Also remove the bot's display name if it appears at the start
        bot_name = turn_context.activity.recipient.name if turn_context.activity.recipient else ""
        if bot_name and cleaned.lower().startswith(bot_name.lower()):
            cleaned = cleaned[len(bot_name):].strip()

        return cleaned or text

    async def _handle_message(self, turn_context: TurnContext) -> None:
        """Forward user message to orchestrator service and render response."""
        user_id = turn_context.activity.from_property.id
        thread_id = turn_context.activity.conversation.id
        raw_text = turn_context.activity.text or ""

        # Strip the @mention prefix before forwarding
        text = self._strip_bot_mention(raw_text, turn_context)

        if not text.strip():
            await turn_context.send_activity(
                build_text_response("Hi! I'm Tagent. Mention me with a request like 'summarize standup' or 'create a Jira ticket'.")
            )
            return

        payload = {
            "user_id": user_id,
            "thread_id": thread_id,
            "message": text,
        }

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self._orchestrator_base_url}/orchestrate",
                    json=payload,
                )
                response.raise_for_status()
                result = response.json()
        except Exception as exc:
            await turn_context.send_activity(
                build_text_response(f"Sorry, I encountered an error: {str(exc)[:200]}")
            )
            return

        # Check if graph was interrupted for human approval
        approval = result.get("approval", {})
        if approval.get("required") and approval.get("status") == "pending":
            card = build_approval_card(
                action_description=approval.get("description", "Approve action"),
                thread_id=result.get("thread_id", thread_id),
            )
            await turn_context.send_activity(card)
        else:
            # Send final response
            response_text = result.get("response", "Done.")
            await turn_context.send_activity(build_text_response(response_text))

    async def _handle_card_action(self, turn_context: TurnContext) -> None:
        """Handle Adaptive Card action (approval/rejection) — posts to /approve."""
        value = turn_context.activity.value or {}
        action = value.get("action", "")
        thread_id = value.get("thread_id", "")

        if not thread_id or action not in ("approve", "reject"):
            return

        user_id = turn_context.activity.from_property.id
        approved = action == "approve"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self._orchestrator_base_url}/approve",
                    json={
                        "thread_id": thread_id,
                        "approved": approved,
                        "user_id": user_id,
                    },
                )
                response.raise_for_status()
                result = response.json()

            status_text = "✅ Approved" if approved else "❌ Rejected"
            response_text = result.get("response", "Action processed.")
            await turn_context.send_activity(
                build_text_response(f"{status_text}\n\n{response_text}")
            )
        except Exception as exc:
            await turn_context.send_activity(
                build_text_response(f"Failed to process approval: {str(exc)[:200]}")
            )
