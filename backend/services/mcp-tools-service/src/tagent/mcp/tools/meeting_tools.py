"""Meeting analysis and summarization tools for MCP."""

from __future__ import annotations

from mcp.server import Server


def register_meeting_tools(server: Server) -> None:
    """Register meeting tools (summarize)."""

    @server.tool()
    async def summarize_meeting_notes(notes: str) -> dict:
        """Summarize meeting notes into updates, blockers, and action items."""
        notes = str(notes or "").strip()
        if not notes:
            return {
                "status": "needs_input",
                "summary": "No meeting notes were provided.",
                "updates": [],
                "blockers": [],
                "action_items": [],
            }

        # Simple logic extracted from legacy server.py
        lines = [line.strip(" -\t") for line in notes.splitlines() if line.strip()]
        updates = lines[:5]
        return {
            "status": "ok",
            "summary": "Meeting notes summarized from MCP tool input.",
            "updates": updates,
            "blockers": [],
            "action_items": [],
        }
