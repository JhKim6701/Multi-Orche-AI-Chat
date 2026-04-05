from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import ModelRegistry
from app.schemas.model import ModelRegistryOut, ModelSortUpdate, ModelToggle
from app.services.ollama_client import OllamaClient

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=list[ModelRegistryOut])
def list_registry(db: Session = Depends(get_db)):
    return db.scalars(select(ModelRegistry).order_by(ModelRegistry.sort_order.asc(), ModelRegistry.model_name.asc())).all()


@router.post("/sync", response_model=list[ModelRegistryOut])
async def sync_registry(db: Session = Depends(get_db)):
    client = OllamaClient()
    if not await client.health_check():
        raise HTTPException(status_code=503, detail="ollama unavailable")
    remote = await client.list_models()
    known = {m.model_name: m for m in db.scalars(select(ModelRegistry)).all()}
    for item in remote:
        name = item["name"]
        model = known.get(name)
        if not model:
            model = ModelRegistry(model_name=name, downloaded=True, last_seen_at=datetime.utcnow())
            db.add(model)
        else:
            model.downloaded = True
            model.last_seen_at = datetime.utcnow()
    db.commit()
    return db.scalars(select(ModelRegistry).order_by(ModelRegistry.sort_order.asc())).all()


@router.post("/{model_name}/pull")
async def pull_model(model_name: str, db: Session = Depends(get_db)):
    client = OllamaClient()
    await client.pull_model(model_name)
    model = db.scalar(select(ModelRegistry).where(ModelRegistry.model_name == model_name))
    if not model:
        model = ModelRegistry(model_name=model_name, downloaded=True)
        db.add(model)
    model.downloaded = True
    model.last_seen_at = datetime.utcnow()
    db.commit()
    return {"ok": True}


@router.delete("/{model_name}")
async def delete_model(model_name: str, db: Session = Depends(get_db)):
    client = OllamaClient()
    await client.delete_model(model_name)
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
