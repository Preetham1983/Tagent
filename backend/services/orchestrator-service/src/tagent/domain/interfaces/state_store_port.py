from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class StateStorePort(ABC):
    @abstractmethod
    async def save_state(self, key: str, state: dict[str, Any]) -> None: ...

    @abstractmethod
    async def load_state(self, key: str) -> dict[str, Any] | None: ...

    @abstractmethod
    async def delete_state(self, key: str) -> None: ...

    @abstractmethod
    async def save_checkpoint(self, thread_id: str, checkpoint: dict[str, Any]) -> str: ...

    @abstractmethod
    async def load_checkpoint(self, checkpoint_id: str) -> dict[str, Any] | None: ...
