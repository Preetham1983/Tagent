"""Azure OpenAI adapter — implements LLMPort."""

from __future__ import annotations

import httpx
from openai import AsyncAzureOpenAI

from tagent.domain.interfaces.llm_port import LLMPort

_default_adapter: "LLMAdapter | None" = None


def get_default_adapter() -> "LLMAdapter":
    """Return a module-level singleton LLMAdapter built from Settings."""
    global _default_adapter
    if _default_adapter is None:
        from tagent.infrastructure.config.settings import Settings

        s = Settings()
        _default_adapter = LLMAdapter(
            endpoint=s.azure_openai_endpoint,
            api_key=s.azure_openai_api_key,
            deployment=s.azure_openai_model,
            api_version=s.azure_openai_api_version,
        )
    return _default_adapter


class LLMAdapter(LLMPort):
    """Concrete adapter for Azure OpenAI API."""

    def __init__(
        self, endpoint: str, api_key: str, deployment: str, api_version: str
    ) -> None:
        # Generous timeouts for Docker environments where the proxy may be
        # reachable but slow on first connection (connect=5s default is too short).
        _timeout = httpx.Timeout(connect=30.0, read=120.0, write=30.0, pool=10.0)

        self._client = AsyncAzureOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
            http_client=httpx.AsyncClient(timeout=_timeout),
        )
        self._deployment = deployment

    async def complete(self, messages: list[dict[str, str]], **kwargs) -> str:
        response = await self._client.chat.completions.create(
            model=self._deployment,
            messages=messages,
            **kwargs,
        )
        return response.choices[0].message.content or ""

    async def structured_output(self, messages: list[dict[str, str]], schema: dict) -> dict:
        response = await self._client.chat.completions.create(
            model=self._deployment,
            messages=messages,
            response_format={"type": "json_schema", "json_schema": schema},
        )
        import json

        return json.loads(response.choices[0].message.content or "{}")
