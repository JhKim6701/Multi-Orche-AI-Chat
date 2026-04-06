from __future__ import annotations

from typing import Final

_KNOWN_PATTERNS: Final[list[tuple[str, tuple[str, ...]]]] = [
    ("ollama_unavailable", ("ollama", "connection refused", "ollama unavailable", "failed to connect to ollama")),
    ("qdrant_unavailable", ("qdrant", "connection refused", "qdrant unavailable", "vector store unavailable")),
    ("embedding_failure", ("embedding", "embed", "vectorize", "nomic-embed")),
    ("ingestion_failure", ("ingest", "extraction", "upload", "chunking", "ocr")),
    ("retrieval_empty", ("retrieval empty", "no retrieval", "no relevant context", "empty retrieval")),
    ("routing_fallback", ("routing", "fallback model", "capability mismatch", "model fallback")),
    ("approval_state_inconsistent", ("approval state", "approval_state", "no pending approval", "already approved", "already rejected")),
    ("desktop_runtime_misconfigured", ("desktop", "mode mismatch", "misconfigured", "runtime-info mismatch")),
]


def classify_failure(message: str) -> str:
    text = (message or "").lower()
    for category, patterns in _KNOWN_PATTERNS:
        if any(pattern in text for pattern in patterns):
            return category
    return "runtime_error"


def recovery_hint(category: str) -> str:
    return {
        "ollama_unavailable": "Ollama 서비스 실행 여부와 MOAC_OLLAMA_BASE_URL을 확인하세요.",
        "qdrant_unavailable": "Qdrant 서비스 실행 여부와 MOAC_QDRANT_URL을 확인하세요.",
        "embedding_failure": "임베딩 모델/네트워크 상태를 확인하고 fallback 모드를 점검하세요.",
        "ingestion_failure": "파일 형식/권한과 OCR·chunking 파이프라인 로그를 확인하세요.",
        "retrieval_empty": "retrieval scope(세그먼트/채팅)와 query를 조정해보세요.",
        "routing_fallback": "모델 capabilities와 enabled/downloaded 상태를 확인하세요.",
        "approval_state_inconsistent": "승인 상태 저장소와 DB run 상태를 점검하고, run detail 재조회 후 approve/reject를 다시 시도하세요.",
        "desktop_runtime_misconfigured": "desktop 모드(env/config)와 doctor 결과를 확인하세요.",
        "runtime_error": "로그와 diagnostics 패널을 확인 후 재시도하세요.",
    }.get(category, "로그와 diagnostics 패널을 확인 후 재시도하세요.")
