"""Manage tasks use case — create/update Jira issues from conversation."""

from __future__ import annotations

from tagent.domain.entities.task import Task
from tagent.domain.interfaces.jira_port import JiraPort


class ManageTasksUseCase:
    """CRUD operations on Jira tasks driven by conversation context."""

    def __init__(self, jira: JiraPort) -> None:
        self._jira = jira

    async def create_task(self, task: Task) -> Task:
        return await self._jira.create_issue(task)

    async def update_task(self, jira_key: str, updates: dict) -> Task:
        return await self._jira.update_issue(jira_key, updates)

    async def search_tasks(self, jql: str) -> list[Task]:
        return await self._jira.search_issues(jql)
