from fastapi.testclient import TestClient

from app.main import app
from app.services.ollama_client import OllamaClient

client = TestClient(app)


async def _mock_list_models(self):
    return [{'name': 'seg-model'}]


async def _mock_chat(self, model_name: str, messages: list[dict], images=None, options=None):
    return {'message': {'content': 'ok'}}


def _seed(monkeypatch):
    monkeypatch.setattr(OllamaClient, 'list_models', _mock_list_models)
    monkeypatch.setattr(OllamaClient, 'chat', _mock_chat)
    client.post('/models/sync')


def test_messages_scope_active_all_segment(monkeypatch):
    _seed(monkeypatch)
    p = client.post('/projects', json={'name': 'm-scope-p', 'description': None}).json()
    c = client.post('/chats', json={'project_id': p['id'], 'title': 'm-scope-c'}).json()

    client.post('/messages/execute', json={
        'project_id': p['id'], 'chat_thread_id': c['id'], 'content_markdown': 'python api auth',
        'selected_model_names': ['seg-model'], 'execution_mode': 'independent', 'message_asset_ids': []
    })
    client.post('/messages/execute', json={
        'project_id': p['id'], 'chat_thread_id': c['id'], 'content_markdown': '여행 일정 추천',
        'selected_model_names': ['seg-model'], 'execution_mode': 'independent', 'message_asset_ids': []
    })

    active = client.get(f"/messages?chat_thread_id={c['id']}&scope=active")
    all_msgs = client.get(f"/messages?chat_thread_id={c['id']}&scope=all")
    assert active.status_code == 200 and all_msgs.status_code == 200
    assert len(all_msgs.json()) >= len(active.json())


def test_execution_result_includes_used_segment(monkeypatch):
    _seed(monkeypatch)
    p = client.post('/projects', json={'name': 'm-seg-p', 'description': None}).json()
    c = client.post('/chats', json={'project_id': p['id'], 'title': 'm-seg-c'}).json()

    res = client.post('/messages/execute', json={
        'project_id': p['id'], 'chat_thread_id': c['id'], 'content_markdown': 'fastapi 질문',
        'selected_model_names': ['seg-model'], 'execution_mode': 'independent', 'message_asset_ids': []
    })
    assert res.status_code == 200
    assert res.json()['used_segment_id'] is not None
