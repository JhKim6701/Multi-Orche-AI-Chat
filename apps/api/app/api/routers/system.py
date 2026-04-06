from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import settings
from app.db.session import SessionLocal
from app.services.ollama_client import OllamaClient
from app.services.qdrant_store import QdrantStore
from app.services.runtime_state import get_gpu_enabled, set_gpu_enabled
from app.services.system_metrics import get_hardware_metrics

router = APIRouter(prefix="/system", tags=["system"])


def _check_db() -> tuple[bool, str]:
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


def _check_upload_root() -> tuple[bool, str]:
    try:
        root = Path(settings.upload_root)
        root.mkdir(parents=True, exist_ok=True)
        probe = root / ".write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True, "ok"
    except Exception as exc:
        return False, str(exc)


@router.get("/health")
async def health():
    ollama = await OllamaClient().health_check()
    db_ok, db_msg = _check_db()
    upload_ok, upload_msg = _check_upload_root()
    qdrant_ok = QdrantStore().health()

    checks = {
        "database": {"ok": db_ok, "detail": db_msg},
        "ollama": {"ok": ollama},
        "qdrant": {"ok": qdrant_ok},
        "upload_root": {"ok": upload_ok, "path": settings.upload_root, "detail": upload_msg},
    }
    overall = all(v.get("ok") for v in checks.values())
    return {
        "status": "ok" if overall else "degraded",
        "app": settings.app_name,
        "env": settings.env,
        "mode": "desktop" if settings.env == "desktop" else "web",
        "data_root": settings.data_root,
        "upload_root": settings.upload_root,
        "database_url": settings.database_url,
        "ollama_base_url": settings.ollama_base_url,
        "qdrant_url": settings.qdrant_url,
        "checks": checks,
    }


@router.get("/readiness")
async def readiness():
    report = await health()
    return {"ready": report["status"] == "ok", "checks": report["checks"], "env": report["env"]}


@router.get("/runtime-info")
def runtime_info():
    return {
        "env": settings.env,
        "mode": "desktop" if settings.env == "desktop" else "web",
        "data_root": settings.data_root,
        "upload_root": settings.upload_root,
        "database_url": settings.database_url,
        "qdrant_url": settings.qdrant_url,
        "ollama_base_url": settings.ollama_base_url,
        "gpu_enabled": get_gpu_enabled(),
    }


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
    return {"connected": await client.health_check(), "base_url": settings.ollama_base_url}
