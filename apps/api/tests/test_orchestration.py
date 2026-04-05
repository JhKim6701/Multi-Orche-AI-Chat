from fastapi.testclient import TestClient

from app.main import app
from app.services.ollama_client import OllamaClient

client = TestClient(app)


async def _mock_list_models(self):
    return [{'name': 'orch-model'}]


async def _mock_chat(self, model_name: str, messages: list[dict], images=None, options=None):
    return {'message': {'content': f'[{model_name}] {messages[-1]["content"][:30]}'}}


def _seed_model(monkeypatch):
    monkeypatch.setattr(OllamaClient, 'list_models', _mock_list_models)
    assert client.post('/models/sync').status_code == 200


def test_orchestration_run_happy_path(monkeypatch):
    _seed_model(monkeypatch)
    monkeypatch.setattr(OllamaClient, 'chat', _mock_chat)

    p = client.post('/projects', json={'name': 'orch-p', 'description': None}).json()
    c = client.post('/chats', json={'project_id': p['id'], 'title': 'orch-c'}).json()

    run = client.post('/orchestration/run', json={
        'project_id': p['id'],
        'chat_thread_id': c['id'],
        'content_markdown': 'summarize this request',
        'selected_model_names': ['orch-model']
    })
    assert run.status_code == 200
    run_id = run.json()['id']

    detail = client.get(f'/orchestration/runs/{run_id}')
    assert detail.status_code == 200
    payload = detail.json()
    assert payload['run']['status'] == 'completed'
    roles = [s['assigned_role'] for s in payload['steps']]
    assert roles[:4] == ['planner', 'context_resolver', 'model_router', 'final_responder']
    assert payload['final_message'] is not None


def test_orchestration_failure_case(monkeypatch):
    _seed_model(monkeypatch)

    async def _fail(self, *args, **kwargs):
        raise RuntimeError('forced failure')

    monkeypatch.setattr(OllamaClient, 'chat', _fail)

    p = client.post('/projects', json={'name': 'orch-fail-p', 'description': None}).json()
    c = client.post('/chats', json={'project_id': p['id'], 'title': 'orch-fail-c'}).json()

    res = client.post('/orchestration/run', json={
        'project_id': p['id'],
        'chat_thread_id': c['id'],
        'content_markdown': 'fail me',
        'selected_model_names': ['orch-model']
    })
    assert res.status_code in (500, 503)
