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
    assert payload['created_segment_id'] == payload['segment_id']
    assert payload['active_switched'] is True
    assert payload['active_segment_id'] == payload['created_segment_id']
    assert payload['branch_from_message_id'] == m['id']
    assert payload['parent_segment_id'] is not None


def test_detect_response_shape():
    p = client.post('/projects', json={'name': 'seg-detect-p', 'description': None}).json()
    c = client.post('/chats', json={'project_id': p['id'], 'title': 'seg-detect-c'}).json()
    client.post('/messages', json={'project_id': p['id'], 'chat_thread_id': c['id'], 'content_markdown': 'fastapi router dependency'})

    detect = client.post(f"/segments/detect?chat_thread_id={c['id']}&new_text=여기서 다른 질문으로 바꿀게")
    assert detect.status_code == 200
    payload = detect.json()
    assert {'active_segment_id', 'diverged', 'overlap', 'reason', 'recommended_action', 'suggested_topic_label'}.issubset(payload.keys())
