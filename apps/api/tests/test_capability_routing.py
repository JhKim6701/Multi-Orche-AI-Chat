from app.api.routers.models import detect_capabilities


def test_capability_routing_heuristic():
    caps = detect_capabilities('qwen2.5-vl:latest')
    assert caps['supports_vision'] is True

    caps2 = detect_capabilities('deepseek-r1:latest')
    assert caps2['supports_reasoning'] is True


def test_capability_embeddings_heuristic():
    caps = detect_capabilities('nomic-embed-text')
    assert caps['supports_embeddings'] is True
