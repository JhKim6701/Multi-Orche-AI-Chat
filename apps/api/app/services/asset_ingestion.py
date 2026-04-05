from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.models import Asset, AssetChunk

SUPPORTED_TEXT_MIME_PREFIX = (
    "text/",
    "application/json",
    "application/csv",
    "application/pdf",
)


def _extract_text(asset: Asset) -> tuple[str, str]:
    path = Path(asset.stored_path)
    mime = asset.mime_type

    try:
        if mime.startswith("text/") or path.suffix.lower() in {".txt", ".md", ".py", ".log"}:
            return path.read_text(encoding="utf-8", errors="ignore"), "text_extracted"

        if mime in {"application/json"} or path.suffix.lower() == ".json":
            payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
            return json.dumps(payload, ensure_ascii=False, indent=2), "json_extracted"

        if "csv" in mime or path.suffix.lower() == ".csv":
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                reader = csv.reader(f)
                rows = list(reader)
            lines = [", ".join(r) for r in rows[:200]]
            return "\n".join(lines), "csv_extracted"

        if "pdf" in mime or path.suffix.lower() == ".pdf":
            try:
                from pypdf import PdfReader  # type: ignore

                reader = PdfReader(str(path))
                text = "\n".join((p.extract_text() or "") for p in reader.pages)
                if text.strip():
                    return text, "pdf_extracted"
                return "", "pdf_no_text"
            except Exception:
                raw = path.read_bytes()[:4000]
                return raw.decode("utf-8", errors="ignore"), "pdf_fallback_decoded"

    except Exception:
        return "", "extraction_failed"

    return "", "unsupported"


def _chunk_text(text: str, chunk_size: int = 500, overlap: int = 80) -> list[str]:
    cleaned = " ".join(text.split())
    if not cleaned:
        return []
    chunks: list[str] = []
    i = 0
    while i < len(cleaned):
        chunks.append(cleaned[i : i + chunk_size])
        i += max(1, chunk_size - overlap)
    return chunks[:40]


def ingest_asset(db: Session, asset: Asset) -> dict:
    text, status = _extract_text(asset)
    chunks = _chunk_text(text)

    db.execute(delete(AssetChunk).where(AssetChunk.asset_id == asset.id))
    for idx, chunk in enumerate(chunks):
        db.add(
            AssetChunk(
                asset_id=asset.id,
                project_id=asset.project_id,
                chat_thread_id=asset.chat_thread_id,
                chunk_index=idx,
                content_text=chunk,
            )
        )

    meta = asset.derived_metadata_json or {}
    meta.update(
        {
            "ingest_status": status,
            "text_length": len(text),
            "chunk_count": len(chunks),
            "preview": text[:240],
        }
    )
    asset.derived_metadata_json = meta
    db.flush()
    return meta


def retrieve_relevant_context(db: Session, chat_thread_id: int, query: str, limit: int = 6) -> list[dict]:
    tokens = [t.lower() for t in query.split() if len(t) > 2][:12]
    if not tokens:
        tokens = [query.lower()[:20]]

    chunks = db.query(AssetChunk, Asset).join(Asset, Asset.id == AssetChunk.asset_id).filter(AssetChunk.chat_thread_id == chat_thread_id).all()
    scored: list[tuple[int, AssetChunk, Asset]] = []
    for chunk, asset in chunks:
        text = chunk.content_text.lower()
        score = sum(2 for t in tokens if t in text)
        if score == 0 and query.lower()[:30] in text:
            score = 1
        if score > 0:
            scored.append((score, chunk, asset))

    scored.sort(key=lambda x: x[0], reverse=True)
    selected = scored[:limit]
    return [
        {
            "asset_id": asset.id,
            "filename": asset.original_filename,
            "chunk_index": chunk.chunk_index,
            "snippet": chunk.content_text[:220],
            "mime_type": asset.mime_type,
        }
        for _, chunk, asset in selected
    ]
