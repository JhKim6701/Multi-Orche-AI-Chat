from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Asset, Message, ModelRegistry, OrchestrationRun, OrchestrationStep, RoleEnum
from app.services.ollama_client import OllamaClient


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
) -> str:
    q = select(ModelRegistry).where(ModelRegistry.enabled.is_(True), ModelRegistry.downloaded.is_(True))
    if selected_model_names:
        q = q.where(ModelRegistry.model_name.in_(selected_model_names))
    rows = db.scalars(q.order_by(ModelRegistry.sort_order.asc(), ModelRegistry.model_name.asc())).all()
    if not rows:
        raise ValueError("enabled/downloaded 모델이 없어 오케스트레이션을 실행할 수 없습니다.")

    if orchestrator_model_name:
        chosen = next((m for m in rows if m.model_name == orchestrator_model_name), None)
        if chosen:
            return chosen.model_name

    if requires_vision:
        vision = next((m for m in rows if m.supports_vision), None)
        if vision:
            return vision.model_name

    return rows[0].model_name


def _summarize(text: str, limit: int = 220) -> str:
    cleaned = " ".join(text.strip().split())
    return cleaned[:limit]


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
    user_message = Message(
        project_id=project_id,
        chat_thread_id=chat_thread_id,
        role=RoleEnum.user,
        content_markdown=content_markdown,
        plain_text_cache=content_markdown,
        sequence_no=max_seq + 1,
    )
    db.add(user_message)
    db.flush()

    assets = []
    if message_asset_ids:
        assets = db.scalars(select(Asset).where(Asset.id.in_(message_asset_ids), Asset.chat_thread_id == chat_thread_id)).all()
        for asset in assets:
            asset.message_id = user_message.id

    has_image = any(a.mime_type.startswith("image/") for a in assets)
    has_file = any(not a.mime_type.startswith("image/") for a in assets)

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

    model_name = _choose_model(
        db=db,
        selected_model_names=selected_model_names,
        orchestrator_model_name=orchestrator_model_name,
        requires_vision=has_image,
    )
    planner_prompt = f"사용자 요청을 계획으로 요약하라: {content_markdown}"
    context_prompt = f"요청에 필요한 컨텍스트를 정리하라. file={has_file}, image={has_image}."
    router_prompt = f"모델 라우팅 결정을 설명하라. 선택 모델={selected_model_names}, chosen={model_name}"

    step_plans = [
        StepPlan("planner", "planner", planner_prompt),
        StepPlan("context_resolver", "context_resolver", context_prompt),
        StepPlan("model_router", "model_router", router_prompt),
    ]

    client = OllamaClient()
    step_outputs: list[str] = []

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
            step.output_summary = _summarize(output)
            step.ended_at = datetime.utcnow()
            step.retry_count = 0
            step_outputs.append(f"[{index + 1}:{plan.role}] {output}")
            db.flush()

        final_prompt = (
            "다음 중간 결과를 바탕으로 사용자에게 최종 응답을 작성하라.\n"
            f"user_request: {content_markdown}\n"
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

        final_resp = await client.chat(model_name=model_name, messages=[{"role": "user", "content": final_prompt}])
        final_text = final_resp.get("message", {}).get("content") or "(empty)"

        final_step.status = "completed"
        final_step.output_summary = _summarize(final_text)
        final_step.ended_at = datetime.utcnow()

        final_message = Message(
            project_id=project_id,
            chat_thread_id=chat_thread_id,
            role=RoleEnum.assistant,
            content_markdown=final_text,
            plain_text_cache=final_text,
            sequence_no=max_seq + 2,
            model_name=model_name,
            model_role="final_responder",
        )
        db.add(final_message)
        db.flush()

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
