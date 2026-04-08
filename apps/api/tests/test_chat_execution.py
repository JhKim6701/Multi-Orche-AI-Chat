from fastapi.testclient import TestClient

from app.main import app
from app.services.ollama_client import OllamaClient

client = TestClient(app)


async def _mock_list_models(self):
    return [{'name': 'model-a'}, {'name': 'model-b'}, {'name': 'llava-vision'}]


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
    assert '[RAG Provenance]' in payload['assistant_messages'][0]['content_markdown']
    assert payload['retrieval']['used_asset_ids']


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


def test_execution_mode_semantics_are_distinct(monkeypatch):
    calls = []

    async def _capture(self, model_name: str, messages: list[dict], images=None, options=None):
        calls.append({'model': model_name, 'prompt': messages[-1]['content']})
        return {'message': {'content': f'reply-{model_name}'}}

    monkeypatch.setattr(OllamaClient, 'chat', _capture)
    _setup_models(monkeypatch)

    p = client.post('/projects', json={'name': 'mode-semantics-project', 'description': None}).json()
    c = client.post('/chats', json={'project_id': p['id'], 'title': 'mode-semantics-chat'}).json()

    client.post('/messages/execute', json={
        'project_id': p['id'],
        'chat_thread_id': c['id'],
        'content_markdown': 'base question',
        'selected_model_names': ['model-a', 'model-b'],
        'execution_mode': 'independent',
        'message_asset_ids': [],
    })
    independent_prompts = [c['prompt'] for c in calls[-2:]]

    client.post('/messages/execute', json={
        'project_id': p['id'],
        'chat_thread_id': c['id'],
        'content_markdown': 'base question',
        'selected_model_names': ['model-a', 'model-b'],
        'execution_mode': 'chained',
        'message_asset_ids': [],
    })
    chained_prompts = [c['prompt'] for c in calls[-2:]]

    client.post('/messages/execute', json={
        'project_id': p['id'],
        'chat_thread_id': c['id'],
        'content_markdown': 'base question',
        'selected_model_names': ['model-a', 'model-b'],
        'execution_mode': 'ordered',
        'message_asset_ids': [],
    })
    ordered_prompts = [c['prompt'] for c in calls[-2:]]

    assert independent_prompts[0] == independent_prompts[1]
    assert chained_prompts[0] != chained_prompts[1]
    assert ordered_prompts[0] != ordered_prompts[1]
    assert 'base question' in ordered_prompts[1]
    assert '[Ordered reference from previous model]' in ordered_prompts[1]


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


def test_image_asset_uses_vision_path(monkeypatch):
    calls = []

    async def _capture(self, model_name: str, messages: list[dict], images=None, options=None):
        calls.append({'model': model_name, 'images': images})
        return {'message': {'content': 'vision-ok'}}

    monkeypatch.setattr(OllamaClient, 'chat', _capture)
    _setup_models(monkeypatch)

    p = client.post('/projects', json={'name': 'vision-project', 'description': None}).json()
    c = client.post('/chats', json={'project_id': p['id'], 'title': 'vision-chat'}).json()
    image_upload = client.post(
        '/assets/upload',
        data={'project_id': str(p['id']), 'chat_thread_id': str(c['id']), 'source_type': 'user_upload'},
        files={'file': ('cat.png', b'fake-image-bytes', 'image/png')},
    ).json()

    res = client.post('/messages/execute', json={
        'project_id': p['id'],
        'chat_thread_id': c['id'],
        'content_markdown': '이미지 보고 설명해줘',
        'selected_model_names': ['llava-vision'],
        'execution_mode': 'independent',
        'message_asset_ids': [image_upload['id']],
    })
    assert res.status_code == 200
    assert calls and calls[0]['images'] is not None
    assert '[Generated artifact]' in res.json()['assistant_messages'][0]['content_markdown']


def test_non_vision_model_fallback(monkeypatch):
    calls = []

    async def _capture(self, model_name: str, messages: list[dict], images=None, options=None):
        calls.append({'model': model_name, 'images': images, 'prompt': messages[-1]['content']})
        return {'message': {'content': 'text-fallback'}}

    monkeypatch.setattr(OllamaClient, 'chat', _capture)
    _setup_models(monkeypatch)

    p = client.post('/projects', json={'name': 'fallback-project', 'description': None}).json()
    c = client.post('/chats', json={'project_id': p['id'], 'title': 'fallback-chat'}).json()
    image_upload = client.post(
        '/assets/upload',
        data={'project_id': str(p['id']), 'chat_thread_id': str(c['id']), 'source_type': 'user_upload'},
        files={'file': ('cat.png', b'fake-image-bytes', 'image/png')},
    ).json()

    res = client.post('/messages/execute', json={
        'project_id': p['id'],
        'chat_thread_id': c['id'],
        'content_markdown': '이미지 보고 설명해줘',
        'selected_model_names': ['model-a'],
        'execution_mode': 'independent',
        'message_asset_ids': [image_upload['id']],
    })
    assert res.status_code == 200
    assert calls and calls[0]['images'] is None
    assert 'Vision fallback' in calls[0]['prompt']


def test_ai_generated_artifact_persisted(monkeypatch):
    monkeypatch.setattr(OllamaClient, 'chat', _mock_chat)
    _setup_models(monkeypatch)

    p = client.post('/projects', json={'name': 'artifact-project', 'description': None}).json()
    c = client.post('/chats', json={'project_id': p['id'], 'title': 'artifact-chat'}).json()
    res = client.post('/messages/execute', json={
        'project_id': p['id'],
        'chat_thread_id': c['id'],
        'content_markdown': 'generate report',
        'selected_model_names': ['model-a'],
        'execution_mode': 'independent',
        'message_asset_ids': [],
    })
    assert res.status_code == 200
    assistant_id = res.json()['assistant_messages'][0]['id']
    assets = client.get(f"/assets/chat/{c['id']}").json()
    generated = [a for a in assets if a['source_type'] == 'ai_generated' and a['message_id'] == assistant_id]
    assert len(generated) >= 1
    assert generated[0]['producing_model'] == 'model-a'
    assert generated[0]['derived_metadata_json']['generation_kind'] in {'text', 'markdown', 'json', 'code'}
