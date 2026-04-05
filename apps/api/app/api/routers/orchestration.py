import json
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Asset, ConversationSegment, Message, OrchestrationRun, OrchestrationStep
from app.schemas.orchestration import OrchestrationRunCreate, OrchestrationRunDetail, OrchestrationRunOut, OrchestrationStepOut
from app.services.ollama_client import OllamaUnavailableError
from app.services.orchestrator import execute_orchestration

router = APIRouter(prefix="/orchestration", tags=["orchestration"])


META_PATTERN = re.compile(r"\[meta\](.*?)\[/meta\]")


def _extract_meta(summary: str | None) -> tuple[dict, str | None]:
    if not summary:
        return {}, summary
    match = META_PATTERN.search(summary)
    if not match:
        return {}, summary
    raw = match.group(1)
    cleaned = summary.replace(match.group(0), "").strip()
    try:
        return json.loads(raw), cleaned
    except json.JSONDecodeError:
        return {}, cleaned


@router.post("/run", response_model=OrchestrationRunOut)
async def run_orchestration(payload: OrchestrationRunCreate, db: Session = Depends(get_db)):
    content = payload.content_markdown
    if not content and payload.user_message_id:
        message = db.get(Message, payload.user_message_id)
        content = message.content_markdown if message else None
    if not content:
        raise HTTPException(status_code=400, detail="content_markdown 또는 user_message_id가 필요합니다.")

    try:
        run = await execute_orchestration(
            db=db,
            project_id=payload.project_id,
            chat_thread_id=payload.chat_thread_id,
            content_markdown=content,
            selected_model_names=payload.selected_model_names,
            orchestrator_model_name=payload.orchestrator_model_name,
            message_asset_ids=payload.message_asset_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OllamaUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return run


@router.get("/runs", response_model=list[OrchestrationRunOut])
def run_history(chat_thread_id: int, db: Session = Depends(get_db)):
    return db.scalars(select(OrchestrationRun).where(OrchestrationRun.chat_thread_id == chat_thread_id).order_by(OrchestrationRun.started_at.desc())).all()


@router.get("/runs/{run_id}", response_model=OrchestrationRunDetail)
def run_detail(run_id: int, db: Session = Depends(get_db)):
    run = db.get(OrchestrationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")

    steps = db.scalars(select(OrchestrationStep).where(OrchestrationStep.orchestration_run_id == run_id).order_by(OrchestrationStep.id.asc())).all()
    final_message = db.get(Message, run.final_message_id) if run.final_message_id else None

    user_msg = db.get(Message, run.user_message_id)
    seg = db.get(ConversationSegment, user_msg.segment_id) if user_msg and user_msg.segment_id else None
    active_step = next((step for step in steps if step.status == "running"), None)
    reviewer_step = next((step for step in steps if step.step_name == "reviewer_critic"), None)
    reviewer_meta, _ = _extract_meta(reviewer_step.output_summary if reviewer_step else None)
    reviewer_decision = reviewer_meta.get("reviewer_decision")
    provenance = {
        "routing_reason": reviewer_meta.get("routing_reason"),
        "used_asset_ids": reviewer_meta.get("used_asset_ids", []),
        "used_segment_id": reviewer_meta.get("used_segment_id") or (user_msg.segment_id if user_msg else None),
        "parent_segment_summary_used": reviewer_meta.get("parent_segment_summary_used", False),
        "reviewer_decision": reviewer_decision,
        "image_asset_ids": reviewer_meta.get("image_asset_ids", []),
        "vision_used": reviewer_meta.get("vision_used", False),
    }
    generated_artifacts = []
    if final_message:
        generated_artifacts = db.scalars(
            select(Asset).where(Asset.message_id == final_message.id, Asset.source_type == "ai_generated").order_by(Asset.created_at.asc())
        ).all()
    artifact_summary = [
        {
            "id": a.id,
            "filename": a.original_filename,
            "mime_type": a.mime_type,
            "producing_model": a.producing_model,
            "producing_role": a.producing_role,
        }
        for a in generated_artifacts
    ]
    final_provenance_summary = (
        f"routing={provenance['routing_reason']}, assets={provenance['used_asset_ids']}, "
        f"images={provenance['image_asset_ids']}, vision_used={provenance['vision_used']}, "
        f"segment={provenance['used_segment_id']}, reviewer={reviewer_decision}, generated_artifacts={[a['id'] for a in artifact_summary]}"
    )
    return OrchestrationRunDetail(
        run={
            "id": run.id,
            "status": run.status,
            "graph_name": run.graph_name,
            "started_at": run.started_at,
            "ended_at": run.ended_at,
            "final_message_id": run.final_message_id,
            "segment_id": user_msg.segment_id if user_msg else None,
            "topic_label": seg.topic_label if seg else None,
            "parent_segment_id": seg.parent_segment_id if seg else None,
            "divergence_reason": (user_msg.model_role or '').replace('segment:', '') if user_msg and user_msg.model_role and user_msg.model_role.startswith('segment:') else None,
            "current_active_step": active_step.step_name if active_step else None,
            "routing_reason": provenance["routing_reason"],
            "used_asset_ids": provenance["used_asset_ids"],
            "used_segment_id": provenance["used_segment_id"],
            "parent_segment_summary_used": provenance["parent_segment_summary_used"],
            "reviewer_decision": reviewer_decision,
            "generated_artifact_ids": [a["id"] for a in artifact_summary],
            "artifact_summary": artifact_summary,
            "vision_used": provenance["vision_used"],
            "image_asset_ids": provenance["image_asset_ids"],
        },
        steps=[
            OrchestrationStepOut(
                id=step.id,
                step_name=step.step_name,
                assigned_role=step.assigned_role,
                model_name=step.model_name,
                status=step.status,
                input_summary=step.input_summary,
                output_summary=_extract_meta(step.output_summary)[1],
                routing_reason=_extract_meta(step.output_summary)[0].get("routing_reason"),
                reviewer_decision=_extract_meta(step.output_summary)[0].get("reviewer_decision"),
                used_asset_ids=_extract_meta(step.output_summary)[0].get("used_asset_ids", []),
                image_asset_ids=_extract_meta(step.output_summary)[0].get("image_asset_ids", []),
                vision_used=_extract_meta(step.output_summary)[0].get("vision_used"),
                used_segment_id=_extract_meta(step.output_summary)[0].get("used_segment_id"),
                parent_segment_summary_used=_extract_meta(step.output_summary)[0].get("parent_segment_summary_used"),
            )
            for step in steps
        ],
        final_message=(
            {
                "id": final_message.id,
                "content_markdown": final_message.content_markdown,
                "model_name": final_message.model_name,
                "model_role": final_message.model_role,
                "final_provenance_summary": final_provenance_summary,
                "generated_artifact_ids": [a["id"] for a in artifact_summary],
            }
            if final_message
            else None
        ),
    )


@router.get("/runs/{run_id}/stream")
def stream_run_events(run_id: int, db: Session = Depends(get_db)):
    run = db.get(OrchestrationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    steps = db.scalars(select(OrchestrationStep).where(OrchestrationStep.orchestration_run_id == run_id).order_by(OrchestrationStep.id.asc())).all()
    user_msg = db.get(Message, run.user_message_id)
    segment_id = user_msg.segment_id if user_msg else None

    def payload(event_type: str, **kwargs):
        base = {
            "event_type": event_type,
            "run_id": run_id,
            "step_id": None,
            "step_name": None,
            "status": run.status,
            "model_name": None,
            "segment_id": segment_id,
            "timestamp": datetime.utcnow().isoformat(),
        }
        base.update(kwargs)
        return json.dumps(base, ensure_ascii=False)

    def gen():
        yield f"event: run_started\ndata: {payload('run_started', status=run.status)}\n\n"
        for step in steps:
            meta, _ = _extract_meta(step.output_summary)
            start_type = "step_started"
            done_type = "step_completed"
            if step.step_name == "reviewer_critic":
                start_type = "reviewer_started"
                done_type = "reviewer_completed"
            elif step.step_name == "final_responder_revision":
                start_type = "revision_started"
                done_type = "revision_completed"
            yield f"event: {start_type}\ndata: {payload(start_type, step_id=step.id, step_name=step.step_name, status='running', model_name=step.model_name, reviewer_decision=meta.get('reviewer_decision'))}\n\n"
            yield f"event: {done_type}\ndata: {payload(done_type, step_id=step.id, step_name=step.step_name, status=step.status, model_name=step.model_name, reviewer_decision=meta.get('reviewer_decision'), vision_used=meta.get('vision_used'), image_asset_ids=meta.get('image_asset_ids', []))}\n\n"
        end_event = "run_completed" if run.status == "completed" else "run_failed"
        yield f"event: {end_event}\ndata: {payload(end_event, status=run.status, final_message_id=run.final_message_id)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
