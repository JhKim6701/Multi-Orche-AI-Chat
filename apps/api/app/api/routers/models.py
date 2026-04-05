from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ModelRegistry
from app.schemas.model import ModelRegistryOut, ModelSortUpdate, ModelToggle
from app.services.ollama_client import OllamaClient, OllamaUnavailableError

router = APIRouter(prefix="/models", tags=["models"])


class PullRequest(BaseModel):
    model_name: str


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
        model = known.get(name)
        if not model:
            model = ModelRegistry(model_name=name, downloaded=True, last_seen_at=datetime.utcnow())
            db.add(model)
        else:
            model.downloaded = True
            model.last_seen_at = datetime.utcnow()

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

    model = db.scalar(select(ModelRegistry).where(ModelRegistry.model_name == payload.model_name))
    if not model:
        model = ModelRegistry(model_name=payload.model_name, downloaded=True)
        db.add(model)
    model.downloaded = True
    model.last_seen_at = datetime.utcnow()
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
