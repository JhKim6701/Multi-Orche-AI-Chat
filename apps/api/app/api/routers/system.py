from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
from app.services.ollama_client import OllamaClient
from app.services.runtime_state import get_gpu_enabled, set_gpu_enabled
from app.services.system_metrics import get_hardware_metrics

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name}


@router.get("/hardware")
def hardware_metrics():
    return get_hardware_metrics()


class GpuToggleRequest(BaseModel):
    enabled: bool


@router.get("/gpu-state")
def gpu_state():
    return {"gpu_enabled": get_gpu_enabled()}


@router.post("/gpu-state")
def set_gpu_state(payload: GpuToggleRequest):
    enabled = set_gpu_enabled(payload.enabled)
    return {"gpu_enabled": enabled}


@router.get("/ollama")
async def ollama_connectivity():
    client = OllamaClient()
    return {"connected": await client.health_check()}
