"""Approval service — manages human-in-the-loop approval workflows."""

from __future__ import annotations

from tagent.domain.interfaces.state_store_port import StateStorePort
from tagent.domain.value_objects.approval import ApprovalRequest, ApprovalStatus


class ApprovalService:
    """Handles creating, storing, and resolving approval requests."""

    def __init__(self, state_store: StateStorePort) -> None:
        self._store = state_store

    async def request_approval(self, approval: ApprovalRequest, thread_id: str) -> str:
        """Store an approval request and return a checkpoint ID."""
        data = {
            "action_description": approval.action_description,
            "level": approval.level.value,
            "status": approval.status.value,
            "user_id": approval.user_id,
        }
        return await self._store.save_checkpoint(thread_id, data)

    async def resolve_approval(
        self, checkpoint_id: str, approved: bool
    ) -> ApprovalRequest | None:
        """Resolve a pending approval (approve or reject)."""
        data = await self._store.load_checkpoint(checkpoint_id)
        if data is None:
            return None

        from tagent.domain.value_objects.approval import ApprovalLevel

        status = ApprovalStatus.APPROVED if approved else ApprovalStatus.REJECTED
        return ApprovalRequest(
            action_description=data["action_description"],
            level=ApprovalLevel(data["level"]),
            status=status,
            user_id=data.get("user_id"),
            checkpoint_id=checkpoint_id,
        )
