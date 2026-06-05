"""Pydantic request/response schemas for the API layer."""

from __future__ import annotations

from pydantic import BaseModel, Field


class OrchestrateRequest(BaseModel):
    user_id: str
    thread_id: str
    message: str = Field(min_length=1)


class ApproveRequest(BaseModel):
    thread_id: str
    approved: bool
    user_id: str = ""


class JiraSettingsRequest(BaseModel):
    jira_base_url: str = ""
    jira_email: str = ""
    jira_api_token: str = ""
    jira_project_key: str = ""


class GoogleCalendarSettingsRequest(BaseModel):
    credentials_path: str = ""


class CalendarSettingsRequest(BaseModel):
    timezone: str


class DirectToolRequest(BaseModel):
    tool_name: str
    query: str = ""
    jql: str = ""
    title: str = ""
    description: str = ""
    priority: str = "Medium"
    user_id: str = ""
