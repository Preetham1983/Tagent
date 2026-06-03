"""Human gate node — pause execution for human-in-the-loop approval."""

from __future__ import annotations

from tagent.agents.state import AgentState
from tagent.domain.value_objects.approval import ApprovalStatus


async def human_gate(state: AgentState) -> dict:
    """This node is an interrupt point.

    LangGraph's `interrupt_before=["human_gate"]` pauses the graph here.
    The bot layer sends an Adaptive Card to the user.
    When the user responds, the graph is resumed with updated approval status.

    If we reach this node after resumption, approval has already been set
    by the external handler.
    """
    approval = state.get("approval")
    if approval is None:
        return {"approval": None}

    # If still pending, the graph should have been interrupted before reaching here.
    # This handles the resume case where approval was injected externally.
    if approval.status == ApprovalStatus.PENDING:
        # This state means we were resumed — check if it's been updated
        # The bot controller updates state before resuming
        pass

    return {"approval": approval}
