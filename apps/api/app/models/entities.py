from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RoleEnum(str, Enum):
    user = "user"
    assistant = "assistant"
    system = "system"
    orchestrator = "orchestrator"


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class ChatThread(Base):
    __tablename__ = "chat_threads"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    chat_thread_id: Mapped[int] = mapped_column(ForeignKey("chat_threads.id"), index=True)
    role: Mapped[RoleEnum] = mapped_column(SAEnum(RoleEnum), index=True)
    content_markdown: Mapped[str] = mapped_column(Text)
    plain_text_cache: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model_role: Mapped[str | None] = mapped_column(String(120), nullable=True)
    sequence_no: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    chat_thread_id: Mapped[int] = mapped_column(ForeignKey("chat_threads.id"), index=True)
    message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id"), nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(50))
    asset_type: Mapped[str] = mapped_column(String(50))
    mime_type: Mapped[str] = mapped_column(String(120))
    original_filename: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(500))
    derived_metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    producing_model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    producing_role: Mapped[str | None] = mapped_column(String(120), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ModelRegistry(Base):
    __tablename__ = "model_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    model_name: Mapped[str] = mapped_column(String(140), unique=True)
    provider: Mapped[str] = mapped_column(String(50), default="ollama")
    downloaded: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    supports_vision: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_tools: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_embeddings: Mapped[bool] = mapped_column(Boolean, default=False)
    supports_reasoning: Mapped[bool] = mapped_column(Boolean, default=False)
    preferred_roles_json: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class OrchestrationRun(Base):
    __tablename__ = "orchestration_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    chat_thread_id: Mapped[int] = mapped_column(ForeignKey("chat_threads.id"), index=True)
    user_message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), index=True)
    status: Mapped[str] = mapped_column(String(40), default="running")
    graph_name: Mapped[str] = mapped_column(String(100), default="default_orchestrator")
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    final_message_id: Mapped[int | None] = mapped_column(ForeignKey("messages.id"), nullable=True)


class OrchestrationStep(Base):
    __tablename__ = "orchestration_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    orchestration_run_id: Mapped[int] = mapped_column(ForeignKey("orchestration_runs.id"), index=True)
    step_name: Mapped[str] = mapped_column(String(100))
    assigned_role: Mapped[str] = mapped_column(String(50))
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    input_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), default="pending")
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


Index("ix_messages_chat_sequence", Message.chat_thread_id, Message.sequence_no)
