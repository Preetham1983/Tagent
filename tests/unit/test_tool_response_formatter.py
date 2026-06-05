"""Unit tests for tool_response_formatter."""

from __future__ import annotations

from tagent.application.services.tool_response_formatter import get_system_prompt


def test_known_tools_return_non_empty_prompts():
    known_tools = [
        "get_daily_briefing",
        "generate_standup",
        "analyze_meeting",
        "nudge_colleague",
        "negotiate_meeting",
        "chat_to_jira",
        "smart_ooo_handoff",
        "analyze_onedrive_transcript",
    ]
    for tool in known_tools:
        prompt = get_system_prompt(tool)
        assert isinstance(prompt, str), f"Expected str for {tool}"
        assert len(prompt) > 20, f"Prompt too short for {tool}"


def test_unknown_tool_returns_default_prompt():
    prompt = get_system_prompt("some_unknown_tool_xyz")
    assert "Tagent" in prompt
    assert "markdown" in prompt.lower() or "format" in prompt.lower()


def test_daily_briefing_prompt_covers_key_sections():
    prompt = get_system_prompt("get_daily_briefing")
    assert "Today's Schedule" in prompt
    assert "Jira" in prompt
    assert "Pull Request" in prompt


def test_standup_prompt_covers_sections():
    prompt = get_system_prompt("generate_standup")
    assert "Yesterday" in prompt
    assert "Today" in prompt
    assert "Blockers" in prompt


def test_analyze_meeting_prompt_covers_sections():
    prompt = get_system_prompt("analyze_meeting")
    assert "Action Items" in prompt
    assert "Participants" in prompt
