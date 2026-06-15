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
_project_root = Path(__file__).resolve().parent.parent
_orch_src = _project_root / "backend" / "services" / "orchestrator-service" / "src"
_mcp_src = _project_root / "backend" / "services" / "mcp-tools-service" / "src"
_orch_root = _project_root / "backend" / "services" / "orchestrator-service"

for p in [str(_orch_src), str(_mcp_src), str(_orch_root)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# ── 2. Set MCP subprocess environment for serverless ──────────────────────
# Force-set path vars — never let stale dashboard env vars (e.g. Windows paths) win.
_mcp_cwd = str(_project_root / "backend" / "services" / "mcp-tools-service")
os.environ["MCP_EXTERNAL_CWD"] = _mcp_cwd
# Use the same interpreter running this process so the subprocess inherits packages.
os.environ["MCP_EXTERNAL_COMMAND"] = sys.executable
os.environ["MCP_EXTERNAL_ARGS"] = '["main.py"]'
os.environ.setdefault("MCP_EXTERNAL_ENABLED", "true")
os.environ.setdefault("MCP_EXTERNAL_TYPE", "stdio")
# Pass sys.path so the subprocess can find packages installed by uv.
os.environ["PYTHONPATH"] = os.pathsep.join(p for p in sys.path if p)

# ── 2b. Token cache — /tmp is writable on Vercel; ~ (/root) is read-only ──
os.environ.setdefault("TOKEN_CACHE_DIR", "/tmp/.tagent")

# ── 3. Load .env from orchestrator if it exists (fallback for local) ──────
_env_file = _orch_root / ".env"
if _env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(str(_env_file), override=False)
    except ImportError:
        pass

# Declare app globally at the top level so Vercel's AST parser detects it
app = None

# ── 4. Import the FastAPI app ─────────────────────────────────────────────
try:
    from main import app as _real_app

    # Vercel passes the full request path (e.g. /api/orchestrate) to the ASGI
    # app, but the orchestrator's routes are registered without the /api prefix.
    # Strip it here so FastAPI can match them.
    async def app(scope, receive, send):
        if scope["type"] in ("http", "websocket"):
            path = scope.get("path", "")
            if path.startswith("/api"):
                scope = dict(scope)
                scope["path"] = path[4:] or "/"
                raw_path = scope.get("raw_path", b"")
                if isinstance(raw_path, bytes) and raw_path.startswith(b"/api"):
                    scope["raw_path"] = raw_path[4:] or b"/"
        await _real_app(scope, receive, send)

except Exception as e:
    import traceback
    _err = traceback.format_exc()
    _path_info = "\n".join(sys.path)
    try:
        _ls = str(list(_project_root.iterdir()))
    except Exception as e2:
        _ls = f"Error listing root: {e2}"

    async def app(scope, receive, send):
        await send({
            "type": "http.response.start",
            "status": 500,
            "headers": [[b"content-type", b"text/plain"]],
        })
        await send({
            "type": "http.response.body",
            "body": f"Import Error:\n{_err}\n\nSYS PATH:\n{_path_info}\n\nROOT DIR:\n{_ls}".encode(),
        })
