"""
Vercel serverless entry — exposes the orchestrator FastAPI app.

Vercel's @vercel/python runtime auto-detects the ASGI `app` variable
and serves it under the /api/* path prefix via rewrites in vercel.json.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# ── 1. Fix Python path so `tagent.*` imports resolve ──────────────────────
_project_root = Path(__file__).resolve().parent
_orch_src = _project_root / "backend" / "services" / "orchestrator-service" / "src"
_mcp_src = _project_root / "backend" / "services" / "mcp-tools-service" / "src"
_orch_root = _project_root / "backend" / "services" / "orchestrator-service"

for p in [str(_orch_src), str(_mcp_src), str(_orch_root)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# ── 2. Set MCP subprocess environment for serverless ──────────────────────
_mcp_cwd = str(_project_root / "backend" / "services" / "mcp-tools-service")
os.environ.setdefault("MCP_EXTERNAL_CWD", _mcp_cwd)
os.environ.setdefault("MCP_EXTERNAL_COMMAND", "python")
os.environ.setdefault("MCP_EXTERNAL_ARGS", '["main.py"]')
os.environ.setdefault("MCP_EXTERNAL_ENABLED", "true")
os.environ.setdefault("MCP_EXTERNAL_TYPE", "stdio")

# ── 3. Load .env from orchestrator if it exists (fallback for local) ──────
_env_file = _orch_root / ".env"
if _env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(str(_env_file), override=False)
    except ImportError:
        pass

# ── 4. Import the FastAPI app ─────────────────────────────────────────────
# This is the same FastAPI `app` defined in orchestrator-service/main.py
from main import app  # noqa: E402, F401
