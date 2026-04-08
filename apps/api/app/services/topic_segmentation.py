from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ConversationSegment, Message

SHIFT_TOKENS = ["다른 질문", "새 주제", "그건 됐고", "이제", "topic change", "switch topic"]
CONTINUATION_TOKENS = ["계속", "이어", "추가", "더 자세히", "continue", "more", "elaborate", "그럼", "그리고"]


def _tokenize(text: str) -> set[str]:
    return {t.lower() for t in text.replace("\n", " ").split() if len(t) > 1}


def detect_topic_divergence(recent_text: str, new_text: str, segment_summary: str = "") -> tuple[bool, float, str, str]:
    text = new_text.lower().strip()
    if len(text) < 4:
        return False, 1.0, "too_short_fallback", "stay"
    if len(text) < 10:
        return False, 1.0, "short_input_fallback", "stay"

    if any(tok in text for tok in CONTINUATION_TOKENS):
        return False, 0.8, "continuation_expression_detected", "stay"

    if any(tok in text for tok in SHIFT_TOKENS):
        return True, 0.0, "shift_expression_detected", "new_segment"

    recent_tokens = _tokenize(recent_text)
    new_tokens = _tokenize(new_text)
    summary_tokens = _tokenize(segment_summary)
    if not new_tokens:
        return False, 1.0, "insufficient_context", "stay"

    recent_overlap = len(recent_tokens & new_tokens) / max(1, len(new_tokens)) if recent_tokens else 0.0
    summary_overlap = len(summary_tokens & new_tokens) / max(1, len(new_tokens)) if summary_tokens else recent_overlap
    overlap = max(recent_overlap, summary_overlap)

    if overlap < 0.08:
        return True, overlap, "very_low_overlap_with_segment", "new_segment"
    if overlap < 0.15:
        return True, overlap, "low_overlap_with_segment", "new_segment"
    return False, overlap, "same_topic", "stay"


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
        .limit(8)
    ).all()
    recent_text = "\n".join(m.content_markdown for m in reversed(recent_msgs))

    diverged, score, reason, action = detect_topic_divergence(recent_text, new_text, active.topic_summary or "")
    if not diverged:
        return active, {
            "diverged": False,
            "overlap": score,
            "reason": reason,
            "recommended_action": action,
            "segment_id": active.id,
            "active_segment_id": active.id,
        }

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
    return seg, {
        "diverged": True,
        "overlap": score,
        "reason": reason,
        "recommended_action": action,
        "segment_id": seg.id,
        "active_segment_id": active.id,
        "parent_segment_id": active.id,
    }


def update_segment_summary(db: Session, segment_id: int) -> None:
    seg = db.get(ConversationSegment, segment_id)
    if not seg:
        return
    msgs = db.scalars(
        select(Message)
        .where(Message.segment_id == segment_id)
        .order_by(Message.sequence_no.asc())
        .limit(20)
    ).all()
    if msgs:
        merged = " ".join(m.content_markdown for m in msgs)
        seg.topic_summary = merged[:320]
        seg.updated_at = datetime.utcnow()
