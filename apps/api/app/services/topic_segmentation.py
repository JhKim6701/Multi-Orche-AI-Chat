from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ConversationSegment, Message

SHIFT_TOKENS = ["다른 질문", "새 주제", "그건 됐고", "이제", "topic change", "switch topic"]


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in text.replace("\n", " ").split() if len(t) > 2}


def detect_topic_divergence(recent_text: str, new_text: str) -> tuple[bool, float, str]:
    if any(tok in new_text.lower() for tok in SHIFT_TOKENS):
        return True, 0.0, "shift_expression_detected"

    recent_tokens = _tokenize(recent_text)
    new_tokens = _tokenize(new_text)
    if not recent_tokens or not new_tokens:
        return False, 1.0, "insufficient_context"

    overlap = len(recent_tokens & new_tokens) / max(1, len(new_tokens))
    if overlap < 0.12:
        return True, overlap, "low_keyword_overlap"
    return False, overlap, "same_topic"


def get_or_create_active_segment(db: Session, chat_thread_id: int) -> ConversationSegment:
    seg = db.scalar(
        select(ConversationSegment)
        .where(ConversationSegment.chat_thread_id == chat_thread_id, ConversationSegment.is_active.is_(True))
        .order_by(ConversationSegment.updated_at.desc())
    )
    if seg:
        return seg

    seg = ConversationSegment(chat_thread_id=chat_thread_id, topic_label="general", topic_summary="Initial segment", is_active=True)
    db.add(seg)
    db.flush()
    return seg


def maybe_start_new_segment(db: Session, chat_thread_id: int, new_text: str) -> tuple[ConversationSegment, dict]:
    active = get_or_create_active_segment(db, chat_thread_id)
    recent_msgs = db.scalars(
        select(Message)
        .where(Message.chat_thread_id == chat_thread_id, Message.segment_id == active.id)
        .order_by(Message.sequence_no.desc())
        .limit(6)
    ).all()
    recent_text = "\n".join(m.content_markdown for m in reversed(recent_msgs))

    diverged, score, reason = detect_topic_divergence(recent_text, new_text)
    if not diverged:
        return active, {"diverged": False, "overlap": score, "reason": reason, "segment_id": active.id}

    active.is_active = False
    topic_label = " ".join(new_text.split()[:5])[:80] or "new-topic"
    seg = ConversationSegment(
        chat_thread_id=chat_thread_id,
        parent_segment_id=active.id,
        branch_from_message_id=recent_msgs[0].id if recent_msgs else None,
        topic_label=topic_label,
        topic_summary=new_text[:220],
        is_active=True,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(seg)
    db.flush()
    return seg, {"diverged": True, "overlap": score, "reason": reason, "segment_id": seg.id, "parent_segment_id": active.id}


def update_segment_summary(db: Session, segment_id: int) -> None:
    seg = db.get(ConversationSegment, segment_id)
    if not seg:
        return
    msgs = db.scalars(
        select(Message)
        .where(Message.segment_id == segment_id)
        .order_by(Message.sequence_no.asc())
        .limit(12)
    ).all()
    if msgs:
        merged = " ".join(m.content_markdown for m in msgs)
        seg.topic_summary = merged[:320]
        seg.updated_at = datetime.utcnow()
