"""Application settings loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration — loaded from .env or environment variables."""

    # Microsoft Graph API
    ms_tenant_id: str = ""
    ms_client_id: str = ""
    ms_client_secret: str = ""
    # Graph access mode: off | auto
    graph_mode: str = "off"

    # External MCP integration (local mcp-tools-service via stdio)
    mcp_external_enabled: bool = False
    mcp_external_command: str = ""
    mcp_external_args: str = ""
    mcp_external_cwd: str = ""
    mcp_external_type: str = "stdio"
    mcp_external_http_url: str = ""
    mcp_external_summary_tool: str = ""
    mcp_external_timeout_seconds: int = 20

    # Azure OpenAI
    azure_openai_endpoint: str = ""
    azure_openai_api_key: str = ""
    azure_openai_model: str = "gpt-4o"
    azure_openai_deployment: str = "gpt-4o"
    azure_openai_temperature: float = 0.0
    azure_openai_api_version: str = "2024-10-21"

    # Google Calendar MCP (official @cocal/google-calendar-mcp npm package)
    gcal_mcp_oauth_credentials: str = ""   # optional path to gcp-oauth.keys.json
    gcal_mcp_timeout_seconds: int = 30
    google_client_id: str = ""             # OAuth client_id (can be set instead of file)
    google_client_secret: str = ""         # OAuth client_secret

    # Jira
    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = ""

    # Database
    database_url: str = "sqlite+aiosqlite:///tagent.db"

    # Redis
    redis_url: str = "redis://localhost:6379"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
