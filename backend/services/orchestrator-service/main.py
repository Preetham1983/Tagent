"""Tagent orchestrator service - application entrypoint.

Responsibilities of this file:
  - Load environment variables
  - Create the FastAPI app
  - Register CORS middleware
  - Mount all routers

Business logic lives in:
  src/tagent/api/routes/      -- HTTP route handlers
  src/tagent/application/     -- use cases and services
  src/tagent/agents/          -- LangGraph orchestration
  src/tagent/infrastructure/  -- adapters and config
"""

from __future__ import annotations

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tagent.api.routes import auth, health, orchestrate, settings, tools

app = FastAPI(title="tagent-orchestrator-service")

_raw_origins = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
_allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(health.router)
app.include_router(orchestrate.router)
app.include_router(auth.router)
app.include_router(settings.router)
app.include_router(tools.router)
