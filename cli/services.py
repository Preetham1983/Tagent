"""Service lifecycle management — start, stop, status for Tagent services."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import httpx

from cli.constants import (
    FRONTEND_DIR,
    FRONTEND_PORT,
    HEALTH_URL,
    ORCHESTRATOR_DIR,
    ORCHESTRATOR_PORT,
    ORCHESTRATOR_URL,
    PIDFILE_DIR,
    PROJECT_ROOT,
    SETTINGS_URL,
)


def _pidfile(name: str) -> Path:
    PIDFILE_DIR.mkdir(parents=True, exist_ok=True)
    return PIDFILE_DIR / f"{name}.pid"


def _write_pid(name: str, pid: int) -> None:
    _pidfile(name).write_text(str(pid))


def _read_pid(name: str) -> int | None:
    pf = _pidfile(name)
    if pf.exists():
        try:
            return int(pf.read_text().strip())
        except ValueError:
            return None
    return None


def _clear_pid(name: str) -> None:
    pf = _pidfile(name)
    if pf.exists():
        pf.unlink()


def _is_running(pid: int) -> bool:
    """Check if a process with the given PID is running."""
    if sys.platform == "win32":
        try:
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"],
                capture_output=True, text=True, timeout=5,
            )
            return str(pid) in result.stdout
        except Exception:
            return False
    else:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def start_services(verbose: bool = False, stream_output: bool = False) -> dict[str, str]:
    """Start the orchestrator and frontend services via Docker Compose. Returns status dict."""
    results = {}
    
    try:
        kwargs = {
            "cwd": str(PROJECT_ROOT),
        }
        if stream_output:
            kwargs["stdout"] = sys.stdout
            kwargs["stderr"] = sys.stderr
        else:
            kwargs["capture_output"] = True
            kwargs["text"] = True

        proc = subprocess.run(
            ["docker", "compose", "up", "--build", "-d"],
            **kwargs
        )
        if proc.returncode == 0:
            results["docker"] = "started via docker compose"
        else:
            err = proc.stderr.strip() if hasattr(proc, "stderr") and proc.stderr else "check docker logs"
            results["docker"] = f"error: {err}"
    except Exception as exc:
        results["docker"] = f"failed to execute docker: {exc}"

    return results


def stop_services() -> dict[str, str]:
    """Kill all managed services using Docker Compose down. Returns status dict."""
    results = {}
    try:
        proc = subprocess.run(
            ["docker", "compose", "down"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        if proc.returncode == 0:
            results["docker"] = "stopped via docker compose"
        else:
            results["docker"] = f"error: {proc.stderr.strip()}"
    except Exception as exc:
        results["docker"] = f"failed to execute docker: {exc}"
    return results


def get_service_status() -> dict[str, dict]:
    """Return live status of each service."""
    statuses = {}

    for name, port in [("orchestrator", ORCHESTRATOR_PORT), ("frontend", FRONTEND_PORT)]:
        pid = _read_pid(name)
        running = bool(pid and _is_running(pid))
        statuses[name] = {
            "running": running,
            "pid": pid if running else None,
            "port": port,
        }

    # Health check the orchestrator API
    try:
        r = httpx.get(HEALTH_URL, timeout=3)
        statuses["orchestrator"]["healthy"] = r.status_code == 200
    except Exception:
        statuses["orchestrator"]["healthy"] = False

    return statuses


def get_integration_status() -> dict | None:
    """Fetch integration status from the orchestrator API."""
    try:
        r = httpx.get(SETTINGS_URL, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return None
