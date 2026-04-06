from __future__ import annotations

import json
from pathlib import Path

from app.core.config import settings

_FILE = Path(settings.pending_approval_file)


def _load() -> dict:
    if not _FILE.exists():
        return {}
    try:
        return json.loads(_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save(data: dict) -> None:
    _FILE.parent.mkdir(parents=True, exist_ok=True)
    _FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def set_pending(run_id: int, payload: dict) -> None:
    data = _load()
    data[str(run_id)] = payload
    _save(data)


def get_pending(run_id: int) -> dict | None:
    return _load().get(str(run_id))


def clear_pending(run_id: int) -> None:
    data = _load()
    if str(run_id) in data:
        del data[str(run_id)]
        _save(data)
