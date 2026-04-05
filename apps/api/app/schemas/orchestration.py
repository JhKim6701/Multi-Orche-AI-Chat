from datetime import datetime

from pydantic import BaseModel


class OrchestrationRunCreate(BaseModel):
    project_id: int
    chat_thread_id: int
    user_message_id: int


class OrchestrationRunOut(BaseModel):
    id: int
    project_id: int
    chat_thread_id: int
    user_message_id: int
    status: str
    graph_name: str
    started_at: datetime
    ended_at: datetime | None
    final_message_id: int | None

    class Config:
        from_attributes = True
