"""Database adapter — implements StateStorePort for persistence."""

from __future__ import annotations

import json
import uuid
from typing import Any

from tagent.domain.interfaces.state_store_port import StateStorePort


class DatabaseAdapter(StateStorePort):
    """Simple in-memory state store. Replace with real DB in production."""

    def __init__(self) -> None:
        self._states: dict[str, dict[str, Any]] = {}
        self._checkpoints: dict[str, dict[str, Any]] = {}

    async def save_state(self, key: str, state: dict[str, Any]) -> None:
        self._states[key] = json.loads(json.dumps(state, default=str))

    async def load_state(self, key: str) -> dict[str, Any] | None:
        return self._states.get(key)

    async def delete_state(self, key: str) -> None:
        self._states.pop(key, None)

    async def save_checkpoint(self, thread_id: str, checkpoint: dict[str, Any]) -> str:
        checkpoint_id = str(uuid.uuid4())
        self._checkpoints[checkpoint_id] = {
            "thread_id": thread_id,
            "data": json.loads(json.dumps(checkpoint, default=str)),
        }
        return checkpoint_id

    async def load_checkpoint(self, checkpoint_id: str) -> dict[str, Any] | None:
        entry = self._checkpoints.get(checkpoint_id)
        return entry["data"] if entry else None
