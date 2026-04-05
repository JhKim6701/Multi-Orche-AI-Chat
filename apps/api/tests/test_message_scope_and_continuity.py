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
    first_segment_id = all_msgs.json()['items'][0]['segment_id']
    by_segment = client.get(f"/messages?chat_thread_id={c['id']}&scope=segment&segment_id={first_segment_id}")
    assert active.status_code == 200 and all_msgs.status_code == 200 and by_segment.status_code == 200
    assert all_msgs.json()['scope_meta']['scope'] == 'all'
    assert active.json()['scope_meta']['scope'] == 'active'
    assert by_segment.json()['scope_meta']['selected_segment_id'] == first_segment_id
    assert len(all_msgs.json()['items']) >= len(active.json()['items'])
    assert len(all_msgs.json()['scope_meta']['segment_boundaries']) >= 1


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


def test_segment_switch_keeps_scope_consistent(monkeypatch):
    _seed(monkeypatch)
    p = client.post('/projects', json={'name': 'scope-switch-p', 'description': None}).json()
    c = client.post('/chats', json={'project_id': p['id'], 'title': 'scope-switch-c'}).json()

    client.post('/messages/execute', json={
        'project_id': p['id'], 'chat_thread_id': c['id'], 'content_markdown': 'python backend',
        'selected_model_names': ['seg-model'], 'execution_mode': 'independent', 'message_asset_ids': []
    })
    client.post('/messages/execute', json={
        'project_id': p['id'], 'chat_thread_id': c['id'], 'content_markdown': '완전히 다른 여행 질문입니다',
        'selected_model_names': ['seg-model'], 'execution_mode': 'independent', 'message_asset_ids': []
    })

    all_msgs = client.get(f"/messages?chat_thread_id={c['id']}&scope=all").json()
    first_segment_id = all_msgs['items'][0]['segment_id']
    switch = client.post(f"/segments/switch?chat_thread_id={c['id']}", json={'segment_id': first_segment_id})
    assert switch.status_code == 200
    assert switch.json()['active_segment']['id'] == first_segment_id

    active = client.get(f"/messages?chat_thread_id={c['id']}&scope=active").json()
    assert active['scope_meta']['active_segment_id'] == first_segment_id
    assert all(m['segment_id'] == first_segment_id for m in active['items'])
