from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ChatThread
from app.schemas.chat import ChatCreate, ChatOut

router = APIRouter(prefix="/chats", tags=["chats"])


@router.post("", response_model=ChatOut)
def create_chat(payload: ChatCreate, db: Session = Depends(get_db)):
    chat = ChatThread(project_id=payload.project_id, title=payload.title)
    db.add(chat)
    db.commit()
    db.refresh(chat)
    return chat


@router.get("", response_model=list[ChatOut])
def list_chats(project_id: int, db: Session = Depends(get_db)):
    return db.scalars(
        select(ChatThread)
        .where(ChatThread.project_id == project_id, ChatThread.deleted_at.is_(None))
        .order_by(ChatThread.updated_at.desc())
    ).all()


@router.get("/{chat_id}", response_model=ChatOut)
def get_chat(chat_id: int, db: Session = Depends(get_db)):
    chat = db.get(ChatThread, chat_id)
    if not chat or chat.deleted_at:
        raise HTTPException(status_code=404, detail="chat not found")
    return chat


@router.delete("/{chat_id}")
def delete_chat(chat_id: int, db: Session = Depends(get_db)):
    chat = db.get(ChatThread, chat_id)
    if not chat or chat.deleted_at:
        raise HTTPException(status_code=404, detail="chat not found")
    from datetime import datetime

    chat.deleted_at = datetime.utcnow()
    db.commit()
    return {"ok": True}
