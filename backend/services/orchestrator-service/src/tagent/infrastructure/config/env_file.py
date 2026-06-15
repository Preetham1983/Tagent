"""Helpers for reading/writing .env and persisting user preferences."""

from __future__ import annotations

import json
import os
from pathlib import Path


def update_env_file(updates: dict[str, str]) -> None:
    """Update specific keys in the .env file without touching other values.
    Silently skips if the filesystem is read-only (e.g. Vercel serverless).
    """
    env_path = Path(".env")
    try:
        if not env_path.exists():
            with open(env_path, "a", encoding="utf-8") as f:
                for key, value in updates.items():
                    f.write(f"{key}={value}\n")
            return

        lines = env_path.read_text(encoding="utf-8").splitlines(keepends=True)
        updated_keys: set[str] = set()
        new_lines: list[str] = []

        for line in lines:
            stripped = line.strip()
            if "=" in stripped and not stripped.startswith("#"):
                key = stripped.split("=", 1)[0].strip()
                if key in updates:
                    new_lines.append(f"{key}={updates[key]}\n")
                    updated_keys.add(key)
                    continue
            new_lines.append(line)

        for key, value in updates.items():
            if key not in updated_keys:
                new_lines.append(f"{key}={value}\n")

        env_path.write_text("".join(new_lines), encoding="utf-8")
    except (OSError, PermissionError):
        # Read-only filesystem (e.g. Vercel) — env was already updated in-memory via os.environ.
        pass


def _prefs_dir() -> str:
    """Return a writable directory for user preferences."""
    cache_dir = os.environ.get("TOKEN_CACHE_DIR", "")
    if cache_dir:
        return cache_dir
    return os.path.join(os.path.expanduser("~"), ".tagent")


def _prefs_path() -> str:
    return os.path.join(_prefs_dir(), "user_preferences.json")


def load_user_prefs() -> dict:
    try:
        with open(_prefs_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, Exception):
        return {}


def save_user_prefs(updates: dict) -> None:
    prefs = load_user_prefs()
    prefs.update(updates)
    try:
        os.makedirs(_prefs_dir(), exist_ok=True)
        with open(_prefs_path(), "w", encoding="utf-8") as f:
            json.dump(prefs, f, indent=2)
    except (OSError, PermissionError):
        pass
