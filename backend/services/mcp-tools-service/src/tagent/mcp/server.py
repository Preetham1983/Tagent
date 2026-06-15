"""MCP tool server — exposes tools to the LangGraph agent."""

from __future__ import annotations

import sys

from mcp.server.fastmcp import FastMCP

_TOOL_MODULES = [
    ("tagent.mcp.tools.meeting_tools", "register_meeting_tools"),
    ("tagent.mcp.tools.graph_api_tools", "register_graph_api_tools"),
    ("tagent.mcp.tools.calendar_tools", "register_calendar_tools"),
    ("tagent.mcp.tools.briefing_tools", "register_briefing_tools"),
    ("tagent.mcp.tools.automation_tools", "register_automation_tools"),
    ("tagent.mcp.tools.jira_tools", "register_jira_tools"),
    ("tagent.mcp.tools.teams_tools", "register_teams_tools"),
    ("tagent.mcp.tools.memory_tools", "register_memory_tools"),
    ("tagent.mcp.tools.github_tools", "register_github_tools"),
    ("tagent.mcp.tools.notion_tools", "register_notion_tools"),
]


def create_mcp_server() -> FastMCP:
    """Create and configure the MCP tool server with all available tools."""
    import importlib

    mcp = FastMCP("tagent-tools")

    for module_path, fn_name in _TOOL_MODULES:
        try:
            mod = importlib.import_module(module_path)
            getattr(mod, fn_name)(mcp)
        except Exception as exc:
            print(f"[tagent-mcp] Skipping {module_path}: {exc}", file=sys.stderr)

    return mcp


def run_mcp_server() -> None:
    """Run the MCP server over stdio."""
    mcp = create_mcp_server()
    # FastMCP.run() is synchronous and handles its own event loop.
    mcp.run()
