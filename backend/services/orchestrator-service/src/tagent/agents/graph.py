"""Main LangGraph agent graph definition."""

from __future__ import annotations

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from tagent.agents.nodes.classifier import classify
from tagent.agents.nodes.executor import execute
from tagent.agents.nodes.human_gate import human_gate
from tagent.agents.nodes.planner import plan
from tagent.agents.nodes.reviewer import review
from tagent.agents.state import AgentState
from tagent.domain.value_objects.approval import ApprovalLevel


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
    graph.add_node("plan", plan)
    graph.add_node("execute", execute)
    graph.add_node("review", review)
    graph.add_node("human_gate", human_gate)

    # Define edges
    graph.set_entry_point("classify")
    graph.add_edge("classify", "plan")
    graph.add_edge("plan", "execute")
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
