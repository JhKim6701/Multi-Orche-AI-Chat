from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Message, RoleEnum
from app.schemas.message import MessageCreate, MessageOut

router = APIRouter(prefix="/messages", tags=["messages"])


@router.get("", response_model=list[MessageOut])
def list_messages(chat_thread_id: int, db: Session = Depends(get_db)):
    return db.scalars(select(Message).where(Message.chat_thread_id == chat_thread_id).order_by(Message.sequence_no.asc())).all()


@router.post("", response_model=MessageOut)
def create_user_message(payload: MessageCreate, db: Session = Depends(get_db)):
    max_seq = db.scalar(select(func.max(Message.sequence_no)).where(Message.chat_thread_id == payload.chat_thread_id)) or 0
    msg = Message(
        project_id=payload.project_id,
        chat_thread_id=payload.chat_thread_id,
        role=RoleEnum.user,
        content_markdown=payload.content_markdown,
        plain_text_cache=payload.content_markdown,
        sequence_no=max_seq + 1,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg
