from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ApprovalLevel(Enum):
    AUTO = "auto"
    CONFIRM = "confirm"
    EXPLICIT = "explicit"


class ApprovalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


@dataclass
class ApprovalRequest:
    action_description: str
    level: ApprovalLevel
    status: ApprovalStatus = ApprovalStatus.PENDING
    user_id: str | None = None
    checkpoint_id: str | None = None
