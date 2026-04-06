from __future__ import annotations

from pathlib import Path

from app.core.config import settings
from app.services.state_store import AtomicJsonFileStore

_STATE_FILE = Path(settings.runtime_state_file)
_STORE = AtomicJsonFileStore(_STATE_FILE, default_data={"gpu_enabled": True})


def _load_state() -> dict:
    state = _STORE.load()
    if "gpu_enabled" not in state:
        state["gpu_enabled"] = True
    return state


def _save_state(state: dict) -> None:
    _STORE.save(state)


def get_gpu_enabled() -> bool:
    return bool(_load_state().get("gpu_enabled", True))


def set_gpu_enabled(enabled: bool) -> bool:
    target = bool(enabled)

    def _mutate(state: dict) -> dict:
        state["gpu_enabled"] = target
        return state

    updated = _STORE.update(_mutate)
    return bool(updated.get("gpu_enabled", True))
