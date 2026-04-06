import json
import re
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Asset, ConversationSegment, Message, OrchestrationRun, OrchestrationStep, RoleEnum
from app.schemas.orchestration import OrchestrationRunCreate, OrchestrationRunDetail, OrchestrationRunOut, OrchestrationStepOut
from app.services.approval_state import get_pending, mark_approved, mark_rejected
from app.services.ollama_client import OllamaUnavailableError
from app.services.orchestrator import execute_orchestration, publish_final_message_from_payload
from app.services.topic_segmentation import update_segment_summary

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


def _step_meta(step: OrchestrationStep) -> tuple[dict, str | None]:
    if step.step_metadata_json and isinstance(step.step_metadata_json, dict):
        return step.step_metadata_json, step.output_summary
    return _extract_meta(step.output_summary)


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
            require_approval_before_publish=payload.require_approval_before_publish,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OllamaUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=f"orchestration runtime failure: {exc}") from exc

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
    critic_step = next((step for step in steps if step.step_name == "critic_debate"), None)
    specialist_step = next((step for step in steps if step.step_name == "specialist_analyzer"), None)
    reviewer_meta, _ = _step_meta(reviewer_step) if reviewer_step else ({}, None)
    critic_meta, critic_summary = _step_meta(critic_step) if critic_step else ({}, None)
    specialist_meta, specialist_summary = _step_meta(specialist_step) if specialist_step else ({}, None)
    reviewer_decision = reviewer_meta.get("reviewer_decision")
    provenance = {
        "routing_reason": reviewer_meta.get("routing_reason"),
        "used_asset_ids": reviewer_meta.get("used_asset_ids", []),
        "used_chunk_ids": reviewer_meta.get("used_chunk_ids", []),
        "used_segment_id": reviewer_meta.get("used_segment_id") or (user_msg.segment_id if user_msg else None),
        "parent_segment_summary_used": reviewer_meta.get("parent_segment_summary_used", False),
        "reviewer_decision": reviewer_decision,
        "image_asset_ids": reviewer_meta.get("image_asset_ids", []),
        "vision_used": reviewer_meta.get("vision_used", False),
        "gpu_enabled": reviewer_meta.get("gpu_enabled"),
        "retrieval_mode": reviewer_meta.get("retrieval_mode"),
        "ocr_used": reviewer_meta.get("ocr_used"),
        "critic_model": critic_step.model_name if critic_step else None,
        "critic_summary": critic_summary,
        "specialist_model": specialist_step.model_name if specialist_step else None,
        "specialist_summary": specialist_summary,
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
        f"chunks={provenance['used_chunk_ids']}, retrieval_mode={provenance['retrieval_mode']}, ocr_used={provenance['ocr_used']}, "
        f"images={provenance['image_asset_ids']}, vision_used={provenance['vision_used']}, "
        f"segment={provenance['used_segment_id']}, reviewer={reviewer_decision}, critic_model={provenance['critic_model']}, gpu_enabled={provenance['gpu_enabled']}, generated_artifacts={[a['id'] for a in artifact_summary]}"
    )
    pending = get_pending(run_id)
    parallel_groups = {}
    for step in steps:
        meta, _ = _step_meta(step)
        grp = meta.get("step_group")
        if grp:
            parallel_groups.setdefault(grp, []).append(step.id)
    execution_graph_summary = {
        "parallel_groups": parallel_groups,
        "step_count": len(steps),
    }
    step_payloads = []
    for step in steps:
        step_meta, step_output = _step_meta(step)
        step_payloads.append(
            OrchestrationStepOut(
                id=step.id,
                step_name=step.step_name,
                assigned_role=step.assigned_role,
                model_name=step.model_name,
                status=step.status,
                input_summary=step.input_summary,
                output_summary=step_output,
                duration_ms=(
                    int((step.ended_at - step.started_at).total_seconds() * 1000)
                    if step.started_at and step.ended_at
                    else None
                ),
                routing_reason=step_meta.get("routing_reason"),
                reviewer_decision=step_meta.get("reviewer_decision"),
                used_asset_ids=step_meta.get("used_asset_ids", []),
                used_chunk_ids=step_meta.get("used_chunk_ids", []),
                image_asset_ids=step_meta.get("image_asset_ids", []),
                vision_used=step_meta.get("vision_used"),
                gpu_enabled=step_meta.get("gpu_enabled"),
                used_segment_id=step_meta.get("used_segment_id"),
                parent_segment_summary_used=step_meta.get("parent_segment_summary_used"),
                step_group=step_meta.get("step_group"),
                depends_on_step_ids=step_meta.get("depends_on_step_ids", []),
                execution_mode=step_meta.get("execution_mode"),
                fallback_model_name=step_meta.get("fallback_model_name"),
                fallback_reason=step_meta.get("fallback_reason"),
                retrieval_mode=step_meta.get("retrieval_mode"),
                ocr_used=step_meta.get("ocr_used"),
                retry_count=step_meta.get("retry_count", 0),
                approval_required=step_meta.get("approval_required"),
                approval_status=step_meta.get("approval_status"),
                step_metadata=step_meta,
            )
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
            "used_chunk_ids": provenance["used_chunk_ids"],
            "used_segment_id": provenance["used_segment_id"],
            "parent_segment_summary_used": provenance["parent_segment_summary_used"],
            "reviewer_decision": reviewer_decision,
            "generated_artifact_ids": [a["id"] for a in artifact_summary],
            "artifact_summary": artifact_summary,
            "vision_used": provenance["vision_used"],
            "image_asset_ids": provenance["image_asset_ids"],
            "gpu_enabled": provenance["gpu_enabled"],
            "retrieval_mode": provenance["retrieval_mode"],
            "ocr_used": provenance["ocr_used"],
            "critic_model": provenance["critic_model"],
            "critic_summary": provenance["critic_summary"],
            "specialist_model": provenance["specialist_model"],
            "specialist_summary": provenance["specialist_summary"],
            "approval_status": "pending" if run.status == "approval_pending" else ("rejected" if run.status == "rejected" else "approved"),
            "pending_final_draft": (pending or {}).get("content_markdown") if pending else None,
            "execution_graph_summary": execution_graph_summary,
            "final_publish_status": "published" if run.final_message_id else ("pending" if run.status == "approval_pending" else run.status),
        },
        steps=step_payloads,
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


@router.get("/runs/{run_id}/observability")
def run_observability(run_id: int, db: Session = Depends(get_db)):
    run = db.get(OrchestrationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    steps = db.scalars(select(OrchestrationStep).where(OrchestrationStep.orchestration_run_id == run_id).order_by(OrchestrationStep.id.asc())).all()
    summary = []
    for step in steps:
        meta, _ = _step_meta(step)
        summary.append(
            {
                "run_id": run_id,
                "step_id": step.id,
                "step_name": step.step_name,
                "assigned_role": step.assigned_role,
                "status": step.status,
                "model_name": step.model_name,
                "duration_ms": int((step.ended_at - step.started_at).total_seconds() * 1000) if step.started_at and step.ended_at else None,
                "retry_count": meta.get("retry_count", 0),
                "fallback_model_name": meta.get("fallback_model_name"),
                "approval_status": meta.get("approval_status"),
                "used_asset_ids": meta.get("used_asset_ids", []),
                "used_chunk_ids": meta.get("used_chunk_ids", []),
                "used_segment_id": meta.get("used_segment_id"),
            }
        )
    return {
        "run_id": run_id,
        "status": run.status,
        "step_count": len(summary),
        "steps": summary,
    }


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
            "assigned_role": None,
            "status": run.status,
            "model_name": None,
            "fallback_model_name": None,
            "fallback_reason": None,
            "retry_count": 0,
            "segment_id": segment_id,
            "approval_status": None,
            "timestamp": datetime.utcnow().isoformat(),
        }
        base.update(kwargs)
        return json.dumps(base, ensure_ascii=False)

    def gen():
        yield f"event: run_started\ndata: {payload('run_started', status=run.status)}\n\n"
        for step in steps:
            meta, _ = _step_meta(step)
            start_type = "step_started"
            done_type = "step_completed"
            if step.step_name == "reviewer_critic":
                start_type = "reviewer_started"
                done_type = "reviewer_completed"
            elif step.step_name == "critic_debate":
                start_type = "critic_started"
                done_type = "critic_completed"
            elif step.step_name == "specialist_analyzer":
                start_type = "specialist_started"
                done_type = "specialist_completed"
            elif step.step_name == "final_responder_revision":
                start_type = "revision_started"
                done_type = "revision_completed"
            if meta.get("retry_count", 0):
                yield f"event: retry_started\ndata: {payload('retry_started', step_id=step.id, step_name=step.step_name, status='retrying', model_name=step.model_name, retry_count=meta.get('retry_count'))}\n\n"
            if meta.get("fallback_model_name"):
                yield f"event: fallback_started\ndata: {payload('fallback_started', step_id=step.id, step_name=step.step_name, assigned_role=step.assigned_role, status='fallback', model_name=step.model_name, fallback_model_name=meta.get('fallback_model_name'), fallback_reason=meta.get('fallback_reason'))}\n\n"
            yield f"event: {start_type}\ndata: {payload(start_type, step_id=step.id, step_name=step.step_name, assigned_role=step.assigned_role, status='running', model_name=step.model_name, reviewer_decision=meta.get('reviewer_decision'))}\n\n"
            if step.status == "failed":
                yield f"event: step_failed\ndata: {payload('step_failed', step_id=step.id, step_name=step.step_name, assigned_role=step.assigned_role, status='failed', model_name=step.model_name, fallback_model_name=meta.get('fallback_model_name'), retry_count=meta.get('retry_count', 0), approval_status=meta.get('approval_status'))}\n\n"
            else:
                yield f"event: {done_type}\ndata: {payload(done_type, step_id=step.id, step_name=step.step_name, assigned_role=step.assigned_role, status=step.status, model_name=step.model_name, reviewer_decision=meta.get('reviewer_decision'), vision_used=meta.get('vision_used'), image_asset_ids=meta.get('image_asset_ids', []), gpu_enabled=meta.get('gpu_enabled'), fallback_model_name=meta.get('fallback_model_name'), fallback_reason=meta.get('fallback_reason'), retry_count=meta.get('retry_count', 0), approval_status=meta.get('approval_status'))}\n\n"
        if run.status == "approval_pending":
            yield f"event: approval_pending\ndata: {payload('approval_pending', run_id=run_id, approval_status='pending')}\n\n"
        end_event = "run_completed" if run.status == "completed" else "run_failed"
        if run.status == "rejected":
            end_event = "run_rejected"
        yield f"event: {end_event}\ndata: {payload(end_event, status=run.status, final_message_id=run.final_message_id)}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/runs/{run_id}/approve")
def approve_run(run_id: int, db: Session = Depends(get_db)):
    run = db.get(OrchestrationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    if run.status == "completed" and run.final_message_id:
        return {"ok": True, "run_id": run_id, "final_message_id": run.final_message_id, "idempotent": True}

    pending = get_pending(run_id)
    if not pending:
        raise HTTPException(status_code=409, detail="approval_state_inconsistent: no pending approval")

    final_message = publish_final_message_from_payload(db=db, run=run, payload=pending)
    transition = mark_approved(run_id, final_message.id)
    if transition.status not in {"approved"}:
        raise HTTPException(status_code=409, detail="approval_state_inconsistent: failed to mark approval")

    for step in db.scalars(select(OrchestrationStep).where(OrchestrationStep.orchestration_run_id == run_id)).all():
        if step.step_metadata_json and isinstance(step.step_metadata_json, dict):
            step.step_metadata_json["approval_status"] = "approved"
    update_segment_summary(db, int(pending["segment_id"]))
    db.commit()
    return {"ok": True, "run_id": run_id, "final_message_id": final_message.id, "idempotent": bool(transition.idempotent)}


@router.post("/runs/{run_id}/reject")
def reject_run(run_id: int, db: Session = Depends(get_db)):
    run = db.get(OrchestrationRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="run not found")
    if run.status == "rejected":
        return {"ok": True, "run_id": run_id, "status": "rejected", "idempotent": True}
    if run.status == "completed":
        raise HTTPException(status_code=400, detail="already published; cannot reject")

    transition = mark_rejected(run_id)
    if transition.status == "missing":
        raise HTTPException(status_code=409, detail="approval_state_inconsistent: no pending approval")
    if transition.status not in {"rejected"}:
        raise HTTPException(status_code=409, detail="approval_state_inconsistent: invalid approval state transition")

    run.status = "rejected"
    run.ended_at = datetime.utcnow()
    for step in db.scalars(select(OrchestrationStep).where(OrchestrationStep.orchestration_run_id == run_id)).all():
        if step.step_metadata_json and isinstance(step.step_metadata_json, dict):
            step.step_metadata_json["approval_status"] = "rejected"
    db.commit()
    return {"ok": True, "run_id": run_id, "status": "rejected", "idempotent": bool(transition.idempotent)}
