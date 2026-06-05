"""Orchestration endpoints — run and resume LangGraph workflows."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from tagent.api.dependencies import get_graph
from tagent.api.schemas import ApproveRequest, OrchestrateRequest

router = APIRouter()


@router.post("/orchestrate")
async def orchestrate(req: OrchestrateRequest) -> dict:
    graph = get_graph()
    state = {
        "messages": [{"role": "user", "content": req.message}],
        "intent": None,
        "plan": [],
        "current_step": 0,
        "tool_results": [],
        "approval": None,
        "user_id": req.user_id,
        "thread_id": req.thread_id,
        "memory": [],
    }
    result = await graph.ainvoke(
        state, config={"configurable": {"thread_id": req.thread_id}}
    )

    tool_results = result.get("tool_results", [])
    response_text = (
        tool_results[-1]["output"] if tool_results else "I'm here to help — ask me anything."
    )

    approval = result.get("approval")
    return {
        "response": response_text,
        "thread_id": req.thread_id,
        "intent": result.get("intent", {}).value if result.get("intent") else None,
        "tool_results": tool_results,
        "approval": {
            "required": bool(approval),
            "description": approval.action_description if approval else None,
            "level": approval.level.value if approval else None,
            "status": approval.status.value if approval else None,
        },
    }


@router.post("/approve")
async def approve(req: ApproveRequest) -> dict:
    """Resume a paused LangGraph workflow after human approval/rejection."""
    from tagent.domain.value_objects.approval import ApprovalStatus

    graph = get_graph()
    try:
        config = {"configurable": {"thread_id": req.thread_id}}
        current_state = await graph.aget_state(config)

        if not current_state or not current_state.values:
            raise HTTPException(status_code=404, detail="No paused workflow found for this thread.")

        approval = current_state.values.get("approval")
        if not approval:
            raise HTTPException(status_code=400, detail="No pending approval in this workflow.")

        approval.status = ApprovalStatus.APPROVED if req.approved else ApprovalStatus.REJECTED
        await graph.aupdate_state(config, {"approval": approval})
        result = await graph.ainvoke(None, config=config)

        tool_results = result.get("tool_results", [])
        response_text = tool_results[-1]["output"] if tool_results else "Action completed."

        return {
            "response": response_text,
            "thread_id": req.thread_id,
            "status": "approved" if req.approved else "rejected",
            "tool_results": tool_results,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500, detail=f"Failed to resume workflow: {str(exc)[:200]}"
        )
