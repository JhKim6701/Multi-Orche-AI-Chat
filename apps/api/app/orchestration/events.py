from __future__ import annotations

from app.models import OrchestrationStep


EVENT_NAME_MAP = {
    "reviewer_critic": ("reviewer_started", "reviewer_completed"),
    "critic_debate": ("critic_started", "critic_completed"),
    "specialist_analyzer": ("specialist_started", "specialist_completed"),
    "final_responder_revision": ("revision_started", "revision_completed"),
}


def step_event_names(step: OrchestrationStep) -> tuple[str, str]:
    return EVENT_NAME_MAP.get(step.step_name, ("step_started", "step_completed"))
