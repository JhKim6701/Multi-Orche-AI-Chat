from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ConversationSegment, Message, OrchestrationRun, OrchestrationStep
from app.schemas.orchestration import OrchestrationRunCreate, OrchestrationRunDetail, OrchestrationRunOut, OrchestrationStepOut
from app.services.ollama_client import OllamaUnavailableError
from app.services.orchestrator import execute_orchestration

router = APIRouter(prefix="/orchestration", tags=["orchestration"])


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
        },
        steps=[
            OrchestrationStepOut(
                id=step.id,
                step_name=step.step_name,
                assigned_role=step.assigned_role,
                model_name=step.model_name,
                status=step.status,
                input_summary=step.input_summary,
                output_summary=step.output_summary,
            )
            for step in steps
        ],
        final_message=(
            {
                "id": final_message.id,
                "content_markdown": final_message.content_markdown,
                "model_name": final_message.model_name,
                "model_role": final_message.model_role,
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

    def gen():
        yield f"event: run_started\ndata: {{\"run_id\": {run_id}, \"status\": \"{run.status}\"}}\n\n"
        for step in steps:
            yield f"event: step_started\ndata: {{\"step_id\": {step.id}, \"step_name\": \"{step.step_name}\"}}\n\n"
            yield (
                "event: step_completed\n"
                f"data: {{\"step_id\": {step.id}, \"status\": \"{step.status}\", \"role\": \"{step.assigned_role}\", \"model\": \"{step.model_name or ''}\"}}\n\n"
            )
        end_event = "run_completed" if run.status == "completed" else "run_failed"
        yield f"event: {end_event}\ndata: {{\"run_id\": {run_id}, \"status\": \"{run.status}\", \"final_message_id\": {run.final_message_id or 0}}}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
