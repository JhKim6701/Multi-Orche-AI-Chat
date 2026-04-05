from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ConversationSegment, Message
from app.services.topic_segmentation import detect_topic_divergence, get_or_create_active_segment

router = APIRouter(prefix="/segments", tags=["segments"])


class SegmentSwitch(BaseModel):
    segment_id: int


class BranchCreate(BaseModel):
    from_message_id: int
    topic_label: str | None = None


@router.get("")
def list_segments(chat_thread_id: int, db: Session = Depends(get_db)):
    segments = db.scalars(select(ConversationSegment).where(ConversationSegment.chat_thread_id == chat_thread_id).order_by(ConversationSegment.created_at.asc())).all()
    return [
        {
            "id": s.id,
            "topic_label": s.topic_label,
            "topic_summary": s.topic_summary,
            "is_active": s.is_active,
            "parent_segment_id": s.parent_segment_id,
            "branch_from_message_id": s.branch_from_message_id,
        }
        for s in segments
    ]


@router.get("/{segment_id}")
def segment_detail(segment_id: int, db: Session = Depends(get_db)):
    seg = db.get(ConversationSegment, segment_id)
    if not seg:
        raise HTTPException(status_code=404, detail="segment not found")
    msgs = db.scalars(select(Message).where(Message.segment_id == segment_id).order_by(Message.sequence_no.asc())).all()
    return {
        "segment": {
            "id": seg.id,
            "topic_label": seg.topic_label,
            "topic_summary": seg.topic_summary,
            "is_active": seg.is_active,
            "parent_segment_id": seg.parent_segment_id,
            "branch_from_message_id": seg.branch_from_message_id,
        },
        "messages": [{"id": m.id, "role": m.role.value if hasattr(m.role, 'value') else str(m.role), "content_markdown": m.content_markdown} for m in msgs],
    }


@router.post("/detect")
def detect_divergence(chat_thread_id: int, new_text: str, db: Session = Depends(get_db)):
    active = get_or_create_active_segment(db, chat_thread_id)
    recent = db.scalars(select(Message).where(Message.segment_id == active.id).order_by(Message.sequence_no.desc()).limit(6)).all()
    recent_text = "\n".join(m.content_markdown for m in reversed(recent))
    diverged, overlap, reason = detect_topic_divergence(recent_text, new_text)
    return {"active_segment_id": active.id, "diverged": diverged, "overlap": overlap, "reason": reason}


@router.post("/switch")
def switch_segment(chat_thread_id: int, payload: SegmentSwitch, db: Session = Depends(get_db)):
    segments = db.scalars(select(ConversationSegment).where(ConversationSegment.chat_thread_id == chat_thread_id)).all()
    target = None
    for seg in segments:
        seg.is_active = seg.id == payload.segment_id
        if seg.id == payload.segment_id:
            target = seg
    if not target:
        raise HTTPException(status_code=404, detail="segment not found")
    target.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "active_segment_id": target.id}


@router.post("/branch")
def create_branch(chat_thread_id: int, payload: BranchCreate, db: Session = Depends(get_db)):
    msg = db.get(Message, payload.from_message_id)
    if not msg or msg.chat_thread_id != chat_thread_id:
        raise HTTPException(status_code=404, detail="message not found")

    active = get_or_create_active_segment(db, chat_thread_id)
    active.is_active = False
    seg = ConversationSegment(
        chat_thread_id=chat_thread_id,
        parent_segment_id=msg.segment_id or active.id,
        branch_from_message_id=msg.id,
        topic_label=payload.topic_label or f"branch-{msg.id}",
        topic_summary=msg.content_markdown[:240],
        is_active=True,
    )
    db.add(seg)
    db.commit()
    db.refresh(seg)
    return {"segment_id": seg.id, "parent_segment_id": seg.parent_segment_id, "branch_from_message_id": seg.branch_from_message_id}
