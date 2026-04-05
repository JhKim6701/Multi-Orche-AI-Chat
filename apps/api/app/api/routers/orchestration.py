from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import OrchestrationRun, OrchestrationStep
from app.schemas.orchestration import OrchestrationRunCreate, OrchestrationRunOut
from app.services.orchestrator import create_minimal_run

router = APIRouter(prefix="/orchestration", tags=["orchestration"])


@router.post("/run", response_model=OrchestrationRunOut)
def run_orchestration(payload: OrchestrationRunCreate, db: Session = Depends(get_db)):
    return create_minimal_run(db, payload.project_id, payload.chat_thread_id, payload.user_message_id)


@router.get("/runs", response_model=list[OrchestrationRunOut])
def run_history(chat_thread_id: int, db: Session = Depends(get_db)):
    return db.scalars(select(OrchestrationRun).where(OrchestrationRun.chat_thread_id == chat_thread_id)).all()


@router.get("/runs/{run_id}")
def run_detail(run_id: int, db: Session = Depends(get_db)):
    run = db.get(OrchestrationRun, run_id)
    steps = db.scalars(select(OrchestrationStep).where(OrchestrationStep.orchestration_run_id == run_id)).all()
    return {"run": run, "steps": steps}


@router.get("/runs/{run_id}/stream")
def stream_run_events(run_id: int):
    def gen():
        yield f"event: step\ndata: {{\"run_id\": {run_id}, \"status\": \"running\"}}\n\n"
        yield f"event: done\ndata: {{\"run_id\": {run_id}, \"status\": \"completed\"}}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
