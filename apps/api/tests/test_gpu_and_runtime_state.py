from fastapi.testclient import TestClient

from app.main import app
from app.services.ollama_client import OllamaClient

client = TestClient(app)


async def _mock_list_models(self):
    return [{'name': 'model-a'}, {'name': 'llava-vision'}, {'name': 'deepseek-r1'}]


async def _mock_chat(self, model_name: str, messages: list[dict], images=None, options=None):
    return {'message': {'content': f'{model_name}-ok'}}


def test_gpu_toggle_persistence(monkeypatch):
    monkeypatch.setattr(OllamaClient, 'list_models', _mock_list_models)
    monkeypatch.setattr(OllamaClient, 'chat', _mock_chat)

    set_off = client.post('/system/gpu-state', json={'enabled': False})
    assert set_off.status_code == 200
    assert set_off.json()['gpu_enabled'] is False

    fetched = client.get('/system/gpu-state')
    assert fetched.status_code == 200
    assert fetched.json()['gpu_enabled'] is False

    hw = client.get('/system/hardware')
    assert hw.status_code == 200
    assert hw.json()['gpu_enabled'] is False


def test_gpu_aware_routing_metadata(monkeypatch):
    monkeypatch.setattr(OllamaClient, 'list_models', _mock_list_models)
    monkeypatch.setattr(OllamaClient, 'chat', _mock_chat)
    client.post('/models/sync')

    p = client.post('/projects', json={'name': 'gpu-route-p', 'description': None}).json()
    c = client.post('/chats', json={'project_id': p['id'], 'title': 'gpu-route-c'}).json()

    client.post('/system/gpu-state', json={'enabled': False})
    run = client.post('/orchestration/run', json={
        'project_id': p['id'],
        'chat_thread_id': c['id'],
        'content_markdown': 'gpu route check',
        'selected_model_names': ['llava-vision', 'deepseek-r1', 'model-a']
    })
    assert run.status_code == 200
    detail = client.get(f"/orchestration/runs/{run.json()['id']}").json()
    assert detail['run']['gpu_enabled'] is False
    assert 'gpu_enabled=False' in (detail['run']['routing_reason'] or '')

    client.post('/system/gpu-state', json={'enabled': True})
