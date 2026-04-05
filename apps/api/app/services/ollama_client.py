from __future__ import annotations

from datetime import datetime
from typing import AsyncIterator

import httpx

from app.core.config import settings


class OllamaUnavailableError(RuntimeError):
    pass


class OllamaClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")

    async def _request(self, method: str, path: str, **kwargs):
        try:
            async with httpx.AsyncClient(timeout=kwargs.pop("timeout", 30.0)) as client:
                resp = await client.request(method, f"{self.base_url}{path}", **kwargs)
                resp.raise_for_status()
                return resp
        except httpx.HTTPError as exc:
            raise OllamaUnavailableError("Ollama 서버에 연결할 수 없거나 요청이 실패했습니다.") from exc

    async def health_check(self) -> bool:
        try:
            await self._request("GET", "/api/tags", timeout=2.0)
            return True
        except OllamaUnavailableError:
            return False

    async def list_models(self) -> list[dict]:
        resp = await self._request("GET", "/api/tags", timeout=5.0)
        return resp.json().get("models", [])

    async def pull_model(self, model_name: str) -> dict:
        resp = await self._request("POST", "/api/pull", json={"name": model_name, "stream": False}, timeout=90.0)
        return resp.json()

    async def delete_model(self, model_name: str) -> dict:
        await self._request("DELETE", "/api/delete", json={"name": model_name}, timeout=15.0)
        return {"deleted": model_name}

    async def chat(self, model_name: str, messages: list[dict], images: list[str] | None = None, options: dict | None = None) -> dict:
        body = {"model": model_name, "messages": messages, "stream": False}
        if images:
            body["images"] = images
        if options:
            body["options"] = options
        resp = await self._request("POST", "/api/chat", json=body, timeout=120.0)
        return resp.json()

    async def stream_chat(self, model_name: str, messages: list[dict]) -> AsyncIterator[str]:
        payload = {"model": model_name, "messages": messages, "stream": True}
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
                    resp.raise_for_status()
                    async for line in resp.aiter_lines():
                        if line:
                            yield line
        except httpx.HTTPError as exc:
            raise OllamaUnavailableError("Ollama 스트리밍 연결에 실패했습니다.") from exc

    async def embeddings(self, model_name: str, input_text: str) -> dict:
        resp = await self._request("POST", "/api/embeddings", json={"model": model_name, "prompt": input_text}, timeout=30.0)
        return resp.json()

    async def warm_model(self, model_name: str) -> dict:
        return {"model": model_name, "warmed_at": datetime.utcnow().isoformat()}

    async def unload_model(self, model_name: str) -> dict:
        return {"model": model_name, "unloaded": True}
