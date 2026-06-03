from __future__ import annotations

from pydantic_settings import BaseSettings


class TeamsAdapterSettings(BaseSettings):
    ms_app_id: str = ""
    ms_app_password: str = ""
    orchestrator_base_url: str = "http://localhost:8001"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}
