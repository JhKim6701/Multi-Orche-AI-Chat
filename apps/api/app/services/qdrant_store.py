from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings


class QdrantStore:
    def __init__(self, base_url: str | None = None, collection: str | None = None) -> None:
        self.base_url = (base_url or settings.qdrant_url).rstrip("/")
        self.collection = collection or settings.qdrant_collection

    def _collection_url(self) -> str:
        return f"{self.base_url}/collections/{self.collection}"

    def ensure_collection(self, vector_size: int) -> dict[str, Any]:
        with httpx.Client(timeout=10.0) as client:
            get_resp = client.get(self._collection_url())
            if get_resp.status_code == 200:
                return {"ok": True, "existing": True}
            resp = client.put(
                self._collection_url(),
                json={
                    "vectors": {"size": vector_size, "distance": "Cosine"},
                    "on_disk_payload": True,
                },
            )
            resp.raise_for_status()
            return {"ok": True, "existing": False}

    def upsert_points(self, points: list[dict[str, Any]]) -> dict[str, Any]:
        if not points:
            return {"ok": True, "count": 0}
        with httpx.Client(timeout=15.0) as client:
            resp = client.put(f"{self._collection_url()}/points", json={"points": points, "wait": True})
            resp.raise_for_status()
            return {"ok": True, "count": len(points)}

    def search(self, vector: list[float], limit: int, filter_payload: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        with httpx.Client(timeout=15.0) as client:
            body: dict[str, Any] = {"vector": vector, "limit": limit, "with_payload": True}
            if filter_payload:
                body["filter"] = filter_payload
            resp = client.post(f"{self._collection_url()}/points/search", json=body)
            resp.raise_for_status()
            return resp.json().get("result", [])
