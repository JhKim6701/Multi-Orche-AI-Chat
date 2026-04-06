"""Golden-fixture style evaluation harness for retrieval/routing/orchestration quality gates."""

from fastapi.testclient import TestClient

from app.main import app
from app.services.ollama_client import OllamaClient

client = TestClient(app)


async def _mock_models(self):
    return [{'name': 'eval-model'}, {'name': 'eval-vision'}]


async def _mock_chat(self, model_name: str, messages: list[dict], images=None, options=None):
    prompt = messages[-1]['content']
    if 'decision: approve|revise|append_missing_points' in prompt:
        return {'message': {'content': 'decision: approve\nlooks good'}}
    return {'message': {'content': f'[{model_name}] {prompt[:40]}'}}


def _seed(monkeypatch):
    monkeypatch.setattr(OllamaClient, 'list_models', _mock_models)
    monkeypatch.setattr(OllamaClient, 'chat', _mock_chat)
    assert client.post('/models/sync').status_code == 200


def test_retrieval_eval_fixture(monkeypatch):
    _seed(monkeypatch)
    p = client.post('/projects', json={'name': 'eval-ret-p', 'description': None}).json()
    c = client.post('/chats', json={'project_id': p['id'], 'title': 'eval-ret-c'}).json()
    up = client.post('/assets/upload', data={'project_id': str(p['id']), 'chat_thread_id': str(c['id']), 'source_type': 'user_upload'}, files={'file': ('guide.txt', b'release checklist deployment rollback plan', 'text/plain')})
    assert up.status_code == 200

    preview = client.get(f"/assets/chat/{c['id']}/retrieval-preview?query=deployment checklist")
    assert preview.status_code == 200
    payload = preview.json()
    assert payload['hits']
    top = payload['hits'][0]
    assert top['asset_id'] == up.json()['id']
    assert top['score'] >= top['vector_score']


def test_routing_eval_fixture(monkeypatch):
    _seed(monkeypatch)
    p = client.post('/projects', json={'name': 'eval-route-p', 'description': None}).json()
    c = client.post('/chats', json={'project_id': p['id'], 'title': 'eval-route-c'}).json()
    image_upload = client.post('/assets/upload', data={'project_id': str(p['id']), 'chat_thread_id': str(c['id']), 'source_type': 'user_upload'}, files={'file': ('img.png', b'fakebytes', 'image/png')}).json()

    run = client.post('/orchestration/run', json={
        'project_id': p['id'],
        'chat_thread_id': c['id'],
        'content_markdown': 'analyze this image request',
        'selected_model_names': ['eval-model', 'eval-vision'],
        'message_asset_ids': [image_upload['id']],
    })
    assert run.status_code == 200
    detail = client.get(f"/orchestration/runs/{run.json()['id']}").json()
    assert 'vision' in (detail['run'].get('routing_reason') or '') or detail['run'].get('vision_used') is True


def test_orchestration_output_eval_fixture(monkeypatch):
    _seed(monkeypatch)
    p = client.post('/projects', json={'name': 'eval-orch-p', 'description': None}).json()
    c = client.post('/chats', json={'project_id': p['id'], 'title': 'eval-orch-c'}).json()

    run = client.post('/orchestration/run', json={
        'project_id': p['id'],
        'chat_thread_id': c['id'],
        'content_markdown': 'provide final answer with review',
        'selected_model_names': ['eval-model'],
    })
    assert run.status_code == 200
    detail = client.get(f"/orchestration/runs/{run.json()['id']}").json()
    assert detail['run']['reviewer_decision'] in {'approve', 'revise', 'append_missing_points'}
    assert detail['run'].get('critic_summary') is not None
