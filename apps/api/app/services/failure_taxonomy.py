from __future__ import annotations


def classify_failure(message: str) -> str:
    text = (message or "").lower()
    if "ollama" in text:
        return "ollama_unavailable"
    if "qdrant" in text:
        return "qdrant_unavailable"
    if "embedding" in text:
        return "embedding_failure"
    if "ingest" in text or "extraction" in text:
        return "ingestion_failure"
    if "retrieval" in text and "empty" in text:
        return "retrieval_empty"
    if "fallback" in text:
        return "routing_fallback"
    if "approval" in text and "pending" in text:
        return "approval_pending_timeout"
    if "approval state" in text or "approval_state" in text or "no pending approval" in text:
        return "approval_state_inconsistent"
    if "desktop" in text and ("misconfigured" in text or "mode mismatch" in text):
        return "desktop_runtime_misconfigured"
    return "runtime_error"


def recovery_hint(category: str) -> str:
    return {
        "ollama_unavailable": "Ollama 서비스 실행 여부와 MOAC_OLLAMA_BASE_URL을 확인하세요.",
        "qdrant_unavailable": "Qdrant 서비스 실행 여부와 MOAC_QDRANT_URL을 확인하세요.",
        "embedding_failure": "임베딩 모델/네트워크 상태를 확인하고 fallback 모드를 점검하세요.",
        "ingestion_failure": "파일 형식과 업로드 경로 권한을 확인하세요.",
        "retrieval_empty": "retrieval scope(세그먼트/채팅)와 query를 조정해보세요.",
        "routing_fallback": "모델 capabilities와 enabled/downloaded 상태를 확인하세요.",
        "approval_pending_timeout": "승인 대기 상태를 점검하고 approve/reject를 수행하세요.",
        "approval_state_inconsistent": "승인 상태 파일과 DB 상태가 어긋났습니다. run detail을 확인 후 재시도하세요.",
        "desktop_runtime_misconfigured": "desktop 모드(env/config)와 doctor 결과를 확인하세요.",
        "runtime_error": "로그와 diagnostics 패널을 확인 후 재시도하세요.",
    }.get(category, "로그와 diagnostics 패널을 확인 후 재시도하세요.")
