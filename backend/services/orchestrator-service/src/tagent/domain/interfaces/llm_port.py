from __future__ import annotations

from abc import ABC, abstractmethod


class LLMPort(ABC):
    @abstractmethod
    async def complete(self, messages: list[dict[str, str]], **kwargs) -> str: ...

    @abstractmethod
    async def structured_output(self, messages: list[dict[str, str]], schema: dict) -> dict: ...
