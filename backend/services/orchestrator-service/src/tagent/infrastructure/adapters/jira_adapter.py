"""Jira REST API adapter — implements JiraPort."""

from __future__ import annotations

from tagent.domain.entities.task import Task
from tagent.domain.interfaces.jira_port import JiraPort


class JiraAdapter(JiraPort):
    """Concrete adapter for Jira REST API."""

    def __init__(self, base_url: str, email: str, api_token: str, project_key: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._email = email
        self._api_token = api_token
        self._project_key = project_key
        # TODO: Initialize httpx async client with basic auth

    async def create_issue(self, task: Task) -> Task:
        # TODO: POST /rest/api/3/issue
        raise NotImplementedError

    async def update_issue(self, jira_key: str, updates: dict) -> Task:
        # TODO: PUT /rest/api/3/issue/{jira_key}
        raise NotImplementedError

    async def get_issue(self, jira_key: str) -> Task:
        # TODO: GET /rest/api/3/issue/{jira_key}
        raise NotImplementedError

    async def search_issues(self, jql: str) -> list[Task]:
        # TODO: POST /rest/api/3/search
        raise NotImplementedError

    async def add_comment(self, jira_key: str, comment: str) -> None:
        # TODO: POST /rest/api/3/issue/{jira_key}/comment
        raise NotImplementedError
