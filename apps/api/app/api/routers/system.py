from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

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


def _mask_path(path: str, reveal: bool) -> str:
    if reveal:
        return path
    p = Path(path)
    return f".../{p.name}" if p.name else "..."


def _mask_url(raw: str, reveal: bool) -> str:
    if reveal:
        return raw
    parts = urlsplit(raw)
    host = parts.hostname or "unknown"
    scheme = parts.scheme or ""
    port = f":{parts.port}" if parts.port else ""
    path_tail = parts.path.rsplit("/", 1)[-1] if parts.path else ""
    suffix = f"/{path_tail}" if path_tail else ""
    if parts.username:
        return f"{scheme}://***@{host}{port}{suffix}"
    return f"{scheme}://{host}{port}{suffix}" if scheme else raw


def _allow_sensitive(verbose: bool) -> bool:
    return settings.env == "dev" and verbose


def _runtime_surface(verbose: bool) -> dict:
    reveal = _allow_sensitive(verbose)
    return {
        "env": settings.env,
        "mode": "desktop" if settings.env == "desktop" else "web",
        "gpu_enabled": get_gpu_enabled(),
        "data_root": _mask_path(settings.data_root, reveal),
        "upload_root": _mask_path(settings.upload_root, reveal),
        "database_url": _mask_url(settings.database_url, reveal),
        "qdrant_url": _mask_url(settings.qdrant_url, reveal),
        "ollama_base_url": _mask_url(settings.ollama_base_url, reveal),
        "sensitive_details_included": reveal,
    }


@router.get("/health")
async def health(client_mode: str | None = None, verbose: bool = False):
    ollama = await OllamaClient().health_check()
    db_ok, db_msg = _check_db()
    upload_ok, upload_msg = _check_upload_root()
    qdrant_ok = QdrantStore().health()
    runtime = _runtime_surface(verbose=verbose)

    checks = {
        "database": {"ok": db_ok, "detail": db_msg if runtime["sensitive_details_included"] else ("ok" if db_ok else "error")},
        "ollama": {"ok": ollama},
        "qdrant": {"ok": qdrant_ok},
        "upload_root": {
            "ok": upload_ok,
            "path": runtime["upload_root"],
            "detail": upload_msg if runtime["sensitive_details_included"] else ("ok" if upload_ok else "error"),
        },
    }
    overall = all(v.get("ok") for v in checks.values())
    unresolved = [name for name, info in checks.items() if not info.get("ok")]
    mode_mismatch = bool(client_mode and client_mode != runtime["mode"])
    return {
        "status": "ok" if overall else "degraded",
        "app": settings.app_name,
        **runtime,
        "checks": checks,
        "unresolved_dependencies": unresolved,
        "mode_mismatch": mode_mismatch,
        "doctor_hint": "npm run doctor로 health/readiness를 점검하세요.",
    }


@router.get("/readiness")
async def readiness(verbose: bool = False):
    report = await health(verbose=verbose)
    return {
        "ready": report["status"] == "ok",
        "checks": report["checks"],
        "env": report["env"],
        "unresolved_dependencies": report["unresolved_dependencies"],
        "doctor_hint": report["doctor_hint"],
        "sensitive_details_included": report["sensitive_details_included"],
    }


@router.get("/runtime-info")
def runtime_info(verbose: bool = False):
    return _runtime_surface(verbose=verbose)


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
async def ollama_connectivity(verbose: bool = False):
    client = OllamaClient()
    runtime = _runtime_surface(verbose=verbose)
    return {"connected": await client.health_check(), "base_url": runtime["ollama_base_url"], "sensitive_details_included": runtime["sensitive_details_included"]}
