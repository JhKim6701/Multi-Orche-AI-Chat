from __future__ import annotations

from datetime import datetime

import httpx

from app.core.config import settings


class OllamaClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")

    async def health_check(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except Exception:
            return False

    async def list_models(self) -> list[dict]:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{self.base_url}/api/tags")
            resp.raise_for_status()
            payload = resp.json()
            return payload.get("models", [])

    async def pull_model(self, model_name: str) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{self.base_url}/api/pull", json={"name": model_name, "stream": False})
            resp.raise_for_status()
            return resp.json()

    async def delete_model(self, model_name: str) -> dict:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.delete(f"{self.base_url}/api/delete", json={"name": model_name})
            resp.raise_for_status()
            return {"deleted": model_name}

    async def chat(self, model_name: str, messages: list[dict], images: list[str] | None = None, options: dict | None = None) -> dict:
        body = {"model": model_name, "messages": messages, "stream": False}
        if images:
            body["images"] = images
        if options:
            body["options"] = options
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=body)
            resp.raise_for_status()
            return resp.json()

    async def embeddings(self, model_name: str, input_text: str) -> dict:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(f"{self.base_url}/api/embeddings", json={"model": model_name, "prompt": input_text})
            resp.raise_for_status()
            return resp.json()

    async def warm_model(self, model_name: str) -> dict:
        return {"model": model_name, "warmed_at": datetime.utcnow().isoformat()}

    async def unload_model(self, model_name: str) -> dict:
        return {"model": model_name, "unloaded": True}
