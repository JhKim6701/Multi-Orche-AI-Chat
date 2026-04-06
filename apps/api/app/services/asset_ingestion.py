from __future__ import annotations

import csv
import io
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Asset, AssetChunk, ConversationSegment, Message
from app.services.embedding_provider import EmbeddingProvider
from app.services.qdrant_store import QdrantStore


@dataclass
class ExtractedPart:
    text: str
    page: int | None = None


def _safe_token_count(text: str) -> int:
    return max(1, len(text.split())) if text else 0


def _extract_from_pdf(path: Path) -> tuple[list[ExtractedPart], str, bool, str | None]:
    try:
        from pypdf import PdfReader  # type: ignore

        reader = PdfReader(str(path))
        parts: list[ExtractedPart] = []
        for i, page in enumerate(reader.pages):
            txt = (page.extract_text() or "").strip()
            if txt:
                parts.append(ExtractedPart(text=txt, page=i + 1))
        if parts:
            return parts, "pdf_extracted", False, None
        ocr_text, ocr_status = _try_ocr(path, mime="application/pdf")
        if ocr_text:
            return [ExtractedPart(text=ocr_text, page=1)], "pdf_ocr_extracted", True, ocr_status
        return [], "pdf_no_text", False, ocr_status
    except Exception as exc:
        return [], "pdf_extract_failed", False, str(exc)


def _try_ocr(path: Path, mime: str) -> tuple[str, str]:
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore

        if mime.startswith("image/"):
            text = pytesseract.image_to_string(Image.open(path)).strip()
            return text, "ocr_image_success" if text else "ocr_image_empty"
    except Exception as exc:
        return "", f"ocr_unavailable:{exc}"

    return "", "ocr_unsupported"


def _extract_parts(asset: Asset) -> tuple[list[ExtractedPart], dict[str, Any]]:
    path = Path(asset.stored_path)
    mime = (asset.mime_type or "").lower()
    suffix = path.suffix.lower()
    meta: dict[str, Any] = {"mime": mime, "suffix": suffix, "ocr_fallback_used": False}

    try:
        if mime.startswith("text/") or suffix in {".txt", ".md", ".log"}:
            text = path.read_text(encoding="utf-8", errors="ignore")
            meta["extract_status"] = "text_extracted"
            return [ExtractedPart(text=text, page=None)], meta

        if mime == "application/json" or suffix == ".json":
            payload = json.loads(path.read_text(encoding="utf-8", errors="ignore"))
            meta["extract_status"] = "json_extracted"
            return [ExtractedPart(text=json.dumps(payload, ensure_ascii=False, indent=2), page=None)], meta

        if "csv" in mime or suffix == ".csv":
            with path.open("r", encoding="utf-8", errors="ignore") as f:
                rows = list(csv.reader(f))
            meta["extract_status"] = "csv_extracted"
            return [ExtractedPart(text="\n".join([", ".join(r) for r in rows]), page=None)], meta

        if "pdf" in mime or suffix == ".pdf":
            parts, status, ocr_used, ocr_status = _extract_from_pdf(path)
            meta["extract_status"] = status
            meta["ocr_fallback_used"] = ocr_used
            meta["ocr_status"] = ocr_status
            return parts, meta

        if suffix == ".docx" or "word" in mime:
            try:
                from docx import Document  # type: ignore

                doc = Document(str(path))
                text = "\n".join(p.text for p in doc.paragraphs)
                meta["extract_status"] = "docx_extracted"
                return [ExtractedPart(text=text, page=None)], meta
            except Exception as exc:
                meta["extract_status"] = "docx_extract_failed"
                meta["error"] = str(exc)
                return [], meta

        if mime.startswith("image/"):
            ocr_text, ocr_status = _try_ocr(path, mime=mime)
            meta["extract_status"] = "image_ocr_extracted" if ocr_text else "image_no_text"
            meta["ocr_fallback_used"] = True
            meta["ocr_status"] = ocr_status
            return ([ExtractedPart(text=ocr_text, page=1)] if ocr_text else []), meta
    except Exception as exc:
        meta["extract_status"] = "extraction_failed"
        meta["error"] = str(exc)
        return [], meta

    meta["extract_status"] = "unsupported"
    return [], meta


def _chunk_parts(parts: list[ExtractedPart], chunk_size: int, overlap: int) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for part in parts:
        text = " ".join(part.text.split())
        if not text:
            continue
        cursor = 0
        local_idx = 0
        while cursor < len(text):
            body = text[cursor : cursor + chunk_size]
            if body.strip():
                chunks.append({"text": body, "page": part.page, "local_index": local_idx})
                local_idx += 1
            cursor += max(1, chunk_size - overlap)
    return chunks[:200]


def ingest_asset(db: Session, asset: Asset) -> dict:
    parts, extract_meta = _extract_parts(asset)
    chunks = _chunk_parts(parts, chunk_size=settings.rag_chunk_size, overlap=settings.rag_chunk_overlap)

    provider = EmbeddingProvider()
    qdrant = QdrantStore()

    db.execute(delete(AssetChunk).where(AssetChunk.asset_id == asset.id))

    indexing_errors: list[str] = []
    points: list[dict[str, Any]] = []
    created: list[AssetChunk] = []
    embedding_mode = "none"

    asset_segment_id = None
    if asset.message_id:
        asset_segment_id = db.scalar(select(Message.segment_id).where(Message.id == asset.message_id))

    for idx, chunk in enumerate(chunks):
        vector, emb_meta = provider.embed_text(chunk["text"])
        embedding_mode = emb_meta.get("mode", embedding_mode)
        vector_id = str(uuid.uuid4())
        chunk_row = AssetChunk(
            asset_id=asset.id,
            project_id=asset.project_id,
            chat_thread_id=asset.chat_thread_id,
            segment_id=asset_segment_id,
            chunk_index=idx,
            content_text=chunk["text"],
            char_count=len(chunk["text"]),
            token_count=_safe_token_count(chunk["text"]),
            vector_id=vector_id,
            embedding_model=settings.ollama_embedding_model,
            embedding_vector_json=vector,
            chunk_metadata_json={
                "page": chunk.get("page"),
                "filename": asset.original_filename,
                "mime_type": asset.mime_type,
                "embedding": emb_meta,
                "local_index": chunk.get("local_index"),
            },
        )
        db.add(chunk_row)
        db.flush()
        created.append(chunk_row)
        points.append(
            {
                "id": vector_id,
                "vector": vector,
                "payload": {
                    "chunk_id": chunk_row.id,
                    "project_id": asset.project_id,
                    "chat_thread_id": asset.chat_thread_id,
                    "asset_id": asset.id,
                    "segment_id": chunk_row.segment_id,
                    "chunk_index": idx,
                    "page": chunk.get("page"),
                    "filename": asset.original_filename,
                    "mime_type": asset.mime_type,
                },
            }
        )

    indexed_count = 0
    if points:
        try:
            qdrant.ensure_collection(vector_size=len(points[0]["vector"]))
            qdrant.upsert_points(points)
            indexed_count = len(points)
        except Exception as exc:
            indexing_errors.append(str(exc))

    meta = asset.derived_metadata_json or {}
    ingest_state = {
        "uploaded": True,
        "extracted": bool(parts),
        "chunked": bool(chunks),
        "embedded": bool(created),
        "indexed": indexed_count == len(points) if points else False,
    }
    ingest_state["failed"] = not ingest_state["chunked"]

    meta.update(
        {
            "ingest_status": extract_meta.get("extract_status", "unknown"),
            "ingest_pipeline": ingest_state,
            "chunk_count": len(chunks),
            "embedded_chunk_count": len(created),
            "indexed_chunk_count": indexed_count,
            "embedding_model": settings.ollama_embedding_model,
            "embedding_mode": embedding_mode,
            "ocr_fallback_used": bool(extract_meta.get("ocr_fallback_used")),
            "ocr_status": extract_meta.get("ocr_status"),
            "preview": (parts[0].text[:240] if parts else ""),
            "text_length": sum(len(p.text) for p in parts),
            "index_errors": indexing_errors,
            "mime_class": asset.mime_type.split("/")[0] if asset.mime_type else "unknown",
        }
    )
    if extract_meta.get("error"):
        meta["extract_error"] = extract_meta["error"]

    asset.derived_metadata_json = meta
    db.flush()
    return meta


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    size = min(len(a), len(b))
    dot = sum(a[i] * b[i] for i in range(size))
    norm_a = sum(a[i] * a[i] for i in range(size)) ** 0.5
    norm_b = sum(b[i] * b[i] for i in range(size)) ** 0.5
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


def retrieve_relevant_context(
    db: Session,
    chat_thread_id: int,
    query: str,
    limit: int = 6,
    *,
    segment_id: int | None = None,
    project_id: int | None = None,
) -> list[dict[str, Any]]:
    provider = EmbeddingProvider()
    qdrant = QdrantStore()

    query_vec, emb_meta = provider.embed_text(query)
    terms = {t.lower() for t in query.split() if len(t) > 2}

    filter_payload = {
        "must": [
            {"key": "chat_thread_id", "match": {"value": chat_thread_id}},
        ]
    }
    if project_id:
        filter_payload["must"].append({"key": "project_id", "match": {"value": project_id}})

    vector_scores: dict[int, float] = {}
    vector_mode = "vector"
    try:
        raw = qdrant.search(query_vec, limit=max(limit * 4, 20), filter_payload=filter_payload)
        for item in raw:
            chunk_id = (item.get("payload") or {}).get("chunk_id")
            if chunk_id is not None:
                vector_scores[int(chunk_id)] = float(item.get("score") or 0.0)
    except Exception:
        vector_mode = "local_fallback"

    rows = (
        db.query(AssetChunk, Asset)
        .join(Asset, Asset.id == AssetChunk.asset_id)
        .filter(AssetChunk.chat_thread_id == chat_thread_id)
        .all()
    )

    if segment_id:
        seg = db.get(ConversationSegment, segment_id)
        parent_id = seg.parent_segment_id if seg else None
    else:
        parent_id = None

    scored: list[dict[str, Any]] = []
    for chunk, asset in rows:
        text_l = chunk.content_text.lower()
        lexical = float(sum(1 for term in terms if term in text_l))
        vector = vector_scores.get(chunk.id)
        if vector is None and vector_mode == "local_fallback" and chunk.embedding_vector_json:
            vector = _cosine(query_vec, chunk.embedding_vector_json)
        vector = vector or 0.0

        scope_bonus = 0.0
        if segment_id and chunk.segment_id == segment_id:
            scope_bonus = 0.25
        elif parent_id and chunk.segment_id == parent_id:
            scope_bonus = 0.1
        elif segment_id and chunk.segment_id and chunk.segment_id != segment_id:
            scope_bonus = -0.08

        hybrid = vector + (lexical * 0.15) + scope_bonus
        if hybrid <= 0:
            continue
        scored.append(
            {
                "chunk_id": chunk.id,
                "asset_id": asset.id,
                "filename": asset.original_filename,
                "chunk_index": chunk.chunk_index,
                "snippet": chunk.content_text[:260],
                "mime_type": asset.mime_type,
                "page": (chunk.chunk_metadata_json or {}).get("page"),
                "score": round(hybrid, 4),
                "vector_score": round(vector, 4),
                "lexical_score": round(lexical, 4),
                "segment_id": chunk.segment_id,
                "ocr_fallback_used": bool((asset.derived_metadata_json or {}).get("ocr_fallback_used")),
            }
        )

    scored.sort(key=lambda x: x["score"], reverse=True)

    deduped: list[dict[str, Any]] = []
    seen_chunks: set[int] = set()
    per_asset_count: dict[int, int] = {}
    for item in scored:
        cid = item["chunk_id"]
        aid = item["asset_id"]
        if cid in seen_chunks:
            continue
        if per_asset_count.get(aid, 0) >= 3:
            continue
        seen_chunks.add(cid)
        per_asset_count[aid] = per_asset_count.get(aid, 0) + 1
        deduped.append(item)
        if len(deduped) >= limit:
            break

    for item in deduped:
        item["retrieval_mode"] = "hybrid" if vector_mode == "vector" else "hybrid_local_fallback"
        item["embedding_mode"] = emb_meta.get("mode")

    return deduped


def pack_retrieval_context(hits: list[dict[str, Any]], max_chars: int | None = None) -> tuple[str, dict[str, Any]]:
    max_chars = max_chars or settings.rag_pack_max_chars
    lines: list[str] = []
    used_assets: set[int] = set()
    used_chunks: list[int] = []
    ocr_used = False

    for hit in hits:
        candidate = (
            f"[asset#{hit['asset_id']} chunk#{hit['chunk_id']} idx={hit['chunk_index']} page={hit.get('page')}] "
            f"score={hit['score']} :: {hit['snippet']}"
        )
        if sum(len(l) for l in lines) + len(candidate) > max_chars:
            break
        lines.append(candidate)
        used_assets.add(hit["asset_id"])
        used_chunks.append(hit["chunk_id"])
        ocr_used = ocr_used or bool(hit.get("ocr_fallback_used"))

    return "\n".join(lines), {
        "used_asset_ids": sorted(used_assets),
        "used_chunk_ids": used_chunks,
        "ocr_used": ocr_used,
        "hit_count": len(hits),
        "packed_count": len(lines),
        "retrieval_mode": hits[0].get("retrieval_mode") if hits else "none",
        "top_scores": [h["score"] for h in hits[:5]],
    }
