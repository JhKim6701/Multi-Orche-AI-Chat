from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from app.orchestration.adapters import OrchestrationRuntime
from app.orchestration.nodes import (
    approval_pending_node,
    context_resolver_node,
    critic_node,
    final_responder_node,
    model_router_node,
    planner_node,
    publish_node,
    reviewer_node,
    revision_node,
    specialist_node,
)
from app.orchestration.state import OrchestrationState


def _specialist_branch(state: OrchestrationState) -> str:
    return "specialist_analyzer" if state.get("should_run_specialist") else "model_router"


def _revision_branch(state: OrchestrationState) -> str:
    return "final_responder_revision" if state.get("should_revise") else "publish_or_pending"


def _approval_branch(state: OrchestrationState) -> str:
    return "approval_pending" if state.get("require_approval_before_publish") else "publish"


def build_graph(runtime: OrchestrationRuntime):
    graph = StateGraph(OrchestrationState)

    async def _planner(state: OrchestrationState):
        return await planner_node(state, runtime)

    async def _context(state: OrchestrationState):
        return await context_resolver_node(state, runtime)

    async def _specialist(state: OrchestrationState):
        return await specialist_node(state, runtime)

    async def _router(state: OrchestrationState):
        return await model_router_node(state, runtime)

    async def _final(state: OrchestrationState):
        return await final_responder_node(state, runtime)

    async def _reviewer(state: OrchestrationState):
        return await reviewer_node(state, runtime)

    async def _critic(state: OrchestrationState):
        return await critic_node(state, runtime)

    async def _revision(state: OrchestrationState):
        return await revision_node(state, runtime)

    async def _approval_pending(state: OrchestrationState):
        return await approval_pending_node(state, runtime)

    async def _publish(state: OrchestrationState):
        return await publish_node(state, runtime)

    graph.add_node("planner", _planner)
    graph.add_node("context_resolver", _context)
    graph.add_node("specialist_analyzer", _specialist)
    graph.add_node("model_router", _router)
    graph.add_node("final_responder", _final)
    graph.add_node("reviewer_critic", _reviewer)
    graph.add_node("critic_debate", _critic)
    graph.add_node("final_responder_revision", _revision)
    graph.add_node("publish_or_pending", lambda state: state)
    graph.add_node("approval_pending", _approval_pending)
    graph.add_node("publish", _publish)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "context_resolver")
    graph.add_conditional_edges("context_resolver", _specialist_branch, {"specialist_analyzer": "specialist_analyzer", "model_router": "model_router"})
    graph.add_edge("specialist_analyzer", "model_router")
    graph.add_edge("model_router", "final_responder")
    graph.add_edge("final_responder", "reviewer_critic")
    graph.add_edge("reviewer_critic", "critic_debate")
    graph.add_conditional_edges(
        "critic_debate",
        _revision_branch,
        {"final_responder_revision": "final_responder_revision", "publish_or_pending": "publish_or_pending"},
    )
    graph.add_conditional_edges(
        "publish_or_pending",
        _approval_branch,
        {"approval_pending": "approval_pending", "publish": "publish"},
    )
    graph.add_conditional_edges(
        "final_responder_revision",
        _approval_branch,
        {"approval_pending": "approval_pending", "publish": "publish"},
    )
    graph.add_edge("approval_pending", END)
    graph.add_edge("publish", END)

    return graph.compile()
