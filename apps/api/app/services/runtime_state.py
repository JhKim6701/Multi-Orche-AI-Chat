from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings

_STATE_FILE = Path(settings.runtime_state_file)


def _load_state() -> dict:
    if not _STATE_FILE.exists():
        return {"gpu_enabled": True}
    try:
        return json.loads(_STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"gpu_enabled": True}


def _save_state(state: dict) -> None:
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.write_text(json.dumps(state), encoding="utf-8")


def get_gpu_enabled() -> bool:
    return bool(_load_state().get("gpu_enabled", True))


def set_gpu_enabled(enabled: bool) -> bool:
    state = _load_state()
    state["gpu_enabled"] = bool(enabled)
    _save_state(state)
    return bool(state["gpu_enabled"])
