"""
Vercel serverless function for the Teams Bot adapter.
Handles /api/messages — the Microsoft Bot Framework messaging endpoint.

This converts the aiohttp-based Teams bot into a FastAPI handler
so it can run on Vercel's Python serverless runtime.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

# ── Fix Python paths ──────────────────────────────────────────────────────
_project_root = Path(__file__).resolve().parent.parent
_teams_src = _project_root / "backend" / "services" / "teams-adapter-service" / "src"
_orch_src = _project_root / "backend" / "services" / "orchestrator-service" / "src"

for p in [str(_teams_src), str(_orch_src)]:
    if p not in sys.path:
        sys.path.insert(0, p)

# ── Load .env ─────────────────────────────────────────────────────────────
_env_file = _project_root / "backend" / "services" / "teams-adapter-service" / ".env"
if _env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(str(_env_file), override=False)
    except ImportError:
        pass

# ── Import bot components ─────────────────────────────────────────────────
from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext
from botbuilder.schema import Activity

from tagent.bot.controllers.message_controller import MessageController

# ── Configure ─────────────────────────────────────────────────────────────
_app_id = os.environ.get("MS_APP_ID", "")
_app_password = os.environ.get("MS_APP_PASSWORD", "")
_orchestrator_url = os.environ.get(
    "ORCHESTRATOR_BASE_URL",
    os.environ.get("VERCEL_URL", "http://localhost:3000")
)

# If ORCHESTRATOR_BASE_URL is not set, use the same Vercel deployment URL
# so the bot calls back to /api/* routes on the same domain
if not os.environ.get("ORCHESTRATOR_BASE_URL") and os.environ.get("VERCEL_URL"):
    _orchestrator_url = f"https://{os.environ['VERCEL_URL']}/api"

_adapter_settings = BotFrameworkAdapterSettings(
    app_id=_app_id,
    app_password=_app_password,
)
_adapter = BotFrameworkAdapter(_adapter_settings)
_controller = MessageController(_orchestrator_url)

# ── FastAPI app for this function ─────────────────────────────────────────
app = FastAPI()


@app.post("/api/messages")
async def messages(request: Request):
    """Bot Framework messaging endpoint — Teams sends activities here."""
    if request.headers.get("content-type", "").startswith("application/json"):
        body = await request.json()
    else:
        return JSONResponse(status_code=415, content={"error": "Unsupported Media Type"})

    activity = Activity().deserialize(body)
    auth_header = request.headers.get("Authorization", "")

    async def _call_bot(turn_context: TurnContext) -> None:
        await _controller.on_turn(turn_context)

    try:
        await _adapter.process_activity(activity, auth_header, _call_bot)
        return JSONResponse(status_code=201, content={})
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": str(exc)[:300]})
