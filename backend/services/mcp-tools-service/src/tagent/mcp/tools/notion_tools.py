"""Notion tools for MCP — Notion API integration."""

from __future__ import annotations

import os

import httpx
from mcp.server import Server


def _get_notion_config() -> dict:
    return {
        "token": os.environ.get("NOTION_TOKEN", ""),
        "default_database_id": os.environ.get("NOTION_DATABASE_ID", ""),
    }


def _get_notion_headers(config: dict) -> dict:
    return {
        "Authorization": f"Bearer {config['token']}",
        "Content-Type": "application/json",
        "Notion-Version": "2022-06-28",
    }


def _extract_title(properties: dict) -> str:
    for key in list(properties.keys()):
        val = properties[key]
        if val.get("type") == "title":
            arr = val.get("title", [])
            if arr:
                return arr[0].get("plain_text", "Untitled")
    return "Untitled"


def register_notion_tools(server: Server) -> None:
    """Register Notion tools."""

    @server.tool()
    async def search_notion(query: str) -> dict:
        """Search across all Notion pages and databases."""
        config = _get_notion_config()
        if not config["token"]:
            return {"status": "not_configured", "message": "NOTION_TOKEN not set.", "results": []}

        try:
            async with httpx.AsyncClient(timeout=15) as http:
                r = await http.post(
                    "https://api.notion.com/v1/search",
                    headers=_get_notion_headers(config),
                    json={"query": query, "page_size": 10},
                )
                if r.status_code == 200:
                    results = []
                    for item in r.json().get("results", []):
                        props = item.get("properties", {})
                        title = _extract_title(props) if props else "Untitled"
                        results.append({
                            "id": item["id"],
                            "type": item["object"],
                            "title": title,
                            "url": item.get("url", ""),
                            "last_edited": item.get("last_edited_time", ""),
                        })
                    return {"status": "ok", "total": len(results), "results": results}
                return {"status": "error", "message": r.text[:300]}
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:200]}

    @server.tool()
    async def list_notion_pages(database_id: str = "") -> dict:
        """List pages in a Notion database."""
        config = _get_notion_config()
        if not config["token"]:
            return {"status": "not_configured", "message": "NOTION_TOKEN not set.", "pages": []}

        db_id = database_id or config["default_database_id"]
        if not db_id:
            return {
                "status": "error",
                "message": "No database_id provided and NOTION_DATABASE_ID not set in config.",
            }

        try:
            async with httpx.AsyncClient(timeout=15) as http:
                r = await http.post(
                    f"https://api.notion.com/v1/databases/{db_id}/query",
                    headers=_get_notion_headers(config),
                    json={"page_size": 20},
                )
                if r.status_code == 200:
                    pages = [
                        {
                            "id": item["id"],
                            "title": _extract_title(item.get("properties", {})),
                            "url": item.get("url", ""),
                            "last_edited": item.get("last_edited_time", ""),
                        }
                        for item in r.json().get("results", [])
                    ]
                    return {"status": "ok", "total": len(pages), "pages": pages}
                return {"status": "error", "message": r.text[:300]}
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:200]}

    @server.tool()
    async def create_notion_page(
        title: str, content: str = "", database_id: str = ""
    ) -> dict:
        """Create a new page in a Notion database."""
        config = _get_notion_config()
        if not config["token"]:
            return {"status": "not_configured", "message": "NOTION_TOKEN not set."}

        db_id = database_id or config["default_database_id"]
        if not db_id:
            return {
                "status": "error",
                "message": "No database_id provided and NOTION_DATABASE_ID not set in config.",
            }

        payload: dict = {
            "parent": {"database_id": db_id},
            "properties": {
                "Name": {
                    "title": [{"type": "text", "text": {"content": title}}]
                }
            },
        }
        if content:
            payload["children"] = [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": content}}]
                    },
                }
            ]

        try:
            async with httpx.AsyncClient(timeout=15) as http:
                r = await http.post(
                    "https://api.notion.com/v1/pages",
                    headers=_get_notion_headers(config),
                    json=payload,
                )
                if r.status_code == 200:
                    data = r.json()
                    return {"status": "ok", "id": data["id"], "url": data.get("url", ""), "title": title}
                return {"status": "error", "message": r.text[:300]}
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:200]}
