"""GitHub tools for MCP — GitHub REST API integration."""

from __future__ import annotations

import os

import httpx
from mcp.server import Server


def _get_github_config() -> dict:
    return {
        "token": os.environ.get("GITHUB_TOKEN", ""),
        "default_owner": os.environ.get("GITHUB_DEFAULT_OWNER", ""),
        "default_repo": os.environ.get("GITHUB_DEFAULT_REPO", ""),
    }


def _get_github_headers(config: dict) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if config["token"]:
        headers["Authorization"] = f"Bearer {config['token']}"
    return headers


def register_github_tools(server: Server) -> None:
    """Register GitHub tools."""

    @server.tool()
    async def list_github_repos(owner: str = "") -> dict:
        """List GitHub repositories for a user or the authenticated user."""
        config = _get_github_config()
        if not config["token"]:
            return {"status": "not_configured", "message": "GITHUB_TOKEN not set.", "repos": []}

        # If an explicit owner was passed in the query, list that user's public repos.
        # Otherwise use /user/repos which lists ALL repos for the authenticated token
        # (avoids 404 from username mismatches with /users/{name}/repos).
        if owner.strip():
            url = f"https://api.github.com/users/{owner.strip()}/repos"
            params: dict = {"sort": "updated", "per_page": 30, "type": "all"}
        else:
            url = "https://api.github.com/user/repos"
            params = {"sort": "updated", "per_page": 30, "affiliation": "owner,collaborator"}

        try:
            async with httpx.AsyncClient(timeout=15) as http:
                r = await http.get(url, headers=_get_github_headers(config), params=params)
                if r.status_code == 200:
                    repos = [
                        {
                            "name": repo["name"],
                            "full_name": repo["full_name"],
                            "description": repo.get("description") or "",
                            "language": repo.get("language") or "",
                            "stars": repo["stargazers_count"],
                            "open_issues": repo["open_issues_count"],
                            "private": repo.get("private", False),
                            "updated_at": repo["updated_at"],
                            "url": repo["html_url"],
                        }
                        for repo in r.json()
                    ]
                    return {"status": "ok", "total": len(repos), "repos": repos}
                return {"status": "error", "message": f"GitHub API {r.status_code}: {r.text[:300]}"}
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:200]}

    @server.tool()
    async def list_github_prs(repo: str = "", owner: str = "", state: str = "open") -> dict:
        """List pull requests for a GitHub repository."""
        config = _get_github_config()
        if not config["token"]:
            return {"status": "not_configured", "message": "GITHUB_TOKEN not set.", "prs": []}

        repo_name = repo or config["default_repo"]
        owner_name = owner or config["default_owner"]
        if not repo_name or not owner_name:
            return {
                "status": "error",
                "message": "Provide owner and repo, or set GITHUB_DEFAULT_OWNER and GITHUB_DEFAULT_REPO.",
            }

        try:
            async with httpx.AsyncClient(timeout=15) as http:
                r = await http.get(
                    f"https://api.github.com/repos/{owner_name}/{repo_name}/pulls",
                    headers=_get_github_headers(config),
                    params={"state": state, "per_page": 20, "sort": "updated"},
                )
                if r.status_code == 200:
                    prs = [
                        {
                            "number": pr["number"],
                            "title": pr["title"],
                            "author": pr["user"]["login"],
                            "state": pr["state"],
                            "draft": pr.get("draft", False),
                            "created_at": pr["created_at"],
                            "updated_at": pr["updated_at"],
                            "url": pr["html_url"],
                            "base": pr["base"]["ref"],
                            "head": pr["head"]["ref"],
                        }
                        for pr in r.json()
                    ]
                    return {
                        "status": "ok",
                        "repo": f"{owner_name}/{repo_name}",
                        "total": len(prs),
                        "prs": prs,
                    }
                return {"status": "error", "message": r.text[:300]}
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:200]}

    @server.tool()
    async def list_github_issues(
        repo: str = "", owner: str = "", state: str = "open", labels: str = ""
    ) -> dict:
        """List issues for a GitHub repository (excludes pull requests)."""
        config = _get_github_config()
        if not config["token"]:
            return {"status": "not_configured", "message": "GITHUB_TOKEN not set.", "issues": []}

        repo_name = repo or config["default_repo"]
        owner_name = owner or config["default_owner"]
        if not repo_name or not owner_name:
            return {
                "status": "error",
                "message": "Provide owner and repo, or set GITHUB_DEFAULT_OWNER and GITHUB_DEFAULT_REPO.",
            }

        params: dict = {"state": state, "per_page": 20, "sort": "updated"}
        if labels:
            params["labels"] = labels

        try:
            async with httpx.AsyncClient(timeout=15) as http:
                r = await http.get(
                    f"https://api.github.com/repos/{owner_name}/{repo_name}/issues",
                    headers=_get_github_headers(config),
                    params=params,
                )
                if r.status_code == 200:
                    issues = [
                        {
                            "number": issue["number"],
                            "title": issue["title"],
                            "author": issue["user"]["login"],
                            "state": issue["state"],
                            "labels": [lbl["name"] for lbl in issue.get("labels", [])],
                            "assignees": [a["login"] for a in issue.get("assignees", [])],
                            "created_at": issue["created_at"],
                            "url": issue["html_url"],
                        }
                        for issue in r.json()
                        if "pull_request" not in issue  # skip PRs
                    ]
                    return {
                        "status": "ok",
                        "repo": f"{owner_name}/{repo_name}",
                        "total": len(issues),
                        "issues": issues,
                    }
                return {"status": "error", "message": r.text[:300]}
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:200]}

    @server.tool()
    async def create_github_issue(
        title: str,
        body: str = "",
        labels: str = "",
        repo: str = "",
        owner: str = "",
    ) -> dict:
        """Create a new issue in a GitHub repository."""
        config = _get_github_config()
        if not config["token"]:
            return {"status": "not_configured", "message": "GITHUB_TOKEN not set."}

        repo_name = repo or config["default_repo"]
        owner_name = owner or config["default_owner"]
        if not repo_name or not owner_name:
            return {
                "status": "error",
                "message": "Provide owner and repo, or set GITHUB_DEFAULT_OWNER and GITHUB_DEFAULT_REPO.",
            }

        payload: dict = {"title": title}
        if body:
            payload["body"] = body
        if labels:
            payload["labels"] = [lbl.strip() for lbl in labels.split(",")]

        try:
            async with httpx.AsyncClient(timeout=15) as http:
                r = await http.post(
                    f"https://api.github.com/repos/{owner_name}/{repo_name}/issues",
                    headers=_get_github_headers(config),
                    json=payload,
                )
                if r.status_code == 201:
                    data = r.json()
                    return {
                        "status": "ok",
                        "number": data["number"],
                        "url": data["html_url"],
                        "title": data["title"],
                    }
                return {"status": "error", "message": r.text[:300]}
        except Exception as exc:
            return {"status": "error", "message": str(exc)[:200]}
