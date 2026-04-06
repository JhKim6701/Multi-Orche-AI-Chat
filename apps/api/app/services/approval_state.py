from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from app.core.config import settings
from app.services.state_store import AtomicJsonFileStore


@dataclass
class ApprovalTransitionResult:
    status: str
    payload: dict[str, Any] | None
    final_message_id: int | None = None
    idempotent: bool = False


class ApprovalStateBackend(Protocol):
    def set_pending(self, run_id: int, payload: dict[str, Any]) -> None: ...

    def get_pending(self, run_id: int) -> dict[str, Any] | None: ...

    def mark_approved(self, run_id: int, final_message_id: int | None = None) -> ApprovalTransitionResult: ...

    def mark_rejected(self, run_id: int) -> ApprovalTransitionResult: ...


class FileApprovalStateBackend:
    def __init__(self, file_path: Path):
        self.store = AtomicJsonFileStore(file_path=file_path, default_data={})

    def set_pending(self, run_id: int, payload: dict[str, Any]) -> None:
        run_key = str(run_id)

        def _mutate(data: dict[str, Any]) -> dict[str, Any]:
            data[run_key] = {
                "status": "pending",
                "payload": payload,
                "updated_at": datetime.utcnow().isoformat(),
            }
            return data

        self.store.update(_mutate)

    def get_pending(self, run_id: int) -> dict[str, Any] | None:
        entry = self.store.load().get(str(run_id))
        if not isinstance(entry, dict):
            return None
        if entry.get("status") != "pending":
            return None
        payload = entry.get("payload")
        return payload if isinstance(payload, dict) else None

    def mark_approved(self, run_id: int, final_message_id: int | None = None) -> ApprovalTransitionResult:
        run_key = str(run_id)
        entry = self.store.load().get(run_key)
        if not isinstance(entry, dict):
            return ApprovalTransitionResult(status="missing", payload=None)

        status = entry.get("status")
        if status == "approved":
            return ApprovalTransitionResult(
                status="approved",
                payload=entry.get("payload") if isinstance(entry.get("payload"), dict) else None,
                final_message_id=entry.get("final_message_id"),
                idempotent=True,
            )
        if status != "pending":
            return ApprovalTransitionResult(status=str(status or "missing"), payload=None)

        payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else None

        def _mutate(data: dict[str, Any]) -> dict[str, Any]:
            cur = data.get(run_key)
            if not isinstance(cur, dict):
                return data
            cur["status"] = "approved"
            cur["final_message_id"] = final_message_id
            cur["updated_at"] = datetime.utcnow().isoformat()
            data[run_key] = cur
            return data

        self.store.update(_mutate)
        return ApprovalTransitionResult(status="approved", payload=payload, final_message_id=final_message_id)

    def mark_rejected(self, run_id: int) -> ApprovalTransitionResult:
        run_key = str(run_id)
        entry = self.store.load().get(run_key)
        if not isinstance(entry, dict):
            return ApprovalTransitionResult(status="missing", payload=None)

        status = entry.get("status")
        if status == "rejected":
            return ApprovalTransitionResult(status="rejected", payload=entry.get("payload"), idempotent=True)
        if status != "pending":
            return ApprovalTransitionResult(status=str(status or "missing"), payload=None)

        payload = entry.get("payload") if isinstance(entry.get("payload"), dict) else None

        def _mutate(data: dict[str, Any]) -> dict[str, Any]:
            cur = data.get(run_key)
            if not isinstance(cur, dict):
                return data
            cur["status"] = "rejected"
            cur["updated_at"] = datetime.utcnow().isoformat()
            data[run_key] = cur
            return data

        self.store.update(_mutate)
        return ApprovalTransitionResult(status="rejected", payload=payload)


_backend: ApprovalStateBackend = FileApprovalStateBackend(Path(settings.pending_approval_file))


def set_pending(run_id: int, payload: dict[str, Any]) -> None:
    _backend.set_pending(run_id, payload)


def get_pending(run_id: int) -> dict[str, Any] | None:
    return _backend.get_pending(run_id)


def mark_approved(run_id: int, final_message_id: int | None = None) -> ApprovalTransitionResult:
    return _backend.mark_approved(run_id, final_message_id)


def mark_rejected(run_id: int) -> ApprovalTransitionResult:
    return _backend.mark_rejected(run_id)
