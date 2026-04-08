from pathlib import Path

from app.services import runtime_state
from app.services.state_store import AtomicJsonFileStore


def test_runtime_state_atomicity_behavior(tmp_path, monkeypatch):
    state_file = tmp_path / "runtime_state.json"
    store = AtomicJsonFileStore(Path(state_file), default_data={"gpu_enabled": True})
    monkeypatch.setattr(runtime_state, "_STORE", store)

    for enabled in [False, True, False, True, False]:
        runtime_state.set_gpu_enabled(enabled)

    assert runtime_state.get_gpu_enabled() is False
    raw = state_file.read_text(encoding="utf-8")
    assert raw.strip().startswith("{") and raw.strip().endswith("}")
