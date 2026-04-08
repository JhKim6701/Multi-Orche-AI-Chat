from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Message, OrchestrationRun, RoleEnum
from app.orchestration.adapters import OrchestrationRuntime
from app.orchestration.graph import build_graph
from app.services.artifact_manager import create_ai_generated_artifact
from app.services.topic_segmentation import update_segment_summary


def publish_final_message_from_payload(
    db: Session,
    run: OrchestrationRun,
    payload: dict[str, Any],
) -> Message:
    chat_thread_id = int(payload["chat_thread_id"])
    max_seq = db.scalar(select(func.max(Message.sequence_no)).where(Message.chat_thread_id == chat_thread_id)) or 0
    final_text = str(payload["content_markdown"])
    final_message = Message(
        project_id=int(payload["project_id"]),
        chat_thread_id=chat_thread_id,
        segment_id=int(payload["segment_id"]),
        role=RoleEnum.assistant,
        content_markdown=final_text,
        plain_text_cache=final_text,
        sequence_no=max_seq + 1,
        model_name=payload.get("model_name"),
        model_role=payload.get("model_role"),
    )
    db.add(final_message)
    db.flush()

    generated_artifact = create_ai_generated_artifact(
        db,
        project_id=int(payload["project_id"]),
        chat_thread_id=chat_thread_id,
        message_id=final_message.id,
        content=final_text,
        model_name=payload.get("model_name"),
        model_role=payload.get("model_role"),
        orchestration_run_id=run.id,
    )
    final_message.content_markdown = (
        f"{final_message.content_markdown}\n"
        f"[Generated artifact] #{generated_artifact.id}:{generated_artifact.original_filename}"
    )
    final_message.plain_text_cache = final_message.content_markdown
    run.final_message_id = final_message.id
    run.status = "completed"
    run.ended_at = datetime.utcnow()
    update_segment_summary(db, int(payload["segment_id"]))
    return final_message


async def execute_orchestration(
    db: Session,
    project_id: int,
    chat_thread_id: int,
    content_markdown: str,
    selected_model_names: list[str],
    orchestrator_model_name: str | None,
    message_asset_ids: list[int],
    require_approval_before_publish: bool = False,
) -> OrchestrationRun:
    runtime = OrchestrationRuntime(
        db=db,
        project_id=project_id,
        chat_thread_id=chat_thread_id,
        content_markdown=content_markdown,
        selected_model_names=selected_model_names,
        orchestrator_model_name=orchestrator_model_name,
        message_asset_ids=message_asset_ids,
        require_approval_before_publish=require_approval_before_publish,
    )

    state = await runtime.bootstrap()
    graph = build_graph(runtime)

    try:
        await graph.ainvoke(state)
        if runtime.run.status == "running":
            runtime.run.status = "completed"
            runtime.run.ended_at = datetime.utcnow()
        db.commit()
        db.refresh(runtime.run)
        return runtime.run
    except Exception:
        if runtime.run:
            runtime.run.status = "failed"
            runtime.run.ended_at = datetime.utcnow()
            db.commit()
            db.refresh(runtime.run)
        raise
