from __future__ import annotations

import hashlib
from typing import Any

import httpx

from app.core.config import settings


class EmbeddingProvider:
    """Ollama-first embedding provider with deterministic local fallback."""

    def __init__(self, model_name: str | None = None, base_url: str | None = None) -> None:
        self.model_name = model_name or settings.ollama_embedding_model
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")

    def _fallback_embedding(self, text: str, dims: int = 384) -> list[float]:
        seed = hashlib.sha256(text.encode("utf-8", errors="ignore")).digest()
        vec: list[float] = []
        while len(vec) < dims:
            seed = hashlib.sha256(seed).digest()
            vec.extend([(byte / 127.5) - 1 for byte in seed])
        return vec[:dims]

    def embed_text(self, text: str) -> tuple[list[float], dict[str, Any]]:
        clean = text.strip()
        if not clean:
            return self._fallback_embedding(""), {"mode": "fallback", "reason": "empty_text"}

        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.post(
                    f"{self.base_url}/api/embeddings",
                    json={"model": self.model_name, "prompt": clean},
                )
                resp.raise_for_status()
                payload = resp.json()
                emb = payload.get("embedding") or []
                if isinstance(emb, list) and emb:
                    return [float(v) for v in emb], {"mode": "ollama", "model": self.model_name}
        except Exception as exc:  # graceful fallback
            return self._fallback_embedding(clean), {"mode": "fallback", "reason": str(exc)}

        return self._fallback_embedding(clean), {"mode": "fallback", "reason": "missing_embedding_in_response"}
