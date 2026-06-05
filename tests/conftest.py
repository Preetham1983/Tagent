"""Basic test configuration."""

import sys
from pathlib import Path

import pytest

# Add service source roots so tests can import tagent packages directly
_orch_src = Path(__file__).resolve().parents[1] / "backend/services/orchestrator-service/src"
_mcp_src = Path(__file__).resolve().parents[1] / "backend/services/mcp-tools-service/src"

for _p in [str(_orch_src), str(_mcp_src)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


@pytest.fixture
def anyio_backend():
    return "asyncio"
