from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ModelRegistry
from app.schemas.model import (
    ModelRegistryOut,
    ModelSortUpdate,
    ModelToggle,
    RoleCandidateOut,
    RolePreferenceOut,
    RolePreferenceUpdate,
)
from app.services.ollama_client import OllamaClient, OllamaUnavailableError

router = APIRouter(prefix="/models", tags=["models"])
VALID_ROLES = {"planner", "context_resolver", "specialist", "model_router", "final_responder", "reviewer", "critic", "orchestrator"}


class PullRequest(BaseModel):
    model_name: str


def detect_capabilities(model_name: str) -> dict:
    n = model_name.lower()
    return {
        "supports_vision": any(x in n for x in ["vision", "llava", "qwen2.5-vl", "bakllava", "moondream"]),
        "supports_reasoning": any(x in n for x in ["reason", "r1", "qwq", "deepseek", "o1"]),
        "supports_embeddings": any(x in n for x in ["embed", "nomic-embed", "bge", "e5"]),
        "supports_tools": any(x in n for x in ["tool", "function"]),
    }


def _validate_role(role: str) -> str:
    normalized = role.strip().lower()
    if normalized not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"invalid role: {role}")
    return normalized


def _role_priority(model: ModelRegistry, role: str) -> int:
    metadata = model.metadata_json if isinstance(model.metadata_json, dict) else {}
    priority_map = metadata.get("role_priority", {})
    if isinstance(priority_map, dict):
        raw = priority_map.get(role)
        if isinstance(raw, int):
            return raw
    return 10_000 + (model.sort_order or 0)


def _role_preferred_models(db: Session, role: str, *, enabled_only: bool = False) -> list[ModelRegistry]:
    q = select(ModelRegistry).where(ModelRegistry.downloaded.is_(True))
    if enabled_only:
        q = q.where(ModelRegistry.enabled.is_(True))
    rows = db.scalars(q).all()
    preferred = []
    for row in rows:
        roles = row.preferred_roles_json if isinstance(row.preferred_roles_json, list) else []
        if role in roles:
            preferred.append(row)
    preferred.sort(key=lambda m: (_role_priority(m, role), m.sort_order, m.model_name))
    return preferred


def _role_capability_score(model: ModelRegistry, role: str) -> int:
    score = 0
    if role in {"orchestrator", "model_router", "reviewer", "critic", "final_responder", "planner"} and model.supports_reasoning:
        score += 3
    if role in {"specialist", "final_responder"} and model.supports_vision:
        score += 2
    if role == "context_resolver" and model.supports_embeddings:
        score += 3
    if model.enabled:
        score += 1
    if model.downloaded:
        score += 1
    return score


@router.get("", response_model=list[ModelRegistryOut])
def list_registry(db: Session = Depends(get_db)):
    return db.scalars(select(ModelRegistry).order_by(ModelRegistry.sort_order.asc(), ModelRegistry.model_name.asc())).all()


@router.get("/enabled", response_model=list[ModelRegistryOut])
def list_enabled(db: Session = Depends(get_db)):
    return db.scalars(
        select(ModelRegistry).where(ModelRegistry.enabled.is_(True), ModelRegistry.downloaded.is_(True)).order_by(ModelRegistry.sort_order.asc())
    ).all()


@router.post("/sync", response_model=list[ModelRegistryOut])
async def sync_registry(db: Session = Depends(get_db)):
    client = OllamaClient()
    try:
        remote = await client.list_models()
    except OllamaUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    known = {m.model_name: m for m in db.scalars(select(ModelRegistry)).all()}
    seen: set[str] = set()
    for item in remote:
        name = item["name"]
        seen.add(name)
        caps = detect_capabilities(name)
        model = known.get(name)
        if not model:
            model = ModelRegistry(model_name=name, downloaded=True, last_seen_at=datetime.utcnow(), **caps)
            db.add(model)
        else:
            model.downloaded = True
            model.last_seen_at = datetime.utcnow()
            model.supports_vision = caps["supports_vision"]
            model.supports_reasoning = caps["supports_reasoning"]
            model.supports_embeddings = caps["supports_embeddings"]
            model.supports_tools = caps["supports_tools"]

    for model in known.values():
        if model.model_name not in seen:
            model.downloaded = False

    db.commit()
    return db.scalars(select(ModelRegistry).order_by(ModelRegistry.sort_order.asc(), ModelRegistry.model_name.asc())).all()


@router.post("/pull")
async def pull_model(payload: PullRequest, db: Session = Depends(get_db)):
    client = OllamaClient()
    try:
        await client.pull_model(payload.model_name)
    except OllamaUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    caps = detect_capabilities(payload.model_name)
    model = db.scalar(select(ModelRegistry).where(ModelRegistry.model_name == payload.model_name))
    if not model:
        model = ModelRegistry(model_name=payload.model_name, downloaded=True, **caps)
        db.add(model)
    model.downloaded = True
    model.last_seen_at = datetime.utcnow()
    model.supports_vision = caps["supports_vision"]
    model.supports_reasoning = caps["supports_reasoning"]
    model.supports_embeddings = caps["supports_embeddings"]
    model.supports_tools = caps["supports_tools"]
    db.commit()
    return {"ok": True}


@router.delete("/{model_name}")
async def delete_model(model_name: str, db: Session = Depends(get_db)):
    client = OllamaClient()
    try:
        await client.delete_model(model_name)
    except OllamaUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    model = db.scalar(select(ModelRegistry).where(ModelRegistry.model_name == model_name))
    if model:
        model.downloaded = False
        db.commit()
    return {"ok": True}


@router.patch("/{model_id}/toggle", response_model=ModelRegistryOut)
def toggle_model(model_id: int, payload: ModelToggle, db: Session = Depends(get_db)):
    model = db.get(ModelRegistry, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="model not found")
    model.enabled = payload.enabled
    db.commit()
    db.refresh(model)
    return model


@router.patch("/{model_id}/sort", response_model=ModelRegistryOut)
def update_sort_order(model_id: int, payload: ModelSortUpdate, db: Session = Depends(get_db)):
    model = db.get(ModelRegistry, model_id)
    if not model:
        raise HTTPException(status_code=404, detail="model not found")
    model.sort_order = payload.sort_order
    db.commit()
    db.refresh(model)
    return model


@router.get("/role-preferences", response_model=list[RolePreferenceOut])
def list_role_preferences(db: Session = Depends(get_db)):
    payload: list[RolePreferenceOut] = []
    for role in sorted(VALID_ROLES):
        preferred = _role_preferred_models(db, role, enabled_only=False)
        names = [m.model_name for m in preferred]
        payload.append(
            RolePreferenceOut(
                role=role,
                preferred_model_names=names,
                default_model_name=(names[0] if names else None),
                fallback_model_names=(names[1:] if len(names) > 1 else []),
            )
        )
    return payload


@router.put("/role-preferences/{role}", response_model=RolePreferenceOut)
def update_role_preferences(role: str, payload: RolePreferenceUpdate, db: Session = Depends(get_db)):
    normalized_role = _validate_role(role)
    unique_names = []
    seen = set()
    for name in payload.preferred_model_names:
        cleaned = name.strip()
        if cleaned and cleaned not in seen:
            unique_names.append(cleaned)
            seen.add(cleaned)

    known = {m.model_name: m for m in db.scalars(select(ModelRegistry)).all()}
    for model_name in unique_names:
        if model_name not in known:
            raise HTTPException(status_code=404, detail=f"model not found: {model_name}")

    for model in known.values():
        roles = [r for r in (model.preferred_roles_json or []) if isinstance(r, str)]
        if model.model_name in unique_names and normalized_role not in roles:
            roles.append(normalized_role)
        if model.model_name not in unique_names and normalized_role in roles:
            roles.remove(normalized_role)
        model.preferred_roles_json = sorted(set(roles)) if roles else None
        metadata = model.metadata_json if isinstance(model.metadata_json, dict) else {}
        priority_map = metadata.get("role_priority")
        if not isinstance(priority_map, dict):
            priority_map = {}
        if model.model_name in unique_names:
            priority_map[normalized_role] = unique_names.index(model.model_name)
        else:
            priority_map.pop(normalized_role, None)
        metadata["role_priority"] = priority_map
        model.metadata_json = metadata

    db.commit()
    preferred = _role_preferred_models(db, normalized_role, enabled_only=False)
    names = [m.model_name for m in preferred]
    return RolePreferenceOut(
        role=normalized_role,
        preferred_model_names=names,
        default_model_name=(names[0] if names else None),
        fallback_model_names=(names[1:] if len(names) > 1 else []),
    )


@router.get("/role-candidates/{role}", response_model=list[RoleCandidateOut])
def list_role_candidates(role: str, enabled_only: bool = True, db: Session = Depends(get_db)):
    normalized_role = _validate_role(role)
    q = select(ModelRegistry)
    if enabled_only:
        q = q.where(ModelRegistry.enabled.is_(True))
    rows = db.scalars(q).all()
    preferred_names = [m.model_name for m in _role_preferred_models(db, normalized_role, enabled_only=False)]
    default_name = preferred_names[0] if preferred_names else None
    fallback_names = set(preferred_names[1:])

    rows.sort(
        key=lambda row: (
            -(1 if row.model_name in preferred_names else 0),
            -_role_capability_score(row, normalized_role),
            _role_priority(row, normalized_role),
            row.sort_order,
            row.model_name,
        )
    )
    return [
        RoleCandidateOut(
            model_name=row.model_name,
            downloaded=row.downloaded,
            enabled=row.enabled,
            priority=_role_priority(row, normalized_role),
            capability_score=_role_capability_score(row, normalized_role),
            is_preferred=row.model_name in preferred_names,
            is_default=row.model_name == default_name,
            is_fallback=row.model_name in fallback_names,
            supports_vision=row.supports_vision,
            supports_reasoning=row.supports_reasoning,
            supports_embeddings=row.supports_embeddings,
        )
        for row in rows
    ]
