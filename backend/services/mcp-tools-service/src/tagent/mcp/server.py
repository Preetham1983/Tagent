"""MCP tool server — exposes tools to the LangGraph agent."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from tagent.mcp.tools.briefing_tools import register_briefing_tools
from tagent.mcp.tools.calendar_tools import register_calendar_tools
from tagent.mcp.tools.automation_tools import register_automation_tools
from tagent.mcp.tools.github_tools import register_github_tools
from tagent.mcp.tools.graph_api_tools import register_graph_api_tools
from tagent.mcp.tools.jira_tools import register_jira_tools
from tagent.mcp.tools.meeting_tools import register_meeting_tools
from tagent.mcp.tools.memory_tools import register_memory_tools
from tagent.mcp.tools.notion_tools import register_notion_tools
from tagent.mcp.tools.teams_tools import register_teams_tools


def create_mcp_server() -> FastMCP:
    """Create and configure the MCP tool server with all available tools."""
    mcp = FastMCP("tagent-tools")

    register_meeting_tools(mcp)
    register_graph_api_tools(mcp)
    register_calendar_tools(mcp)
    register_briefing_tools(mcp)
    register_automation_tools(mcp)
    register_jira_tools(mcp)
    register_teams_tools(mcp)
    register_memory_tools(mcp)
    register_github_tools(mcp)
    register_notion_tools(mcp)

    return mcp


def run_mcp_server() -> None:
    """Run the MCP server over stdio."""
    mcp = create_mcp_server()
    # FastMCP.run() is synchronous and handles its own event loop.
    mcp.run()
