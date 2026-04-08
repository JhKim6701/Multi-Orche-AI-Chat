import time

from fastapi.testclient import TestClient

from app.main import app
from app.services.ollama_client import OllamaClient

client = TestClient(app)


async def _mock_list_models(self):
    return [{"name": "rc-model"}]


async def _mock_chat(self, model_name: str, messages: list[dict], images=None, options=None):
    prompt = messages[-1]["content"]
    if "decision: approve|revise|append_missing_points" in prompt:
        return {"message": {"content": "decision: approve"}}
    return {"message": {"content": f"[{model_name}] {prompt[:24]}"}}


def _wait_run(run_id: int, timeout: float = 3.0):
    started = time.time()
    while time.time() - started < timeout:
        detail = client.get(f"/orchestration/runs/{run_id}")
        if detail.status_code == 200:
            status = detail.json()["run"]["status"]
            if status in {"completed", "approval_pending", "rejected", "failed"}:
                return detail.json()
        time.sleep(0.05)
    return client.get(f"/orchestration/runs/{run_id}").json()


def test_release_candidate_smoke(monkeypatch):
    monkeypatch.setattr(OllamaClient, "list_models", _mock_list_models)
    monkeypatch.setattr(OllamaClient, "chat", _mock_chat)
    assert client.post("/models/sync").status_code == 200

    health = client.get("/system/health").json()
    assert "migration" in health["checks"]
    assert "database" in health["checks"]
    assert "ollama" in health["checks"]
    assert "qdrant" in health["checks"]
    assert "upload_root" in health["checks"]
    readiness = client.get("/system/readiness")
    assert readiness.status_code == 200
    readiness_payload = readiness.json()
    assert "ready" in readiness_payload
    assert "unresolved_dependencies" in readiness_payload

    p = client.post("/projects", json={"name": "rc-project", "description": "smoke"}).json()
    c = client.post("/chats", json={"project_id": p["id"], "title": "rc-chat"}).json()

    manual = client.post(
        "/messages/execute",
        json={
            "project_id": p["id"],
            "chat_thread_id": c["id"],
            "content_markdown": "manual execution smoke",
            "selected_model_names": ["rc-model"],
            "execution_mode": "independent",
        },
    )
    assert manual.status_code == 200

    run = client.post(
        "/orchestration/run",
        json={
            "project_id": p["id"],
            "chat_thread_id": c["id"],
            "content_markdown": "orchestration smoke",
            "selected_model_names": ["rc-model"],
            "require_approval_before_publish": True,
        },
    )
    assert run.status_code == 200
    run_id = run.json()["id"]
    detail = _wait_run(run_id)
    assert detail["run"]["status"] == "approval_pending"

    assert client.post(f"/orchestration/runs/{run_id}/approve").status_code == 200
    approved = _wait_run(run_id)
    assert approved["run"]["approval_status"] == "approved"

    run2 = client.post(
        "/orchestration/run",
        json={
            "project_id": p["id"],
            "chat_thread_id": c["id"],
            "content_markdown": "orchestration reject smoke",
            "selected_model_names": ["rc-model"],
            "require_approval_before_publish": True,
        },
    )
    run2_id = run2.json()["id"]
    rejected_pre = _wait_run(run2_id)
    assert rejected_pre["run"]["status"] == "approval_pending"
    assert client.post(f"/orchestration/runs/{run2_id}/reject").status_code == 200
    rejected = _wait_run(run2_id)
    assert rejected["run"]["approval_status"] == "rejected"

    prefs = client.get("/models/role-preferences")
    assert prefs.status_code == 200
    assert isinstance(prefs.json(), list)
    update = client.put("/models/role-preferences/orchestrator", json={"preferred_model_names": ["rc-model"]})
    assert update.status_code == 200
    assert update.json()["default_model_name"] == "rc-model"
