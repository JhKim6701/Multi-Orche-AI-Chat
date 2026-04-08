from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Any, AsyncIterator

from app.db.session import SessionLocal
from app.models import OrchestrationRun
from app.orchestration.adapters import OrchestrationRuntime
from app.orchestration.graph import build_graph
from app.orchestration.state import OrchestrationState


class RunEventHub:
    def __init__(self):
        self._queues: dict[int, list[asyncio.Queue[dict[str, Any]]]] = defaultdict(list)

    def subscribe(self, run_id: int) -> asyncio.Queue[dict[str, Any]]:
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._queues[run_id].append(q)
        return q

    def unsubscribe(self, run_id: int, queue: asyncio.Queue[dict[str, Any]]) -> None:
        lst = self._queues.get(run_id, [])
        if queue in lst:
            lst.remove(queue)

    def publish(self, run_id: int, payload: dict[str, Any]) -> None:
        payload.setdefault("timestamp", datetime.utcnow().isoformat())
        for q in self._queues.get(run_id, []):
            q.put_nowait(payload)


hub = RunEventHub()


def launch_run(state: OrchestrationState, runtime_kwargs: dict[str, Any]) -> None:
    run_id = int(state["run_id"])

    async def _task() -> None:
        hub.publish(run_id, {"event_type": "run_started", "run_id": run_id, "status": "running"})
        db = SessionLocal()
        try:
            runtime = OrchestrationRuntime(db=db, emit_event=lambda evt: hub.publish(run_id, evt), **runtime_kwargs)
            runtime.run = db.get(OrchestrationRun, run_id)
            graph = build_graph(runtime)
            await graph.ainvoke(state)
            if runtime.run and runtime.run.status == "running":
                runtime.run.status = "completed"
                runtime.run.ended_at = datetime.utcnow()
            db.commit()
            hub.publish(run_id, {"event_type": "run_completed", "run_id": run_id, "status": runtime.run.status if runtime.run else "completed", "final_message_id": runtime.run.final_message_id if runtime.run else None})
        except Exception as exc:
            if runtime.run:
                runtime.run.status = "failed"
                runtime.run.ended_at = datetime.utcnow()
                db.commit()
            hub.publish(run_id, {"event_type": "run_failed", "run_id": run_id, "status": "failed", "error": str(exc)})
        finally:
            db.close()

    asyncio.create_task(_task())


async def stream_events(run_id: int) -> AsyncIterator[dict[str, Any]]:
    q = hub.subscribe(run_id)
    try:
        while True:
            event = await q.get()
            yield event
            if event.get("event_type") in {"run_completed", "run_failed", "run_rejected"}:
                break
    finally:
        hub.unsubscribe(run_id, q)
