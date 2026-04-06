from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Asset
from app.utils.files import safe_join, sanitize_filename


def _infer_artifact_type(text: str) -> tuple[str, str, str]:
    stripped = text.strip()
    if stripped.startswith("```"):
        first = stripped.splitlines()[0].replace("```", "").strip().lower()
        if first in {"python", "py"}:
            return "code", "text/x-python", "response.py"
        if first in {"typescript", "ts"}:
            return "code", "text/typescript", "response.ts"
        if first in {"javascript", "js"}:
            return "code", "text/javascript", "response.js"
        return "code", "text/plain", "response.txt"

    if stripped.startswith("{") or stripped.startswith("["):
        try:
            json.loads(stripped)
            return "json", "application/json", "response.json"
        except json.JSONDecodeError:
            pass

    if len(stripped) > 480 or "#" in stripped:
        return "markdown", "text/markdown", "response.md"

    return "text", "text/plain", "response.txt"


def create_ai_generated_artifact(
    db: Session,
    *,
    project_id: int,
    chat_thread_id: int,
    message_id: int,
    content: str,
    model_name: str | None,
    model_role: str | None,
    orchestration_run_id: int | None = None,
) -> Asset:
    kind, mime_type, default_name = _infer_artifact_type(content)
    root = Path(settings.upload_root)
    generated_dir = safe_join(root, "projects", str(project_id), "chats", str(chat_thread_id), "generated", str(message_id))
    generated_dir.mkdir(parents=True, exist_ok=True)

    stamped_name = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{default_name}"
    filename = sanitize_filename(stamped_name)
    target = safe_join(generated_dir, filename)
    try:
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"generated artifact write failed: {exc}") from exc

    metadata = {
        "kind": kind,
        "generation_kind": kind,
        "generated_from_message_id": message_id,
        "source_message_id": message_id,
    }
    if kind == "markdown":
        metadata["artifact_summary"] = "structured_report"
    if kind == "code":
        metadata["artifact_summary"] = "code_file"
    if orchestration_run_id is not None:
        metadata["orchestration_run_id"] = orchestration_run_id
    if "image" in content.lower():
        metadata["image_placeholder"] = True

    asset = Asset(
        project_id=project_id,
        chat_thread_id=chat_thread_id,
        message_id=message_id,
        source_type="ai_generated",
        asset_type="document",
        mime_type=mime_type,
        original_filename=filename,
        stored_path=str(target),
        derived_metadata_json=metadata,
        producing_model=model_name,
        producing_role=model_role,
    )
    db.add(asset)
    db.flush()
    return asset
