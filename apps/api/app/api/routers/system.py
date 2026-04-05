from fastapi import APIRouter

from app.core.config import settings
from app.services.ollama_client import OllamaClient
from app.services.system_metrics import get_hardware_metrics

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/health")
async def health():
    return {"status": "ok", "app": settings.app_name}


@router.get("/hardware")
def hardware_metrics():
    return get_hardware_metrics()


@router.get("/ollama")
async def ollama_connectivity():
    client = OllamaClient()
    return {"connected": await client.health_check()}
