from pathlib import Path

from app.services import approval_state, runtime_state
from app.services.approval_state import FileApprovalStateBackend
from app.services.state_store import AtomicJsonFileStore


def test_approval_state_atomicity_behavior(tmp_path, monkeypatch):
    state_file = tmp_path / "pending_approvals.json"
    backend = FileApprovalStateBackend(state_file)
    monkeypatch.setattr(approval_state, "_backend", backend)

    approval_state.set_pending(10, {"chat_thread_id": 1, "content_markdown": "draft"})
    pending = approval_state.get_pending(10)
    assert pending and pending["content_markdown"] == "draft"

    first = approval_state.mark_approved(10, final_message_id=99)
    second = approval_state.mark_approved(10, final_message_id=99)
    assert first.status == "approved"
    assert second.status == "approved"
    assert second.idempotent is True

    text = state_file.read_text(encoding="utf-8")
    assert '"status":"approved"' in text


def test_runtime_state_atomicity_behavior(tmp_path, monkeypatch):
    state_file = tmp_path / "runtime_state.json"
    store = AtomicJsonFileStore(Path(state_file), default_data={"gpu_enabled": True})
    monkeypatch.setattr(runtime_state, "_STORE", store)

    for enabled in [False, True, False, True, False]:
        runtime_state.set_gpu_enabled(enabled)

    assert runtime_state.get_gpu_enabled() is False
    raw = state_file.read_text(encoding="utf-8")
    assert raw.strip().startswith("{") and raw.strip().endswith("}")
