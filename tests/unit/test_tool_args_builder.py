"""Unit tests for tool_args_builder — no I/O, no mocking needed."""

from __future__ import annotations

import os

import pytest

from tagent.api.schemas import DirectToolRequest
from tagent.application.services.tool_args_builder import build_tool_args


def _req(**kwargs) -> DirectToolRequest:
    return DirectToolRequest(tool_name=kwargs.pop("tool_name"), **kwargs)


# ── Jira ──────────────────────────────────────────────────────────────────────

def test_list_jira_projects_returns_empty_args():
    assert build_tool_args(_req(tool_name="list_jira_projects")) == {}


def test_list_project_members_uses_query():
    args = build_tool_args(_req(tool_name="list_project_members", query="ITP"))
    assert args["project_key"] == "ITP"


def test_search_jira_issues_wraps_free_text():
    os.environ["JIRA_PROJECT_KEY"] = "ITP"
    args = build_tool_args(_req(tool_name="search_jira_issues", query="login bug"))
    assert 'text ~ "login bug"' in args["jql"]
    assert "ITP" in args["jql"]


def test_search_jira_issues_passes_jql_as_is():
    args = build_tool_args(_req(tool_name="search_jira_issues", jql="project = ITP AND status = Done"))
    assert args["jql"] == "project = ITP AND status = Done"


def test_create_jira_issue_uses_title_and_priority():
    args = build_tool_args(_req(tool_name="create_jira_issue", title="Fix login", priority="High"))
    assert args["title"] == "Fix login"
    assert args["priority"] == "High"


def test_create_jira_issue_falls_back_to_query():
    args = build_tool_args(_req(tool_name="create_jira_issue", query="Bug in signup"))
    assert args["title"] == "Bug in signup"


# ── GitHub ─────────────────────────────────────────────────────────────────────

def test_list_github_prs_default_state():
    args = build_tool_args(_req(tool_name="list_github_prs"))
    assert args["state"] == "open"


def test_create_github_issue_uses_title():
    args = build_tool_args(_req(tool_name="create_github_issue", title="Add dark mode"))
    assert args["title"] == "Add dark mode"
    assert args["body"] == ""


# ── Notion ─────────────────────────────────────────────────────────────────────

def test_search_notion_passes_query():
    args = build_tool_args(_req(tool_name="search_notion", query="sprint planning"))
    assert args["query"] == "sprint planning"


def test_list_notion_pages_returns_empty():
    assert build_tool_args(_req(tool_name="list_notion_pages")) == {}


# ── Teams ──────────────────────────────────────────────────────────────────────

def test_send_direct_message_splits_email_and_body():
    args = build_tool_args(_req(tool_name="send_direct_message", query="alice@example.com - Hey there"))
    assert args["recipient_email"] == "alice@example.com"
    assert args["message"] == "Hey there"


def test_send_direct_message_no_body_defaults_hello():
    args = build_tool_args(_req(tool_name="send_direct_message", query="alice@example.com"))
    assert args["message"] == "Hello!"


def test_send_direct_message_name_only_split():
    args = build_tool_args(_req(tool_name="send_direct_message", query="Alice Smith - Can we sync?"))
    assert args["recipient_email"] == "Alice Smith"
    assert args["message"] == "Can we sync?"


# ── Simple tools ───────────────────────────────────────────────────────────────

def test_get_user_info_returns_empty():
    assert build_tool_args(_req(tool_name="get_user_info")) == {}


def test_get_daily_briefing_returns_empty():
    assert build_tool_args(_req(tool_name="get_daily_briefing")) == {}


def test_nudge_colleague_splits_query():
    args = build_tool_args(_req(tool_name="nudge_colleague", query="Bob, PROJ-42"))
    assert args["colleague_name"] == "Bob"
    assert args["item_id"] == "PROJ-42"


def test_nudge_colleague_default_item_id():
    args = build_tool_args(_req(tool_name="nudge_colleague", query="Bob"))
    assert args["item_id"] == "Task"


def test_negotiate_meeting_splits_query():
    args = build_tool_args(_req(tool_name="negotiate_meeting", query="Carol, Design review"))
    assert args["colleague_name"] == "Carol"
    assert args["topic"] == "Design review"


def test_smart_ooo_handoff_three_parts():
    args = build_tool_args(_req(tool_name="smart_ooo_handoff", query="Bob, 2026-06-10, 2026-06-20"))
    assert args["backup_colleague_name"] == "Bob"
    assert args["start_date"] == "2026-06-10"
    assert args["end_date"] == "2026-06-20"


def test_unknown_tool_falls_back_to_query():
    args = build_tool_args(_req(tool_name="some_future_tool", query="hello"))
    assert args == {"query": "hello"}


def test_unknown_tool_no_query_returns_empty():
    args = build_tool_args(_req(tool_name="some_future_tool"))
    assert args == {}
