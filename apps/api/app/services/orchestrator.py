from __future__ import annotations

import json
import base64
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Asset, ConversationSegment, Message, ModelRegistry, OrchestrationRun, OrchestrationStep, RoleEnum
from app.services.artifact_manager import create_ai_generated_artifact
from app.services.asset_ingestion import retrieve_relevant_context
from app.services.ollama_client import OllamaClient
from app.services.runtime_state import get_gpu_enabled
from app.services.topic_segmentation import maybe_start_new_segment, update_segment_summary


@dataclass
class StepPlan:
    name: str
    role: str
    prompt: str


def _choose_model(
    db: Session,
    selected_model_names: list[str],
    orchestrator_model_name: str | None,
    requires_vision: bool,
    needs_reasoning: bool,
    gpu_enabled: bool,
) -> tuple[str, str]:
    q = select(ModelRegistry).where(ModelRegistry.enabled.is_(True), ModelRegistry.downloaded.is_(True))
    if selected_model_names:
        q = q.where(ModelRegistry.model_name.in_(selected_model_names))
    rows = db.scalars(q.order_by(ModelRegistry.sort_order.asc(), ModelRegistry.model_name.asc())).all()
    if not rows:
        raise ValueError("enabled/downloaded 모델이 없어 오케스트레이션을 실행할 수 없습니다.")

    if orchestrator_model_name:
        chosen = next((m for m in rows if m.model_name == orchestrator_model_name), None)
        if chosen:
            return chosen.model_name, "user_selected_orchestrator_model"

    if not gpu_enabled:
        cpu_safe = [m for m in rows if not m.supports_vision and not m.supports_reasoning]
        if cpu_safe:
            return cpu_safe[0].model_name, "gpu_disabled_cpu_fallback"

    if requires_vision:
        vision = next((m for m in rows if m.supports_vision), None)
        if vision:
            return vision.model_name, "vision_asset_detected"

    if needs_reasoning:
        reasoning = next((m for m in rows if m.supports_reasoning), None)
        if reasoning:
            return reasoning.model_name, "long_context_reasoning"

    return rows[0].model_name, "sort_order_fallback"


def _summarize(text: str, limit: int = 220) -> str:
    cleaned = " ".join(text.strip().split())
    return cleaned[:limit]


def _pack_summary(text: str, meta: dict, limit: int = 700) -> str:
    payload = f"[meta]{json.dumps(meta, ensure_ascii=False)}[/meta]\n{text}"
    return _summarize(payload, limit=limit)


def _review_decision(text: str) -> str:
    lowered = text.lower()
    if "append_missing_points" in lowered:
        return "append_missing_points"
    if "revise" in lowered:
        return "revise"
    return "approve"


def _encode_image_assets(assets: list[Asset]) -> tuple[list[str], list[int]]:
    images: list[str] = []
    image_ids: list[int] = []
    for asset in assets:
        if not asset.mime_type.startswith("image/"):
            continue
        raw = Path(asset.stored_path).read_bytes()
        images.append(base64.b64encode(raw).decode("utf-8"))
        image_ids.append(asset.id)
    return images, image_ids


async def execute_orchestration(
    db: Session,
    project_id: int,
    chat_thread_id: int,
    content_markdown: str,
    selected_model_names: list[str],
    orchestrator_model_name: str | None,
    message_asset_ids: list[int],
) -> OrchestrationRun:
    max_seq = db.scalar(select(func.max(Message.sequence_no)).where(Message.chat_thread_id == chat_thread_id)) or 0
    segment, divergence = maybe_start_new_segment(db, chat_thread_id, content_markdown)
    user_message = Message(
        project_id=project_id,
        chat_thread_id=chat_thread_id,
        segment_id=segment.id,
        role=RoleEnum.user,
        content_markdown=content_markdown,
        plain_text_cache=content_markdown,
        sequence_no=max_seq + 1,
        model_role=f"segment:{divergence.get('reason')}" if divergence.get('diverged') else None,
    )
    db.add(user_message)
    db.flush()

    assets = []
    if message_asset_ids:
        assets = db.scalars(select(Asset).where(Asset.id.in_(message_asset_ids), Asset.chat_thread_id == chat_thread_id)).all()
        for asset in assets:
            asset.message_id = user_message.id

    has_image = any(a.mime_type.startswith("image/") for a in assets)
    image_payloads, image_asset_ids = _encode_image_assets(assets)
    context_hits = retrieve_relevant_context(db=db, chat_thread_id=chat_thread_id, query=content_markdown, limit=8)
    context_block = "\n".join([f"asset#{h['asset_id']} {h['filename']}: {h['snippet']}" for h in context_hits])
    needs_reasoning = len(context_block) > 800

    run = OrchestrationRun(
        project_id=project_id,
        chat_thread_id=chat_thread_id,
        user_message_id=user_message.id,
        status="running",
        graph_name="rule_based_orchestrator_v1",
        started_at=datetime.utcnow(),
    )
    db.add(run)
    db.flush()

    model_name, routing_reason = _choose_model(
        db=db,
        selected_model_names=selected_model_names,
        orchestrator_model_name=orchestrator_model_name,
        requires_vision=has_image,
        needs_reasoning=needs_reasoning,
        gpu_enabled=get_gpu_enabled(),
    )
    gpu_enabled = get_gpu_enabled()
    if has_image and needs_reasoning:
        routing_reason = f"{routing_reason}+vision_and_reasoning"
    elif has_image:
        routing_reason = f"{routing_reason}+vision_priority"
    routing_reason = f"{routing_reason}+gpu_enabled={gpu_enabled}"

    parent_summary = ""
    if segment.parent_segment_id:
        parent = db.get(ConversationSegment, segment.parent_segment_id)
        if parent:
            parent_summary = parent.topic_summary[:200]
    planner_prompt = f"segment#{segment.id} topic={segment.topic_label} parent_summary={parent_summary} 사용자 요청 계획: {content_markdown}"
    context_prompt = f"자산 컨텍스트를 요약하라:\n{context_block or '자산 컨텍스트 없음'}"
    router_prompt = f"모델 라우팅 결정: chosen={model_name}, reason={routing_reason}, has_image={has_image}, context_len={len(context_block)}"

    step_plans = [
        StepPlan("planner", "planner", planner_prompt),
        StepPlan("context_resolver", "context_resolver", context_prompt),
        StepPlan("model_router", "model_router", router_prompt),
    ]

    client = OllamaClient()
    step_outputs: list[str] = []
    used_asset_ids = [hit["asset_id"] for hit in context_hits]
    parent_summary_used = bool(parent_summary)

    try:
        for index, plan in enumerate(step_plans):
            step = OrchestrationStep(
                orchestration_run_id=run.id,
                step_name=plan.name,
                assigned_role=plan.role,
                model_name=model_name,
                status="running",
                input_summary=_summarize(plan.prompt),
                started_at=datetime.utcnow(),
            )
            db.add(step)
            db.flush()

            resp = await client.chat(model_name=model_name, messages=[{"role": "user", "content": plan.prompt}])
            output = resp.get("message", {}).get("content") or "(empty)"
            step.status = "completed"
            step.output_summary = _pack_summary(
                output,
                {
                    "routing_reason": routing_reason,
                    "gpu_enabled": gpu_enabled,
                    "used_asset_ids": used_asset_ids,
                    "image_asset_ids": image_asset_ids,
                    "vision_used": has_image,
                    "used_segment_id": segment.id,
                    "parent_segment_summary_used": parent_summary_used,
                },
            )
            step.ended_at = datetime.utcnow()
            step.retry_count = 0
            step_outputs.append(f"[{index + 1}:{plan.role}] {output}")
            db.flush()

        final_prompt = (
            "다음 중간 결과와 자산 컨텍스트를 바탕으로 사용자에게 최종 응답을 작성하라.\n"
            f"user_request: {content_markdown}\n"
            f"context:\n{context_block or '없음'}\n"
            f"intermediate:\n" + "\n".join(step_outputs)
        )
        final_step = OrchestrationStep(
            orchestration_run_id=run.id,
            step_name="final_responder",
            assigned_role="final_responder",
            model_name=model_name,
            status="running",
            input_summary=_summarize(final_prompt),
            started_at=datetime.utcnow(),
        )
        db.add(final_step)
        db.flush()

        vision_model = db.scalar(select(ModelRegistry).where(ModelRegistry.model_name == model_name))
        can_use_vision = bool(vision_model and vision_model.supports_vision)
        final_resp = await client.chat(
            model_name=model_name,
            messages=[{"role": "user", "content": final_prompt}],
            images=image_payloads if image_payloads and can_use_vision else None,
        )
        final_text = final_resp.get("message", {}).get("content") or "(empty)"
        if context_hits:
            src = ", ".join(f"#{h['asset_id']}:{h['filename']}" for h in context_hits[:4])
            final_text = f"{final_text}\n\n[Used assets] {src}"

        final_step.status = "completed"
        final_step.output_summary = _pack_summary(
            final_text,
                {
                    "routing_reason": routing_reason,
                    "used_asset_ids": used_asset_ids,
                    "image_asset_ids": image_asset_ids,
                    "vision_used": bool(image_payloads and can_use_vision),
                    "used_segment_id": segment.id,
                    "parent_segment_summary_used": parent_summary_used,
                },
            )
        final_step.ended_at = datetime.utcnow()

        review_prompt = (
            "너는 reviewer/critic이다. 아래 응답 초안을 검토하고 정확성/누락/구조를 판단하라.\n"
            "출력 첫 줄은 반드시 decision: approve|revise|append_missing_points 형태로 시작하라.\n"
            f"user_request: {content_markdown}\n"
            f"draft_answer: {final_text}\n"
            f"context: {context_block or '없음'}"
        )
        reviewer_step = OrchestrationStep(
            orchestration_run_id=run.id,
            step_name="reviewer_critic",
            assigned_role="reviewer",
            model_name=model_name,
            status="running",
            input_summary=_summarize(review_prompt),
            started_at=datetime.utcnow(),
        )
        db.add(reviewer_step)
        db.flush()

        review_resp = await client.chat(model_name=model_name, messages=[{"role": "user", "content": review_prompt}])
        review_text = review_resp.get("message", {}).get("content") or "decision: approve"
        reviewer_decision = _review_decision(review_text)
        reviewer_step.status = "completed"
        reviewer_step.output_summary = _pack_summary(
            review_text,
                {
                "routing_reason": routing_reason,
                "gpu_enabled": gpu_enabled,
                "reviewer_decision": reviewer_decision,
                    "used_asset_ids": used_asset_ids,
                    "image_asset_ids": image_asset_ids,
                    "vision_used": bool(image_payloads and can_use_vision),
                    "used_segment_id": segment.id,
                    "parent_segment_summary_used": parent_summary_used,
                },
            )
        reviewer_step.ended_at = datetime.utcnow()

        revised = False
        critic_model = model_name
        critic_reason = "same_model_fallback"
        critic_candidate = db.scalar(
            select(ModelRegistry)
            .where(
                ModelRegistry.enabled.is_(True),
                ModelRegistry.downloaded.is_(True),
                ModelRegistry.model_name != model_name,
            )
            .order_by(ModelRegistry.supports_reasoning.desc(), ModelRegistry.sort_order.asc())
        )
        if critic_candidate:
            critic_model = critic_candidate.model_name
            critic_reason = "alternate_model_for_critic"

        critic_prompt = (
            "너는 critic/debate 역할이다. 아래 draft의 취약점/반론/누락점을 3개 이내로 제시하라.\n"
            f"user_request: {content_markdown}\n"
            f"draft_answer: {final_text}\n"
            f"context: {context_block or '없음'}"
        )
        critic_step = OrchestrationStep(
            orchestration_run_id=run.id,
            step_name="critic_debate",
            assigned_role="critic",
            model_name=critic_model,
            status="running",
            input_summary=_summarize(critic_prompt),
            started_at=datetime.utcnow(),
        )
        db.add(critic_step)
        db.flush()
        critic_resp = await client.chat(model_name=critic_model, messages=[{"role": "user", "content": critic_prompt}])
        critic_text = critic_resp.get("message", {}).get("content") or "(critic empty)"
        critic_step.status = "completed"
        critic_step.output_summary = _pack_summary(
            critic_text,
            {
                "routing_reason": f"{routing_reason}+critic_reason={critic_reason}",
                "gpu_enabled": gpu_enabled,
                "used_asset_ids": used_asset_ids,
                "image_asset_ids": image_asset_ids,
                "vision_used": bool(image_payloads and can_use_vision),
                "used_segment_id": segment.id,
                "parent_segment_summary_used": parent_summary_used,
            },
        )
        critic_step.ended_at = datetime.utcnow()

        if reviewer_decision in {"revise", "append_missing_points"}:
            revision_prompt = (
                "reviewer 피드백을 반영해 최종 답변을 개선하라. 길이는 간결하되 누락점 보강.\n"
                f"user_request: {content_markdown}\n"
                f"previous_draft: {final_text}\n"
                f"reviewer_feedback: {review_text}\n"
                f"critic_feedback: {critic_text}\n"
                f"context: {context_block or '없음'}"
            )
            revision_step = OrchestrationStep(
                orchestration_run_id=run.id,
                step_name="final_responder_revision",
                assigned_role="final_responder",
                model_name=model_name,
                status="running",
                input_summary=_summarize(revision_prompt),
                started_at=datetime.utcnow(),
            )
            db.add(revision_step)
            db.flush()

            revision_resp = await client.chat(model_name=model_name, messages=[{"role": "user", "content": revision_prompt}])
            revised_text = revision_resp.get("message", {}).get("content") or final_text
            if context_hits:
                src = ", ".join(f"#{h['asset_id']}:{h['filename']}" for h in context_hits[:4])
                revised_text = f"{revised_text}\n\n[Used assets] {src}"
            final_text = revised_text
            revised = True
            revision_step.status = "completed"
            revision_step.output_summary = _pack_summary(
                revised_text,
                {
                    "routing_reason": routing_reason,
                    "gpu_enabled": gpu_enabled,
                    "reviewer_decision": reviewer_decision,
                    "used_asset_ids": used_asset_ids,
                    "image_asset_ids": image_asset_ids,
                    "vision_used": bool(image_payloads and can_use_vision),
                    "used_segment_id": segment.id,
                    "parent_segment_summary_used": parent_summary_used,
                    "revision_applied": True,
                },
            )
            revision_step.ended_at = datetime.utcnow()

        provenance_line = (
            f"[Orchestration Provenance] segment={segment.id}, assets={used_asset_ids or []}, "
            f"images={image_asset_ids or []}, vision_used={bool(image_payloads and can_use_vision)}, routing_reason={routing_reason}, parent_summary_used={parent_summary_used}, "
            f"reviewer_decision={reviewer_decision}, critic_model={critic_model}, revised={revised}, gpu_enabled={gpu_enabled}"
        )
        final_text = f"{final_text}\n\n{provenance_line}"

        final_message = Message(
            project_id=project_id,
            chat_thread_id=chat_thread_id,
            segment_id=segment.id,
            role=RoleEnum.assistant,
            content_markdown=final_text,
            plain_text_cache=final_text,
            sequence_no=max_seq + 2,
            model_name=model_name,
            model_role="final_responder_revised" if revised else "final_responder",
        )
        db.add(final_message)
        db.flush()
        generated_artifact = create_ai_generated_artifact(
            db,
            project_id=project_id,
            chat_thread_id=chat_thread_id,
            message_id=final_message.id,
            content=final_text,
            model_name=model_name,
            model_role=final_message.model_role,
            orchestration_run_id=run.id,
        )
        final_message.content_markdown = (
            f"{final_message.content_markdown}\n"
            f"[Generated artifact] #{generated_artifact.id}:{generated_artifact.original_filename}"
        )
        final_message.plain_text_cache = final_message.content_markdown

        update_segment_summary(db, segment.id)
        run.final_message_id = final_message.id
        run.status = "completed"
        run.ended_at = datetime.utcnow()
        db.commit()
        db.refresh(run)
        return run

    except Exception:
        run.status = "failed"
        run.ended_at = datetime.utcnow()
        db.commit()
        db.refresh(run)
        raise
