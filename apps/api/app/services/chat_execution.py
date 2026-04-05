from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Asset, Message, ModelRegistry, RoleEnum
from app.services.ollama_client import OllamaClient


async def execute_chat(
    db: Session,
    project_id: int,
    chat_thread_id: int,
    content_markdown: str,
    selected_model_names: list[str],
    execution_mode: str,
    message_asset_ids: list[int],
) -> tuple[Message, list[Message]]:
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

    max_seq = db.scalar(select(func.max(Message.sequence_no)).where(Message.chat_thread_id == chat_thread_id)) or 0
    user_msg = Message(
        project_id=project_id,
        chat_thread_id=chat_thread_id,
        role=RoleEnum.user,
        content_markdown=content_markdown,
        plain_text_cache=content_markdown,
        sequence_no=max_seq + 1,
    )
    db.add(user_msg)
    db.flush()

    if message_asset_ids:
        assets = db.scalars(select(Asset).where(Asset.id.in_(message_asset_ids), Asset.chat_thread_id == chat_thread_id)).all()
        for asset in assets:
            asset.message_id = user_msg.id

    history = db.scalars(select(Message).where(Message.chat_thread_id == chat_thread_id).order_by(Message.sequence_no.asc())).all()
    context_messages = [{"role": m.role.value if hasattr(m.role, "value") else str(m.role), "content": m.content_markdown} for m in history]

    client = OllamaClient()
    assistant_messages: list[Message] = []
    chain_input = content_markdown

    for idx, model_name in enumerate(execution_models):
        if execution_mode == "chained":
            query_messages = context_messages + [{"role": "user", "content": chain_input}]
        else:
            query_messages = context_messages + [{"role": "user", "content": content_markdown}]

        response = await client.chat(model_name=model_name, messages=query_messages)
        answer = response.get("message", {}).get("content") or "(empty response)"

        asst = Message(
            project_id=project_id,
            chat_thread_id=chat_thread_id,
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

    db.commit()
    db.refresh(user_msg)
    for message in assistant_messages:
        db.refresh(message)
    return user_msg, assistant_messages
