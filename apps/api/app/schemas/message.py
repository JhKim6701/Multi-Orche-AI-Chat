from datetime import datetime

from pydantic import BaseModel


class MessageCreate(BaseModel):
    project_id: int
    chat_thread_id: int
    content_markdown: str


class MessageOut(BaseModel):
    id: int
    project_id: int
    chat_thread_id: int
    role: str
    content_markdown: str
    model_name: str | None
    sequence_no: int
    created_at: datetime

    class Config:
        from_attributes = True
