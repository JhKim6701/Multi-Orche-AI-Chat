from __future__ import annotations

from typing import Any, TypedDict


class OrchestrationState(TypedDict, total=False):
    project_id: int
    chat_thread_id: int
    run_id: int
    user_message_id: int
    segment_id: int
    content_markdown: str

    selected_model_names: list[str]
    orchestrator_model_name: str | None
    require_approval_before_publish: bool

    model_name: str
    routing_reason: str
    gpu_enabled: bool

    has_image: bool
    image_asset_ids: list[int]
    image_payloads: list[str]
    needs_reasoning: bool
    context_hits: list[dict[str, Any]]
    packed_context: str
    retrieval_meta: dict[str, Any]
    context_block: str
    parent_summary_used: bool

    step_outputs: list[str]
    used_asset_ids: list[int]
    used_chunk_ids: list[int]

    reviewer_decision: str
    critic_model: str
    revised: bool
    final_text: str
    model_role: str

    should_run_specialist: bool
    should_revise: bool
    approval_status: str
