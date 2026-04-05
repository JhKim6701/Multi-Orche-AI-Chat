from fastapi.testclient import TestClient

from app.main import app
from app.services.ollama_client import OllamaClient

client = TestClient(app)


async def _mock_list_models(self):
    return [{'name': 'model-a'}, {'name': 'model-b'}]


async def _mock_chat(self, model_name: str, messages: list[dict], images=None, options=None):
    return {'message': {'content': f'reply-from-{model_name}'}}


def _setup_models(monkeypatch):
    monkeypatch.setattr(OllamaClient, 'list_models', _mock_list_models)
    sync = client.post('/models/sync')
    assert sync.status_code == 200


def test_execute_message_happy_path(monkeypatch):
    monkeypatch.setattr(OllamaClient, 'chat', _mock_chat)
    _setup_models(monkeypatch)

    p = client.post('/projects', json={'name': 'exec-project', 'description': None}).json()
    c = client.post('/chats', json={'project_id': p['id'], 'title': 'exec-chat'}).json()

    up = client.post('/assets/upload', data={'project_id': str(p['id']), 'chat_thread_id': str(c['id']), 'source_type': 'user_upload'}, files={'file': ('ref.txt', b'hello retrieval context for model', 'text/plain')})
    aid = up.json()['id']

    res = client.post(
        '/messages/execute',
        json={
            'project_id': p['id'],
            'chat_thread_id': c['id'],
            'content_markdown': 'hello',
            'selected_model_names': ['model-a'],
            'execution_mode': 'independent',
            'message_asset_ids': [aid]
        }
    )

    assert res.status_code == 200
    payload = res.json()
    assert payload['user_message']['role'] == 'user'
    assert 'reply-from-model-a' in payload['assistant_messages'][0]['content_markdown']
    assert '[Used assets]' in payload['assistant_messages'][0]['content_markdown']


def test_multiple_model_ordered_execution(monkeypatch):
    monkeypatch.setattr(OllamaClient, 'chat', _mock_chat)
    _setup_models(monkeypatch)

    models = client.get('/models').json()
    by_name = {m['model_name']: m for m in models}
    client.patch(f"/models/{by_name['model-a']['id']}/sort", json={'sort_order': 2})
    client.patch(f"/models/{by_name['model-b']['id']}/sort", json={'sort_order': 1})

    p = client.post('/projects', json={'name': 'ordered-project', 'description': None}).json()
    c = client.post('/chats', json={'project_id': p['id'], 'title': 'ordered-chat'}).json()

    res = client.post(
        '/messages/execute',
        json={
            'project_id': p['id'],
            'chat_thread_id': c['id'],
            'content_markdown': 'hello',
            'selected_model_names': ['model-a', 'model-b'],
            'execution_mode': 'ordered',
            'message_asset_ids': []
        }
    )
    assert res.status_code == 200
    assistant_messages = res.json()['assistant_messages']
    assert assistant_messages[0]['model_name'] == 'model-b'
    assert assistant_messages[1]['model_name'] == 'model-a'


def test_execute_message_ollama_unavailable(monkeypatch):
    async def _raise(self, *args, **kwargs):
        from app.services.ollama_client import OllamaUnavailableError

        raise OllamaUnavailableError('Ollama 서버에 연결할 수 없거나 요청이 실패했습니다.')

    monkeypatch.setattr(OllamaClient, 'chat', _raise)
    _setup_models(monkeypatch)

    p = client.post('/projects', json={'name': 'exec-project-2', 'description': None}).json()
    c = client.post('/chats', json={'project_id': p['id'], 'title': 'exec-chat-2'}).json()

    res = client.post(
        '/messages/execute',
        json={
            'project_id': p['id'],
            'chat_thread_id': c['id'],
            'content_markdown': 'hello',
            'selected_model_names': ['model-a'],
            'execution_mode': 'independent',
            'message_asset_ids': []
        }
    )
    assert res.status_code == 503
