from app.services.failure_taxonomy import classify_failure, recovery_hint


def test_failure_taxonomy_mapping():
    assert classify_failure('Ollama server unreachable') == 'ollama_unavailable'
    assert classify_failure('qdrant connection refused') == 'qdrant_unavailable'
    assert classify_failure('embedding call failed') == 'embedding_failure'
    assert classify_failure('ingest failed') == 'ingestion_failure'
    assert classify_failure('retrieval empty result') == 'retrieval_empty'
    assert classify_failure('routing fallback triggered') == 'routing_fallback'
    assert classify_failure('approval pending timeout') == 'approval_pending_timeout'
    assert classify_failure('desktop mode mismatch misconfigured') == 'desktop_runtime_misconfigured'


def test_failure_taxonomy_hint_non_empty():
    cat = classify_failure('qdrant unavailable')
    assert recovery_hint(cat)
