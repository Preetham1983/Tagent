"""Adaptive Card builders for Teams bot responses (View layer)."""

from __future__ import annotations

from botbuilder.schema import Activity, ActivityTypes, Attachment


def build_approval_card(action_description: str, thread_id: str = "") -> Activity:
    """Build an Adaptive Card requesting user approval."""
    card_json = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": [
            {
                "type": "TextBlock",
                "text": "⚠️ Approval Required",
                "weight": "Bolder",
                "size": "Medium",
                "color": "Warning",
            },
            {
                "type": "TextBlock",
                "text": action_description,
                "wrap": True,
            },
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "✅ Approve",
                "data": {"action": "approve", "thread_id": thread_id},
            },
            {
                "type": "Action.Submit",
                "title": "❌ Reject",
                "data": {"action": "reject", "thread_id": thread_id},
            },
        ],
    }

    attachment = Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card_json,
    )
    activity = Activity(
        type=ActivityTypes.message,
        attachments=[attachment],
    )
    return activity


def build_text_response(text: str) -> Activity:
    """Build a simple text message response."""
    return Activity(
        type=ActivityTypes.message,
        text=text,
    )


def build_summary_card(title: str, summary: str, action_items: list[str]) -> Activity:
    """Build a rich summary card with action items."""
    body = [
        {
            "type": "TextBlock",
            "text": f"📋 {title}",
            "weight": "Bolder",
            "size": "Medium",
        },
        {
            "type": "TextBlock",
            "text": summary,
            "wrap": True,
        },
    ]

    if action_items:
        body.append(
            {
                "type": "TextBlock",
                "text": "🎯 Action Items",
                "weight": "Bolder",
                "spacing": "Medium",
            }
        )
        for item in action_items:
            body.append(
                {
                    "type": "TextBlock",
                    "text": f"• {item}",
                    "wrap": True,
                }
            )

    card_json = {
        "type": "AdaptiveCard",
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.5",
        "body": body,
    }

    attachment = Attachment(
        content_type="application/vnd.microsoft.card.adaptive",
        content=card_json,
    )
    return Activity(
        type=ActivityTypes.message,
        attachments=[attachment],
    )
