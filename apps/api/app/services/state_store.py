from __future__ import annotations

import json
import os
import tempfile
import threading
from pathlib import Path
from typing import Any


class AtomicJsonFileStore:
    """Thread-safe JSON file store backed by atomic replace writes.

    현재는 runtime_state(gpu toggle) persistence 용도로만 사용한다.
    """

    def __init__(self, file_path: Path, default_data: dict[str, Any] | None = None):
        self.file_path = file_path
        self.default_data = default_data or {}
        self._lock = threading.RLock()

    def load(self) -> dict[str, Any]:
        with self._lock:
            if not self.file_path.exists():
                return dict(self.default_data)
            try:
                return json.loads(self.file_path.read_text(encoding="utf-8"))
            except Exception:
                # corrupted/partial writes should never break runtime flows
                return dict(self.default_data)

    def save(self, data: dict[str, Any]) -> None:
        payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
        self._atomic_write(payload)

    def update(self, mutator):
        with self._lock:
            data = self.load()
            next_data = mutator(dict(data))
            self.save(next_data)
            return next_data

    def _atomic_write(self, payload: str) -> None:
        with self._lock:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp_name = tempfile.mkstemp(prefix=f".{self.file_path.name}.", suffix=".tmp", dir=str(self.file_path.parent))
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as tmp:
                    tmp.write(payload)
                    tmp.flush()
                    os.fsync(tmp.fileno())
                os.replace(tmp_name, self.file_path)
            finally:
                try:
                    if os.path.exists(tmp_name):
                        os.unlink(tmp_name)
                except OSError:
                    pass
