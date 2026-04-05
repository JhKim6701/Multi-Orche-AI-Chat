from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    r = client.get('/system/health')
    assert r.status_code == 200
    assert r.json()['status'] == 'ok'


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
    assert len(lst.json()) >= 1
