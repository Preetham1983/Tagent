from __future__ import annotations

from abc import ABC, abstractmethod

from tagent.domain.entities.task import Task


class JiraPort(ABC):
    @abstractmethod
    async def create_issue(self, task: Task) -> Task: ...

    @abstractmethod
    async def update_issue(self, jira_key: str, updates: dict) -> Task: ...

    @abstractmethod
    async def get_issue(self, jira_key: str) -> Task: ...

    @abstractmethod
    async def search_issues(self, jql: str) -> list[Task]: ...

    @abstractmethod
    async def add_comment(self, jira_key: str, comment: str) -> None: ...
