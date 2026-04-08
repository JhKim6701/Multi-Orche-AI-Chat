from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.models import ModelRegistry
from app.orchestration.adapters import OrchestrationRuntime
from app.orchestration.state import OrchestrationState


def _base_meta(state: OrchestrationState, step_group: str, execution_mode: str = "sequential") -> dict[str, Any]:
    return {
        "routing_reason": state["routing_reason"],
        "gpu_enabled": state["gpu_enabled"],
        "used_asset_ids": state["used_asset_ids"],
        "image_asset_ids": state["image_asset_ids"],
        "used_chunk_ids": state["used_chunk_ids"],
        "retrieval_mode": state["retrieval_meta"].get("retrieval_mode"),
        "ocr_used": state["retrieval_meta"].get("ocr_used"),
        "vision_used": state["has_image"],
        "used_segment_id": state["segment_id"],
        "parent_segment_summary_used": state["parent_summary_used"],
        "step_group": step_group,
        "execution_mode": execution_mode,
    }


async def planner_node(state: OrchestrationState, runtime: OrchestrationRuntime) -> OrchestrationState:
    prompt = f"segment#{state['segment_id']} 사용자 요청 계획: {state['content_markdown']}"
    ctx = runtime.open_step("planner", "planner", state["model_name"], prompt)
    output, retry_count, fallback_model_name, fallback_reason, _ = await runtime.chat_with_retry(state["model_name"], prompt)
    step_id = runtime.close_step(
        ctx,
        output,
        {**_base_meta(state, "planning"), "fallback_model_name": fallback_model_name, "fallback_reason": fallback_reason},
        retry_count=retry_count,
    )
    return {**state, "step_outputs": state["step_outputs"] + [f"[planner] {output}"], "planner_step_id": step_id}


async def context_resolver_node(state: OrchestrationState, runtime: OrchestrationRuntime) -> OrchestrationState:
    prompt = f"자산 컨텍스트를 요약하라:\n{state['packed_context'] or state['context_block'] or '자산 컨텍스트 없음'}"
    ctx = runtime.open_step("context_resolver", "context_resolver", state["model_name"], prompt, depends_on=[state.get("planner_step_id", 0)])
    output, retry_count, fallback_model_name, fallback_reason, _ = await runtime.chat_with_retry(state["model_name"], prompt)
    step_id = runtime.close_step(
        ctx,
        output,
        {**_base_meta(state, "analysis_parallel", execution_mode="parallel_candidate"), "fallback_model_name": fallback_model_name, "fallback_reason": fallback_reason},
        retry_count=retry_count,
    )
    return {**state, "step_outputs": state["step_outputs"] + [f"[context_resolver] {output}"], "context_step_id": step_id}


async def specialist_node(state: OrchestrationState, runtime: OrchestrationRuntime) -> OrchestrationState:
    role = "vision specialist" if state["has_image"] else "specialist"
    prompt = f"{role} 관점으로 요청 분석: {state['content_markdown']}"
    ctx = runtime.open_step("specialist_analyzer", "specialist_analyzer", state["model_name"], prompt, depends_on=[state.get("planner_step_id", 0)])
    output, retry_count, fallback_model_name, fallback_reason, _ = await runtime.chat_with_retry(state["model_name"], prompt)
    step_id = runtime.close_step(
        ctx,
        output,
        {**_base_meta(state, "analysis_parallel", execution_mode="parallel_candidate"), "fallback_model_name": fallback_model_name, "fallback_reason": fallback_reason},
        retry_count=retry_count,
    )
    return {**state, "step_outputs": state["step_outputs"] + [f"[specialist] {output}"], "specialist_step_id": step_id}


async def model_router_node(state: OrchestrationState, runtime: OrchestrationRuntime) -> OrchestrationState:
    prompt = f"모델 라우팅 결정: chosen={state['model_name']}, reason={state['routing_reason']}, has_image={state['has_image']}"
    depends = [sid for sid in [state.get("context_step_id"), state.get("specialist_step_id")] if sid]
    ctx = runtime.open_step("model_router", "model_router", state["model_name"], prompt, depends_on=depends)
    output, retry_count, fallback_model_name, fallback_reason, _ = await runtime.chat_with_retry(state["model_name"], prompt)
    step_id = runtime.close_step(
        ctx,
        output,
        {**_base_meta(state, "routing"), "fallback_model_name": fallback_model_name, "fallback_reason": fallback_reason},
        retry_count=retry_count,
    )
    return {**state, "step_outputs": state["step_outputs"] + [f"[router] {output}"], "router_step_id": step_id}


async def final_responder_node(state: OrchestrationState, runtime: OrchestrationRuntime) -> OrchestrationState:
    prompt = (
        "다음 중간 결과와 자산 컨텍스트를 바탕으로 사용자에게 최종 응답을 작성하라.\n"
        f"user_request: {state['content_markdown']}\n"
        f"context:\n{state['context_block'] or '없음'}\n"
        f"intermediate:\n" + "\n".join(state["step_outputs"])
    )
    ctx = runtime.open_step("final_responder", "final_responder", state["model_name"], prompt, depends_on=[state.get("router_step_id", 0)])

    vision_model = runtime.db.scalar(select(ModelRegistry).where(ModelRegistry.model_name == state["model_name"]))
    can_use_vision = bool(vision_model and vision_model.supports_vision)
    resp = await runtime.client.chat(
        model_name=state["model_name"],
        messages=[{"role": "user", "content": prompt}],
        images=state["image_payloads"] if state["image_payloads"] and can_use_vision else None,
    )
    final_text = resp.get("message", {}).get("content") or "(empty)"
    if state["context_hits"]:
        src = ", ".join(f"#{h['asset_id']}:{h['filename']}" for h in state["context_hits"][:4])
        final_text = f"{final_text}\n\n[Used assets] {src}"
    step_id = runtime.close_step(ctx, final_text, _base_meta(state, "response"), retry_count=0)
    return {**state, "final_text": final_text, "model_role": "final_responder", "final_step_id": step_id}


async def reviewer_node(state: OrchestrationState, runtime: OrchestrationRuntime) -> OrchestrationState:
    prompt = (
        "너는 reviewer/critic이다. decision: approve|revise|append_missing_points 로 시작하라.\n"
        f"user_request: {state['content_markdown']}\n"
        f"draft_answer: {state['final_text']}\n"
        f"context: {state['context_block'] or '없음'}"
    )
    ctx = runtime.open_step("reviewer_critic", "reviewer", state["model_name"], prompt, depends_on=[state.get("final_step_id", 0)])
    output, retry_count, fallback_model_name, fallback_reason, _ = await runtime.chat_with_retry(state["model_name"], prompt)
    decision = runtime.review_decision(output)
    step_id = runtime.close_step(
        ctx,
        output,
        {**_base_meta(state, "quality_gate"), "reviewer_decision": decision, "fallback_model_name": fallback_model_name, "fallback_reason": fallback_reason},
        retry_count=retry_count,
    )
    return {**state, "reviewer_decision": decision, "should_revise": decision in {"revise", "append_missing_points"}, "reviewer_step_id": step_id}


async def critic_node(state: OrchestrationState, runtime: OrchestrationRuntime) -> OrchestrationState:
    critic_model = state["model_name"]
    candidate = runtime.db.scalar(
        select(ModelRegistry)
        .where(ModelRegistry.enabled.is_(True), ModelRegistry.downloaded.is_(True), ModelRegistry.model_name != state["model_name"])
        .order_by(ModelRegistry.supports_reasoning.desc(), ModelRegistry.sort_order.asc())
    )
    if candidate:
        critic_model = candidate.model_name
    prompt = (
        "너는 critic/debate 역할이다. 취약점/반론/누락점을 3개 이내 제시하라.\n"
        f"user_request: {state['content_markdown']}\n"
        f"draft_answer: {state['final_text']}"
    )
    ctx = runtime.open_step("critic_debate", "critic", critic_model, prompt, depends_on=[state.get("final_step_id", 0)])
    output, retry_count, fallback_model_name, fallback_reason, _ = await runtime.chat_with_retry(critic_model, prompt)
    step_id = runtime.close_step(
        ctx,
        output,
        {**_base_meta(state, "quality_gate"), "fallback_model_name": fallback_model_name, "fallback_reason": fallback_reason},
        retry_count=retry_count,
    )
    return {**state, "critic_model": critic_model, "critic_text": output, "critic_step_id": step_id}


async def revision_node(state: OrchestrationState, runtime: OrchestrationRuntime) -> OrchestrationState:
    prompt = (
        "reviewer 피드백을 반영해 최종 답변을 개선하라.\n"
        f"user_request: {state['content_markdown']}\n"
        f"previous_draft: {state['final_text']}\n"
        f"reviewer_feedback: {state.get('reviewer_decision')}\n"
        f"critic_feedback: {state.get('critic_text', '')}"
    )
    ctx = runtime.open_step("final_responder_revision", "final_responder", state["model_name"], prompt, depends_on=[state.get("reviewer_step_id", 0), state.get("critic_step_id", 0)])
    output, retry_count, fallback_model_name, fallback_reason, _ = await runtime.chat_with_retry(state["model_name"], prompt)
    if state["context_hits"]:
        src = ", ".join(f"#{h['asset_id']}:{h['filename']}" for h in state["context_hits"][:4])
        output = f"{output}\n\n[Used assets] {src}"
    runtime.close_step(
        ctx,
        output,
        {**_base_meta(state, "quality_gate"), "reviewer_decision": state["reviewer_decision"], "revision_applied": True, "fallback_model_name": fallback_model_name, "fallback_reason": fallback_reason},
        retry_count=retry_count,
    )
    return {**state, "final_text": output, "model_role": "final_responder_revised", "revised": True}


async def approval_pending_node(state: OrchestrationState, runtime: OrchestrationRuntime) -> OrchestrationState:
    with_prov = runtime.append_provenance(state)
    updated = {**state, "final_text": with_prov}
    runtime.mark_approval_pending(updated)
    return updated


async def publish_node(state: OrchestrationState, runtime: OrchestrationRuntime) -> OrchestrationState:
    with_prov = runtime.append_provenance(state)
    updated = {**state, "final_text": with_prov}
    runtime.publish_now(updated)
    return updated
