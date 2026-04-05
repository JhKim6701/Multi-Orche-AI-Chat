from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class OrchestrationRunCreate(BaseModel):
    project_id: int
    chat_thread_id: int
    user_message_id: int | None = None
    content_markdown: str | None = None
    selected_model_names: list[str] = Field(default_factory=list)
    orchestrator_model_name: str | None = None
    message_asset_ids: list[int] = Field(default_factory=list)
    require_approval_before_publish: bool = False


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


class OrchestrationStepOut(BaseModel):
    id: int
    step_name: str
    assigned_role: str
    model_name: str | None
    status: str
    input_summary: str | None
    output_summary: str | None
    routing_reason: str | None = None
    reviewer_decision: str | None = None
    used_asset_ids: list[int] = Field(default_factory=list)
    image_asset_ids: list[int] = Field(default_factory=list)
    vision_used: bool | None = None
    gpu_enabled: bool | None = None
    used_segment_id: int | None = None
    parent_segment_summary_used: bool | None = None
    step_group: str | None = None
    depends_on_step_ids: list[int] = Field(default_factory=list)
    execution_mode: str | None = None
    fallback_model_name: str | None = None
    approval_required: bool | None = None
    approval_status: str | None = None


class OrchestrationRunDetail(BaseModel):
    run: dict[str, Any]
    steps: list[OrchestrationStepOut]
    final_message: dict[str, Any] | None
