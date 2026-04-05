from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models import OrchestrationRun, OrchestrationStep


def create_minimal_run(db: Session, project_id: int, chat_thread_id: int, user_message_id: int) -> OrchestrationRun:
    run = OrchestrationRun(
        project_id=project_id,
        chat_thread_id=chat_thread_id,
        user_message_id=user_message_id,
        status="running",
        graph_name="rule_based_orchestrator",
    )
    db.add(run)
    db.flush()
    for idx, (name, role) in enumerate([
        ("planner", "planner"),
        ("context_resolver", "context_resolver"),
        ("final_responder", "final_responder"),
    ]):
        db.add(
            OrchestrationStep(
                orchestration_run_id=run.id,
                step_name=name,
                assigned_role=role,
                status="completed" if idx < 2 else "pending",
                input_summary="auto-generated input",
                output_summary="auto-generated output" if idx < 2 else None,
                started_at=datetime.utcnow(),
                ended_at=datetime.utcnow() if idx < 2 else None,
            )
        )
    db.commit()
    db.refresh(run)
    return run
