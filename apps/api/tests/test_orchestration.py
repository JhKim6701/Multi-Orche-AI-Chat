from fastapi.testclient import TestClient

from app.main import app
from app.services.ollama_client import OllamaClient

client = TestClient(app)


async def _mock_list_models(self):
    return [{'name': 'orch-model'}]


async def _mock_chat(self, model_name: str, messages: list[dict], images=None, options=None):
    prompt = messages[-1]["content"]
    if "decision: approve|revise|append_missing_points" in prompt:
        return {'message': {'content': 'decision: approve\nLooks good.'}}
    if "reviewer 피드백을 반영해 최종 답변을 개선하라" in prompt:
        return {'message': {'content': f'[{model_name}] revised final answer'}}
    return {'message': {'content': f'[{model_name}] {prompt[:30]}'}}


async def _mock_chat_revise(self, model_name: str, messages: list[dict], images=None, options=None):
    prompt = messages[-1]["content"]
    if "decision: approve|revise|append_missing_points" in prompt:
        return {'message': {'content': 'decision: revise\nMissing concrete checklist.'}}
    if "reviewer 피드백을 반영해 최종 답변을 개선하라" in prompt:
        return {'message': {'content': f'[{model_name}] revised with checklist'}}
    return {'message': {'content': f'[{model_name}] {prompt[:30]}'}}


def _seed_model(monkeypatch):
    monkeypatch.setattr(OllamaClient, 'list_models', _mock_list_models)
    assert client.post('/models/sync').status_code == 200


def test_orchestration_run_happy_path(monkeypatch):
    _seed_model(monkeypatch)
    monkeypatch.setattr(OllamaClient, 'chat', _mock_chat)

    p = client.post('/projects', json={'name': 'orch-p', 'description': None}).json()
    c = client.post('/chats', json={'project_id': p['id'], 'title': 'orch-c'}).json()

    up = client.post('/assets/upload', data={'project_id': str(p['id']), 'chat_thread_id': str(c['id']), 'source_type': 'user_upload'}, files={'file': ('ctx.txt', b'context_resolver should use this asset', 'text/plain')})
    asset_id = up.json()['id']

    run = client.post('/orchestration/run', json={
        'project_id': p['id'],
        'chat_thread_id': c['id'],
        'content_markdown': 'summarize this request',
        'selected_model_names': ['orch-model'],
        'message_asset_ids': [asset_id]
    })
    assert run.status_code == 200
    run_id = run.json()['id']

    detail = client.get(f'/orchestration/runs/{run_id}')
    assert detail.status_code == 200
    payload = detail.json()
    assert payload['run']['status'] == 'completed'
    roles = [s['assigned_role'] for s in payload['steps']]
    assert roles[:4] == ['planner', 'context_resolver', 'model_router', 'final_responder']
    ctx_step = next(step for step in payload['steps'] if step['assigned_role'] == 'context_resolver')
    assert 'asset' in (ctx_step.get('input_summary') or '').lower() or 'asset' in (ctx_step.get('output_summary') or '').lower()
    assert payload['final_message'] is not None
    assert 'final_provenance_summary' in payload['final_message']


def test_orchestration_failure_case(monkeypatch):
    _seed_model(monkeypatch)

    async def _fail(self, *args, **kwargs):
        raise RuntimeError('forced failure')

    monkeypatch.setattr(OllamaClient, 'chat', _fail)

    p = client.post('/projects', json={'name': 'orch-fail-p', 'description': None}).json()
    c = client.post('/chats', json={'project_id': p['id'], 'title': 'orch-fail-c'}).json()

    res = client.post('/orchestration/run', json={
        'project_id': p['id'],
        'chat_thread_id': c['id'],
        'content_markdown': 'fail me',
        'selected_model_names': ['orch-model']
    })
    assert res.status_code in (500, 503)


def test_orchestration_stream_payload_shape(monkeypatch):
    _seed_model(monkeypatch)
    monkeypatch.setattr(OllamaClient, 'chat', _mock_chat)

    p = client.post('/projects', json={'name': 'orch-stream-p', 'description': None}).json()
    c = client.post('/chats', json={'project_id': p['id'], 'title': 'orch-stream-c'}).json()
    run = client.post('/orchestration/run', json={
        'project_id': p['id'],
        'chat_thread_id': c['id'],
        'content_markdown': 'stream payload check',
        'selected_model_names': ['orch-model']
    })
    assert run.status_code == 200
    run_id = run.json()['id']

    stream = client.get(f'/orchestration/runs/{run_id}/stream')
    assert stream.status_code == 200
    body = stream.text
    assert 'event: run_started' in body
    assert 'event_type' in body
    assert 'segment_id' in body
    assert 'timestamp' in body
    assert 'final_message_id' in body
    assert 'reviewer_completed' in body


def test_orchestration_reviewer_happy_path(monkeypatch):
    _seed_model(monkeypatch)
    monkeypatch.setattr(OllamaClient, 'chat', _mock_chat)

    p = client.post('/projects', json={'name': 'orch-review-ok-p', 'description': None}).json()
    c = client.post('/chats', json={'project_id': p['id'], 'title': 'orch-review-ok-c'}).json()
    run = client.post('/orchestration/run', json={
        'project_id': p['id'],
        'chat_thread_id': c['id'],
        'content_markdown': 'review this',
        'selected_model_names': ['orch-model']
    })
    assert run.status_code == 200

    run_id = run.json()['id']
    detail = client.get(f'/orchestration/runs/{run_id}').json()
    assert detail['run']['reviewer_decision'] == 'approve'
    assert any(step['step_name'] == 'reviewer_critic' for step in detail['steps'])
    assert detail['run']['used_segment_id'] is not None


def test_orchestration_reviewer_revise_path(monkeypatch):
    _seed_model(monkeypatch)
    monkeypatch.setattr(OllamaClient, 'chat', _mock_chat_revise)

    p = client.post('/projects', json={'name': 'orch-review-revise-p', 'description': None}).json()
    c = client.post('/chats', json={'project_id': p['id'], 'title': 'orch-review-revise-c'}).json()
    run = client.post('/orchestration/run', json={
        'project_id': p['id'],
        'chat_thread_id': c['id'],
        'content_markdown': 'please revise',
        'selected_model_names': ['orch-model']
    })
    assert run.status_code == 200
    run_id = run.json()['id']
    detail = client.get(f'/orchestration/runs/{run_id}').json()
    assert detail['run']['reviewer_decision'] == 'revise'
    assert any(step['step_name'] == 'final_responder_revision' for step in detail['steps'])
    assert detail['final_message']['model_role'] == 'final_responder_revised'
    assert '[Orchestration Provenance]' in detail['final_message']['content_markdown']
