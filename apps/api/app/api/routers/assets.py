from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models import Asset
from app.schemas.asset import AssetOut
from app.utils.files import safe_join, sanitize_filename

router = APIRouter(prefix="/assets", tags=["assets"])


@router.post("/upload", response_model=AssetOut)
async def upload_asset(
    project_id: int = Form(...),
    chat_thread_id: int = Form(...),
    source_type: str = Form("user_upload"),
    message_id: int | None = Form(None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    content = await file.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail="file too large")

    root = Path(settings.upload_root)
    filename = sanitize_filename(file.filename or "upload.bin")
    upload_dir = safe_join(root, "projects", str(project_id), "chats", str(chat_thread_id), "uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    target = safe_join(upload_dir, filename)
    target.write_bytes(content)

    asset = Asset(
        project_id=project_id,
        chat_thread_id=chat_thread_id,
        message_id=message_id,
        source_type=source_type,
        asset_type=(file.content_type or "application/octet-stream").split("/")[0],
        mime_type=file.content_type or "application/octet-stream",
        original_filename=file.filename or filename,
        stored_path=str(target),
        derived_metadata_json={"size": len(content)},
    )
    db.add(asset)
    db.commit()
    db.refresh(asset)
    return asset


@router.get("/chat/{chat_id}", response_model=list[AssetOut])
def list_assets(chat_id: int, db: Session = Depends(get_db)):
    return db.scalars(select(Asset).where(Asset.chat_thread_id == chat_id).order_by(Asset.created_at.asc())).all()


@router.get("/{asset_id}", response_model=AssetOut)
def get_asset(asset_id: int, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="asset not found")
    return asset


@router.get("/{asset_id}/download")
def download_asset(asset_id: int, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="asset not found")
    return FileResponse(asset.stored_path, filename=asset.original_filename, media_type=asset.mime_type)
