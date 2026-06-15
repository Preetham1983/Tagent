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
        "dacl_result": None,
        "approval": None,
        "user_id": req.user_id,
        "thread_id": req.thread_id,
        "user_role": req.user_role,
        "user_tier": req.user_tier,
        "memory": [],
    }
    try:
        result = await graph.ainvoke(
            state, config={"configurable": {"thread_id": req.thread_id}}
        )
    except Exception as exc:
        import traceback
        traceback.print_exc()
        cause = str(exc)
        raise HTTPException(status_code=500, detail=f"Orchestrator error: {cause[:400]}")

    tool_results = result.get("tool_results", [])
    dacl_result = result.get("dacl_result")
    
    # Check if BRN blocked the request
    if dacl_result and dacl_result.get("allowed") == "no":
        policy_name = dacl_result.get("policy_name", "Unknown Policy")
        fallback = dacl_result.get("fallback_action", "escalate_to_human")
        response_text = (
            f"🚫 **Action Blocked by BRN Policy**\n\n"
            f"Your request was blocked by the business rules network.\n\n"
            f"**Policy:** {policy_name}\n"
            f"**Action:** {fallback.replace('_', ' ').title()}\n\n"
            f"Please refine your request or contact an administrator for assistance."
        )
    else:
        response_text = (
            tool_results[-1]["output"] if tool_results else "I'm here to help — ask me anything."
        )

    approval = result.get("approval")
    step_dacl_results = result.get("step_dacl_results")
    
    # Extract BRN validation status
    brn_validation = {
        "enabled": bool(dacl_result and dacl_result.get("dacl_available")),
        "intent_check": {
            "passed": dacl_result.get("allowed") == "yes" if dacl_result else None,
            "policy_name": dacl_result.get("policy_name") if dacl_result else None,
            "allowed": dacl_result.get("allowed") if dacl_result else None,
            "auto_execute": dacl_result.get("auto_execute") if dacl_result else None,
        } if dacl_result else None,
        "step_checks": [
            {
                "step": sr.get("step"),
                "passed": sr.get("allowed") == "yes",
                "allowed": sr.get("allowed"),
            }
            for sr in (step_dacl_results or [])
        ] if step_dacl_results else [],
    }
    
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
        "brn_validation": brn_validation,
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
