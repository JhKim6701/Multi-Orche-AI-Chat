from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_branch_linkage_integrity():
    p = client.post('/projects', json={'name': 'seg-p', 'description': None}).json()
    c = client.post('/chats', json={'project_id': p['id'], 'title': 'seg-c'}).json()

    m = client.post('/messages', json={'project_id': p['id'], 'chat_thread_id': c['id'], 'content_markdown': 'first topic message'}).json()

    b = client.post(f"/segments/branch?chat_thread_id={c['id']}", json={'from_message_id': m['id'], 'topic_label': 'branch-topic'})
    assert b.status_code == 200
    payload = b.json()
    assert payload['branch_from_message_id'] == m['id']
    assert payload['parent_segment_id'] is not None
