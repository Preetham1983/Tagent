from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class User:
    id: str
    display_name: str
    email: str
    teams_id: str | None = None
    preferences: dict[str, str] = field(default_factory=dict)
