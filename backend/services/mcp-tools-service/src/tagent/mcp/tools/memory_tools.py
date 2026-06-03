"""Memory tools for MCP — persist and retrieve user/session context."""

from __future__ import annotations

import json
import os

from mcp.server import Server

_MEMORY_DIR = os.path.join(os.path.expanduser("~"), ".tagent", "memory")


def _ensure_memory_dir() -> None:
    os.makedirs(_MEMORY_DIR, exist_ok=True)


def _user_file(user_id: str) -> str:
    # Sanitize user_id for filename
    safe_id = "".join(c if c.isalnum() or c in "-_" else "_" for c in user_id)
    return os.path.join(_MEMORY_DIR, f"{safe_id}.json")


def _load_user_memory(user_id: str) -> dict:
    path = _user_file(user_id)
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_user_memory(user_id: str, data: dict) -> None:
    _ensure_memory_dir()
    path = _user_file(user_id)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def register_memory_tools(server: Server) -> None:
    """Register memory tools (store, retrieve, search context)."""

    @server.tool()
    async def store_memory(user_id: str, key: str, value: str) -> dict:
        """Store a memory entry for a user. Persists across sessions."""
        try:
            data = _load_user_memory(user_id)
            data[key] = value
            _save_user_memory(user_id, data)
            return {"status": "ok", "user_id": user_id, "key": key, "stored": True}
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:200]}

    @server.tool()
    async def retrieve_memory(user_id: str, key: str) -> dict:
        """Retrieve a stored memory entry for a user."""
        try:
            data = _load_user_memory(user_id)
            value = data.get(key)
            return {
                "status": "ok",
                "user_id": user_id,
                "key": key,
                "value": value,
                "found": value is not None,
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:200]}

    @server.tool()
    async def list_memories(user_id: str) -> dict:
        """List all stored memory keys for a user."""
        try:
            data = _load_user_memory(user_id)
            return {
                "status": "ok",
                "user_id": user_id,
                "keys": list(data.keys()),
                "count": len(data),
            }
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:200]}
