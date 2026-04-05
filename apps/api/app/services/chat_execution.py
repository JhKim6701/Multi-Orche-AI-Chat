from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Asset, ConversationSegment, Message, ModelRegistry, RoleEnum
from app.services.asset_ingestion import retrieve_relevant_context
from app.services.ollama_client import OllamaClient
from app.services.topic_segmentation import maybe_start_new_segment, update_segment_summary


def _build_context_block(context_hits: list[dict]) -> str:
    if not context_hits:
        return ""
    lines = ["참고 자산 컨텍스트:"]
    for hit in context_hits:
        lines.append(f"- asset#{hit['asset_id']}({hit['filename']}): {hit['snippet']}")
    return "\n".join(lines)


async def execute_chat(
    db: Session,
    project_id: int,
    chat_thread_id: int,
    content_markdown: str,
    selected_model_names: list[str],
    execution_mode: str,
    message_asset_ids: list[int],
) -> tuple[int, Message, list[Message]]:
    selected_rows = db.scalars(
        select(ModelRegistry)
        .where(
            ModelRegistry.model_name.in_(selected_model_names),
            ModelRegistry.enabled.is_(True),
            ModelRegistry.downloaded.is_(True),
        )
        .order_by(ModelRegistry.sort_order.asc(), ModelRegistry.model_name.asc())
    ).all()
    execution_models = [m.model_name for m in selected_rows]
    if not execution_models:
        raise ValueError("실행 가능한 enabled/downloaded 모델이 없습니다. 모델 sync/pull/enable 상태를 확인하세요.")

    segment, divergence = maybe_start_new_segment(db, chat_thread_id, content_markdown)

    max_seq = db.scalar(select(func.max(Message.sequence_no)).where(Message.chat_thread_id == chat_thread_id)) or 0
    user_msg = Message(
        project_id=project_id,
        chat_thread_id=chat_thread_id,
        segment_id=segment.id,
        role=RoleEnum.user,
        content_markdown=content_markdown,
        plain_text_cache=content_markdown,
        sequence_no=max_seq + 1,
        model_role="segment_start" if divergence.get("diverged") else None,
    )
    db.add(user_msg)
    db.flush()

    if message_asset_ids:
        assets = db.scalars(select(Asset).where(Asset.id.in_(message_asset_ids), Asset.chat_thread_id == chat_thread_id)).all()
        for asset in assets:
            asset.message_id = user_msg.id

    context_hits = retrieve_relevant_context(db=db, chat_thread_id=chat_thread_id, query=content_markdown, limit=6)
    context_block = _build_context_block(context_hits)

    history = db.scalars(
        select(Message)
        .where(Message.chat_thread_id == chat_thread_id, Message.segment_id == segment.id)
        .order_by(Message.sequence_no.asc())
    ).all()
    parent_summary = ""
    if segment.parent_segment_id:
        parent = db.get(ConversationSegment, segment.parent_segment_id)
        if parent:
            parent_summary = f"Parent segment summary: {parent.topic_summary[:200]}"

    context_messages = [{"role": m.role.value if hasattr(m.role, "value") else str(m.role), "content": m.content_markdown} for m in history]
    if parent_summary:
        context_messages = [{"role": "system", "content": parent_summary}] + context_messages

    client = OllamaClient()
    assistant_messages: list[Message] = []
    chain_input = content_markdown

    for idx, model_name in enumerate(execution_models):
        user_content = chain_input if execution_mode == "chained" else content_markdown
        prompt = f"{user_content}\n\n{context_block}" if context_block else user_content
        query_messages = context_messages + [{"role": "user", "content": prompt}]

        response = await client.chat(model_name=model_name, messages=query_messages)
        answer = response.get("message", {}).get("content") or "(empty response)"
        if context_hits:
            sources = ", ".join(f"#{h['asset_id']}:{h['filename']}" for h in context_hits[:3])
            answer = f"{answer}\n\n[Used assets] {sources}"

        asst = Message(
            project_id=project_id,
            chat_thread_id=chat_thread_id,
            segment_id=segment.id,
            role=RoleEnum.assistant,
            content_markdown=answer,
            plain_text_cache=answer,
            sequence_no=max_seq + 2 + idx,
            model_name=model_name,
            model_role="assistant",
        )
        db.add(asst)
        assistant_messages.append(asst)
        context_messages.append({"role": "assistant", "content": answer})
        if execution_mode == "chained":
            chain_input = answer

    update_segment_summary(db, segment.id)
    db.commit()
    db.refresh(user_msg)
    for message in assistant_messages:
        db.refresh(message)
    return segment.id, user_msg, assistant_messages
