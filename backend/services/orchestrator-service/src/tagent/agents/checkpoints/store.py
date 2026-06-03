"""Checkpoint store for LangGraph human-in-the-loop persistence."""

from __future__ import annotations

from typing import Any

from tagent.domain.interfaces.state_store_port import StateStorePort


class CheckpointStore:
    """Manages graph checkpoint persistence through the state store port."""

    def __init__(self, state_store: StateStorePort) -> None:
        self._store = state_store

    async def save(self, thread_id: str, checkpoint: dict[str, Any]) -> str:
        return await self._store.save_checkpoint(thread_id, checkpoint)

    async def load(self, checkpoint_id: str) -> dict[str, Any] | None:
        return await self._store.load_checkpoint(checkpoint_id)
