from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.models import Asset, AssetChunk, Message
from app.schemas.asset import AssetOut
from app.services.asset_ingestion import ingest_asset, pack_retrieval_context, retrieve_relevant_context
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
    db.flush()
    try:
        ingest_asset(db, asset)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"asset ingest failed: {exc}. upload/data root 또는 qdrant/embedding 의존성을 확인하세요.",
        ) from exc
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


@router.get("/{asset_id}/ingestion-status")
def get_ingestion_status(asset_id: int, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="asset not found")
    return {
        "asset_id": asset.id,
        "filename": asset.original_filename,
        "mime_type": asset.mime_type,
        "ingestion": (asset.derived_metadata_json or {}),
    }


@router.get("/{asset_id}/chunks")
def list_asset_chunks(asset_id: int, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="asset not found")
    rows = (
        db.query(AssetChunk)
        .filter(AssetChunk.asset_id == asset_id)
        .order_by(AssetChunk.chunk_index.asc())
        .all()
    )
    return [
        {
            "id": row.id,
            "asset_id": row.asset_id,
            "chunk_index": row.chunk_index,
            "segment_id": row.segment_id,
            "char_count": row.char_count,
            "token_count": row.token_count,
            "vector_id": row.vector_id,
            "metadata": row.chunk_metadata_json or {},
            "snippet": row.content_text[:280],
        }
        for row in rows
    ]


@router.get("/chat/{chat_id}/retrieval-preview")
def retrieval_preview(chat_id: int, query: str, segment_id: int | None = None, limit: int = 8, db: Session = Depends(get_db)):
    project_id = db.scalar(select(Message.project_id).where(Message.chat_thread_id == chat_id).limit(1))
    hits = retrieve_relevant_context(
        db=db,
        chat_thread_id=chat_id,
        project_id=project_id,
        segment_id=segment_id,
        query=query,
        limit=min(max(limit, 1), 20),
    )
    packed_context, packed_meta = pack_retrieval_context(hits)
    return {
        "query": query,
        "scope": {
            "project_id": project_id,
            "chat_thread_id": chat_id,
            "segment_id": segment_id,
            "limit": min(max(limit, 1), 20),
        },
        "hits": hits,
        "packed_context": packed_context,
        "packed_meta": packed_meta,
    }


@router.get("/{asset_id}/download")
def download_asset(asset_id: int, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="asset not found")
    return FileResponse(asset.stored_path, filename=asset.original_filename, media_type=asset.mime_type)
