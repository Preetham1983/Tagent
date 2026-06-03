"""External MCP adapter for calling third-party MCP servers over stdio or HTTP."""

from __future__ import annotations

import json
import os
from datetime import timedelta

from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CallToolResult, Tool


class ExternalMCPAdapter:
    """Call external MCP tools over stdio or HTTP (official Microsoft remote servers)."""

    def __init__(
        self,
        command: str = "",
        args: list[str] | None = None,
        cwd: str | None = None,
        http_url: str = "",
        summary_tool: str = "",
        timeout_seconds: int = 20,
    ) -> None:
        self._command = command.strip()
        self._args = args or []
        self._cwd = cwd or None
        self._http_url = http_url.strip()
        self._summary_tool = summary_tool.strip()
        self._timeout_seconds = timeout_seconds

    @staticmethod
    def _load_cached_token() -> str:
        """Load delegated access token from tagent cache."""
        import time
        cache_file = os.path.join(os.path.expanduser("~"), ".tagent", "ms_graph_token_cache.json")
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                cached = json.load(f)
            token = cached.get("access_token", "")
            expiry = float(cached.get("token_expiry", 0))
            if token and time.time() < expiry - 60:
                return token
        except Exception:
            pass
        return ""

    @staticmethod
    def _parse_args(args_text: str) -> list[str]:
        """Parse args from JSON list or whitespace-delimited text."""
        text = (args_text or "").strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                raw = json.loads(text)
                if isinstance(raw, list):
                    return [str(x) for x in raw]
            except Exception:
                return []
        return [x for x in text.split(" ") if x]

    def enabled(self) -> bool:
        return bool(self._command or self._http_url)

    def _is_http(self) -> bool:
        return bool(self._http_url)

    def _tool_name(self, tool: Tool) -> str:
        return str(getattr(tool, "name", "") or "")

    def _pick_summary_tool(self, tools: list[Tool]) -> Tool | None:
        if not tools:
            return None

        # Explicit tool wins.
        if self._summary_tool:
            for t in tools:
                if self._tool_name(t) == self._summary_tool:
                    return t

        # Heuristic fallback based on name/description.
        preferred_tokens = (
            "summarize",
            "summary",
            "meeting",
            "transcript",
            "notes",
            "calendar",
            "work",
            "chat",
        )

        scored: list[tuple[int, Tool]] = []
        for t in tools:
            name = self._tool_name(t).lower()
            desc = str(getattr(t, "description", "") or "").lower()
            text = f"{name} {desc}"
            score = sum(1 for token in preferred_tokens if token in text)
            scored.append((score, t))

        scored.sort(key=lambda x: x[0], reverse=True)
        best_score, best_tool = scored[0]
        return best_tool if best_score > 0 else None

    def _candidate_arg_payloads(self, tool: Tool, query: str) -> list[dict]:
        schema = getattr(tool, "inputSchema", None) or {}
        properties = schema.get("properties") or {}
        required = schema.get("required") or []

        preferred_keys = ["query", "text", "message", "prompt", "input", "question", "content"]
        payloads: list[dict] = []

        for key in preferred_keys:
            if key in properties:
                payloads.append({key: query})

        if len(required) == 1:
            payloads.append({required[0]: query})

        if not properties:
            payloads.append({"query": query})
            payloads.append({})

        # Deduplicate while preserving order.
        seen = set()
        deduped: list[dict] = []
        for p in payloads:
            marker = json.dumps(p, sort_keys=True)
            if marker not in seen:
                seen.add(marker)
                deduped.append(p)

        return deduped or [{}]

    @staticmethod
    def _extract_text(result: CallToolResult) -> str:
        parts: list[str] = []
        for item in result.content:
            text = getattr(item, "text", None)
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())

        if parts:
            return "\n".join(parts)

        if result.structuredContent:
            return json.dumps(result.structuredContent, ensure_ascii=True)

        return ""

    async def summarize_from_query(self, query: str, prefer_tool: str = "") -> str | None:
        """Call a best-match external MCP tool (stdio or remote HTTP)."""
        if not self.enabled():
            return None

        try:
            if self._is_http():
                return await self._call_http(query, prefer_tool)
            return await self._call_stdio(query, prefer_tool)
        except Exception as exc:
            return f"(External MCP unavailable: {str(exc)[:200]})"

    async def _call_http(self, query: str, prefer_tool: str) -> str | None:
        """Call a remote HTTP MCP server (e.g., official Microsoft agent365 MCPs)."""
        token = self._load_cached_token()
        headers: dict[str, str] = {}
        if token:
            headers["Authorization"] = f"Bearer {token}"

        async with streamablehttp_client(
            self._http_url,
            headers=headers or None,
            timeout=float(self._timeout_seconds),
        ) as (read_stream, write_stream, _):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                resolved_prefer = prefer_tool or self._summary_tool
                tool = None
                if resolved_prefer:
                    for t in tools_result.tools:
                        if self._tool_name(t) == resolved_prefer:
                            tool = t
                            break
                if tool is None:
                    tool = self._pick_summary_tool(tools_result.tools)
                if tool is None:
                    # No matching tool but list succeeded — return tool names for debugging
                    names = [self._tool_name(t) for t in tools_result.tools]
                    return f"(MCP connected. Available tools: {names}. No matching tool for query.)"
                return await self._invoke_tool(session, tool, query)

    async def _call_stdio(self, query: str, prefer_tool: str) -> str | None:
        """Call a local stdio MCP server."""
        params = StdioServerParameters(
            command=self._command,
            args=self._args,
            cwd=self._cwd,
        )
        async with stdio_client(params) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools_result = await session.list_tools()
                resolved_prefer = prefer_tool or self._summary_tool
                tool = None
                if resolved_prefer:
                    for t in tools_result.tools:
                        if self._tool_name(t) == resolved_prefer:
                            tool = t
                            break
                if tool is None:
                    tool = self._pick_summary_tool(tools_result.tools)
                if tool is None:
                    return None
                return await self._invoke_tool(session, tool, query)

    async def _invoke_tool(self, session: ClientSession, tool: Tool, query: str) -> str | None:
        tool_name = self._tool_name(tool)
        read_timeout = timedelta(seconds=self._timeout_seconds)
        last_error = ""
        for payload in self._candidate_arg_payloads(tool, query):
            try:
                result = await session.call_tool(
                    tool_name,
                    payload,
                    read_timeout_seconds=read_timeout,
                )
                text = self._extract_text(result)
                if result.isError:
                    last_error = text or "tool returned error"
                    continue
                if text:
                    return text
                if result.structuredContent is not None:
                    return json.dumps(result.structuredContent, ensure_ascii=False)
            except Exception as exc:
                last_error = str(exc)
                continue
        return f"(External MCP tool failed: {last_error[:200]})" if last_error else None


_default_adapter: ExternalMCPAdapter | None = None


def get_external_mcp_adapter() -> ExternalMCPAdapter:
    """Return singleton external MCP adapter from Settings."""
    global _default_adapter
    if _default_adapter is None:
        from tagent.infrastructure.config.settings import Settings

        s = Settings()
        args = ExternalMCPAdapter._parse_args(s.mcp_external_args)
        _default_adapter = ExternalMCPAdapter(
            command=s.mcp_external_command,
            args=args,
            cwd=s.mcp_external_cwd or None,
            http_url=s.mcp_external_http_url,
            summary_tool=s.mcp_external_summary_tool,
            timeout_seconds=s.mcp_external_timeout_seconds,
        )
    return _default_adapter
