"""Shared FastAPI dependencies."""

from __future__ import annotations

from functools import lru_cache

from tagent.agents.graph import build_agent_graph


@lru_cache(maxsize=1)
def get_graph():
    """Build the LangGraph once at startup and reuse across all requests."""
    return build_agent_graph()
