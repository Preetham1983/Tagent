"""Main LangGraph agent graph definition."""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from tagent.agents.nodes.classifier import classify
from tagent.agents.nodes.dacl_guard import dacl_guard
from tagent.agents.nodes.executor import execute
from tagent.agents.nodes.human_gate import human_gate
from tagent.agents.nodes.planner import plan
from tagent.agents.nodes.reviewer import review
from tagent.agents.nodes.step_dacl_guard import step_dacl_guard
from tagent.agents.state import AgentState
from tagent.domain.value_objects.approval import ApprovalLevel


def _after_dacl_guard(state: AgentState) -> str:
    """Route after DACL gate: proceed to plan or block immediately."""
    dacl = state.get("dacl_result") or {}
    allowed = dacl.get("allowed", "yes")
    if allowed == "no":
        return "end"          # blocked — graph ends, UI gets blocked message
    # "yes" or "conditional" — proceed; reviewer handles approval level
    return "plan"


def _after_step_dacl_guard(state: AgentState) -> str:
    """Route after step-level DACL gate: proceed to execute or block."""
    step_results = state.get("step_dacl_results") or []
    for r in step_results:
        if r.get("allowed") == "no":
            return "end"      # at least one planned step was rejected by policy
    return "execute"


def _should_request_approval(state: AgentState) -> str:
    """Route after reviewer: auto-approve or go to human gate."""
    approval = state.get("approval")
    if approval and approval.level != ApprovalLevel.AUTO:
        return "human_gate"
    return "end"


def _after_human_gate(state: AgentState) -> str:
    """Route after human approval: resume execution or end."""
    from tagent.domain.value_objects.approval import ApprovalStatus

    approval = state.get("approval")
    if approval and approval.status == ApprovalStatus.APPROVED:
        return "execute"
    return "end"


def build_agent_graph() -> StateGraph:
    """Construct and compile the Tagent orchestration graph."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("classify", classify)
    graph.add_node("dacl_guard", dacl_guard)
    graph.add_node("plan", plan)
    graph.add_node("step_dacl_guard", step_dacl_guard)
    graph.add_node("execute", execute)
    graph.add_node("review", review)
    graph.add_node("human_gate", human_gate)

    # Define edges
    graph.set_entry_point("classify")
    graph.add_edge("classify", "dacl_guard")

    # Conditional: intent-level DACL gate — allowed → plan, blocked → END
    graph.add_conditional_edges(
        "dacl_guard",
        _after_dacl_guard,
        {"plan": "plan", "end": END},
    )

    # Step-level DACL gate: validate every planned step before any action is taken
    graph.add_edge("plan", "step_dacl_guard")
    graph.add_conditional_edges(
        "step_dacl_guard",
        _after_step_dacl_guard,
        {"execute": "execute", "end": END},
    )

    graph.add_edge("execute", "review")

    # Conditional: reviewer decides approval route
    graph.add_conditional_edges(
        "review",
        _should_request_approval,
        {"human_gate": "human_gate", "end": END},
    )

    # Conditional: after human gate
    graph.add_conditional_edges(
        "human_gate",
        _after_human_gate,
        {"execute": "execute", "end": END},
    )

    # Compile with checkpointer for human-in-the-loop persistence
    checkpointer = MemorySaver()
    return graph.compile(checkpointer=checkpointer, interrupt_before=["human_gate"])
