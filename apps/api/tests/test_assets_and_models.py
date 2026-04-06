from fastapi.testclient import TestClient

from app.main import app
from app.services.ollama_client import OllamaClient

client = TestClient(app)


async def _mock_list_models(self):
    return [{'name': 'mistral:latest'}, {'name': 'llama3.1:8b'}]


async def _mock_pull(self, model_name: str):
    return {'status': 'success', 'name': model_name}


def test_asset_upload_happy_path(tmp_path, monkeypatch):
    p = client.post('/projects', json={'name': 'asset-project', 'description': None}).json()
    c = client.post('/chats', json={'project_id': p['id'], 'title': 'asset-chat'}).json()

    files = {'file': ('hello.txt', b'hello-world', 'text/plain')}
    data = {'project_id': str(p['id']), 'chat_thread_id': str(c['id']), 'source_type': 'user_upload'}
    res = client.post('/assets/upload', data=data, files=files)
    assert res.status_code == 200
    assert res.json()['original_filename'] == 'hello.txt'
    asset_id = res.json()['id']
    status = client.get(f'/assets/{asset_id}/ingestion-status')
    assert status.status_code == 200
    assert 'ingestion' in status.json()
    chunks = client.get(f'/assets/{asset_id}/chunks')
    assert chunks.status_code == 200
    assert isinstance(chunks.json(), list)


def test_retrieval_debug_endpoint_shape():
    p = client.post('/projects', json={'name': 'asset-project-debug', 'description': None}).json()
    c = client.post('/chats', json={'project_id': p['id'], 'title': 'asset-chat-debug'}).json()
    files = {'file': ('guide.txt', b'deployment guide and troubleshooting checklist', 'text/plain')}
    data = {'project_id': str(p['id']), 'chat_thread_id': str(c['id']), 'source_type': 'user_upload'}
    upload = client.post('/assets/upload', data=data, files=files)
    assert upload.status_code == 200
    preview = client.get(f"/assets/chat/{c['id']}/retrieval-preview?query=checklist")
    assert preview.status_code == 200
    payload = preview.json()
    assert 'hits' in payload
    assert 'scope' in payload
    assert 'packed_meta' in payload
    if payload['hits']:
        assert {'chunk_id', 'asset_id', 'score', 'vector_score', 'lexical_score', 'retrieval_mode'}.issubset(payload['hits'][0].keys())


def test_model_toggle_and_sort(monkeypatch):
    monkeypatch.setattr(OllamaClient, 'list_models', _mock_list_models)
    monkeypatch.setattr(OllamaClient, 'pull_model', _mock_pull)

    sync = client.post('/models/sync')
    assert sync.status_code == 200
    model = sync.json()[0]

    toggled = client.patch(f"/models/{model['id']}/toggle", json={'enabled': False})
    assert toggled.status_code == 200
    assert toggled.json()['enabled'] is False

    sorted_res = client.patch(f"/models/{model['id']}/sort", json={'sort_order': 99})
    assert sorted_res.status_code == 200
    assert sorted_res.json()['sort_order'] == 99
