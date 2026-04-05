from fastapi.testclient import TestClient

from app.main import app
from app.services.ollama_client import OllamaClient

client = TestClient(app)


async def _mock_chat(self, model_name: str, messages: list[dict], images=None, options=None):
    return {'message': {'content': f'reply-from-{model_name}'}}


def test_execute_message_happy_path(monkeypatch):
    monkeypatch.setattr(OllamaClient, 'chat', _mock_chat)

    p = client.post('/projects', json={'name': 'exec-project', 'description': None}).json()
    c = client.post('/chats', json={'project_id': p['id'], 'title': 'exec-chat'}).json()

    res = client.post(
        '/messages/execute',
        json={
            'project_id': p['id'],
            'chat_thread_id': c['id'],
            'content_markdown': 'hello',
            'selected_model_names': ['llama3.1'],
            'execution_mode': 'independent',
            'message_asset_ids': []
        }
    )

    assert res.status_code == 200
    payload = res.json()
    assert payload['user_message']['role'] == 'user'
    assert payload['assistant_messages'][0]['content_markdown'] == 'reply-from-llama3.1'


def test_execute_message_ollama_unavailable(monkeypatch):
    async def _raise(self, *args, **kwargs):
        from app.services.ollama_client import OllamaUnavailableError

        raise OllamaUnavailableError('Ollama 서버에 연결할 수 없거나 요청이 실패했습니다.')

    monkeypatch.setattr(OllamaClient, 'chat', _raise)

    p = client.post('/projects', json={'name': 'exec-project-2', 'description': None}).json()
    c = client.post('/chats', json={'project_id': p['id'], 'title': 'exec-chat-2'}).json()

    res = client.post(
        '/messages/execute',
        json={
            'project_id': p['id'],
            'chat_thread_id': c['id'],
            'content_markdown': 'hello',
            'selected_model_names': ['llama3.1'],
            'execution_mode': 'independent',
            'message_asset_ids': []
        }
    )
    assert res.status_code == 503
