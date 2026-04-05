from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class MessageCreate(BaseModel):
    project_id: int
    chat_thread_id: int
    segment_id: int | None = None
    content_markdown: str


class MessageOut(BaseModel):
    id: int
    project_id: int
    chat_thread_id: int
    segment_id: int | None
    role: str
    content_markdown: str
    model_name: str | None
    model_role: str | None
    sequence_no: int
    created_at: datetime

    class Config:
        from_attributes = True


class MessageExecutionRequest(BaseModel):
    project_id: int
    chat_thread_id: int
    segment_id: int | None = None
    content_markdown: str = Field(min_length=1)
    selected_model_names: list[str] = Field(min_length=1)
    execution_mode: Literal["independent", "chained", "ordered"] = "independent"
    message_asset_ids: list[int] = Field(default_factory=list)


class MessageExecutionResult(BaseModel):
    used_segment_id: int
    user_message: MessageOut
    assistant_messages: list[MessageOut]


class MessageScopeMeta(BaseModel):
    scope: Literal["active", "segment", "all"]
    active_segment_id: int | None = None
    selected_segment_id: int | None = None
    segment_boundaries: list[int] = Field(default_factory=list)


class MessageListResponse(BaseModel):
    items: list[MessageOut]
    scope_meta: MessageScopeMeta
