from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get('/system/health')
    assert r.status_code == 200
    payload = r.json()
    assert payload['status'] in {'ok', 'degraded'}
    assert 'checks' in payload
    assert {'database', 'ollama', 'qdrant', 'upload_root'}.issubset(payload['checks'].keys())
    assert 'unresolved_dependencies' in payload
    assert 'doctor_hint' in payload


def test_readiness_shape():
    r = client.get('/system/readiness')
    assert r.status_code == 200
    payload = r.json()
    assert 'ready' in payload
    assert 'checks' in payload
    assert 'unresolved_dependencies' in payload


def test_diagnostics_masking():
    health = client.get('/system/health')
    assert health.status_code == 200
    payload = health.json()
    assert payload['sensitive_details_included'] is False
    assert payload['database_url'] != payload.get('upload_root')
    assert '...' in payload['upload_root'] or payload['upload_root'].startswith('/')

    runtime_info = client.get('/system/runtime-info')
    assert runtime_info.status_code == 200
    info = runtime_info.json()
    assert info['sensitive_details_included'] is False
    assert '***' in info['database_url']


def test_project_chat_message_flow():
    p = client.post('/projects', json={'name': 'demo', 'description': 'd'})
    assert p.status_code == 200
    pid = p.json()['id']

    c = client.post('/chats', json={'project_id': pid, 'title': 'chat1'})
    assert c.status_code == 200
    cid = c.json()['id']

    m = client.post('/messages', json={'project_id': pid, 'chat_thread_id': cid, 'content_markdown': 'hello'})
    assert m.status_code == 200

    lst = client.get(f'/messages?chat_thread_id={cid}')
    assert lst.status_code == 200
    payload = lst.json()
    assert payload['scope_meta']['scope'] == 'active'
    assert len(payload['items']) >= 1
