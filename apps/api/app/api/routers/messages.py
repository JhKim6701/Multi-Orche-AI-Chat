import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Message, RoleEnum
from app.schemas.message import MessageCreate, MessageExecutionRequest, MessageExecutionResult, MessageOut
from app.services.chat_execution import execute_chat
from app.services.ollama_client import OllamaClient, OllamaUnavailableError
from app.services.topic_segmentation import get_or_create_active_segment

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("", response_model=list[MessageOut])
def list_messages(chat_thread_id: int, scope: str = "active", segment_id: int | None = None, db: Session = Depends(get_db)):
    q = select(Message).where(Message.chat_thread_id == chat_thread_id)
    if scope == "active":
        active = get_or_create_active_segment(db, chat_thread_id)
        q = q.where(Message.segment_id == active.id)
    elif scope == "segment":
        if not segment_id:
            raise HTTPException(status_code=400, detail="segment scope requires segment_id")
        q = q.where(Message.segment_id == segment_id)
    elif scope == "all":
        pass
    else:
        raise HTTPException(status_code=400, detail="invalid scope")

    return db.scalars(q.order_by(Message.sequence_no.asc())).all()


@router.post("", response_model=MessageOut)
def create_user_message(payload: MessageCreate, db: Session = Depends(get_db)):
    max_seq = db.scalar(select(func.max(Message.sequence_no)).where(Message.chat_thread_id == payload.chat_thread_id)) or 0
    seg = get_or_create_active_segment(db, payload.chat_thread_id)
    msg = Message(
        project_id=payload.project_id,
        chat_thread_id=payload.chat_thread_id,
        segment_id=payload.segment_id or seg.id,
        role=RoleEnum.user,
        content_markdown=payload.content_markdown,
        plain_text_cache=payload.content_markdown,
        sequence_no=max_seq + 1,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg


@router.post("/execute", response_model=MessageExecutionResult)
async def execute_message(payload: MessageExecutionRequest, db: Session = Depends(get_db)):
    try:
        used_segment_id, user, assistants = await execute_chat(
            db=db,
            project_id=payload.project_id,
            chat_thread_id=payload.chat_thread_id,
            content_markdown=payload.content_markdown,
            selected_model_names=payload.selected_model_names,
            execution_mode=payload.execution_mode,
            message_asset_ids=payload.message_asset_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OllamaUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return MessageExecutionResult(used_segment_id=used_segment_id, user_message=user, assistant_messages=assistants)


@router.get("/stream")
async def stream_single_model(chat_thread_id: int, model_name: str, prompt: str, scope: str = "active", segment_id: int | None = None, db: Session = Depends(get_db)):
    client = OllamaClient()
    q = select(Message).where(Message.chat_thread_id == chat_thread_id)
    if scope == "active":
        seg = get_or_create_active_segment(db, chat_thread_id)
        q = q.where(Message.segment_id == seg.id)
    elif scope == "segment":
        if not segment_id:
            raise HTTPException(status_code=400, detail="segment scope requires segment_id")
        q = q.where(Message.segment_id == segment_id)
    elif scope == "all":
        pass
    else:
        raise HTTPException(status_code=400, detail="invalid scope")

    history = db.scalars(q.order_by(Message.sequence_no.asc())).all()
    stream_messages = [{"role": m.role.value if hasattr(m.role, "value") else str(m.role), "content": m.content_markdown} for m in history[-10:]]
    stream_messages.append({"role": "user", "content": prompt})

    async def gen():
        try:
            async for line in client.stream_chat(model_name=model_name, messages=stream_messages):
                yield f"data: {line}\n\n"
        except OllamaUnavailableError as exc:
            yield f"event: error\ndata: {json.dumps({'detail': str(exc)})}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")
