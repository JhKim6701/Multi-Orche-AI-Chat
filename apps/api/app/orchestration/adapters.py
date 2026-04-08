from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Asset, ConversationSegment, Message, ModelRegistry, OrchestrationRun, OrchestrationStep, RoleEnum
from app.orchestration.state import OrchestrationState
from app.services.artifact_manager import create_ai_generated_artifact
from app.services.asset_ingestion import pack_retrieval_context, retrieve_relevant_context
from app.services.ollama_client import OllamaClient
from app.services.runtime_state import get_gpu_enabled
from app.services.topic_segmentation import maybe_start_new_segment, update_segment_summary
from app.orchestration.events import step_event_names


@dataclass
class StepContext:
    step: OrchestrationStep
    depends_on: list[int]


class OrchestrationRuntime:
    def __init__(
        self,
        db: Session,
        project_id: int,
        chat_thread_id: int,
        content_markdown: str,
        selected_model_names: list[str],
        orchestrator_model_name: str | None,
        message_asset_ids: list[int],
        require_approval_before_publish: bool,
        emit_event=None,
    ):
        self.db = db
        self.project_id = project_id
        self.chat_thread_id = chat_thread_id
        self.content_markdown = content_markdown
        self.selected_model_names = selected_model_names
        self.orchestrator_model_name = orchestrator_model_name
        self.message_asset_ids = message_asset_ids
        self.require_approval_before_publish = require_approval_before_publish
        self.client = OllamaClient()
        self.run: OrchestrationRun | None = None
        self.emit_event = emit_event

    @staticmethod
    def summarize(text: str, limit: int = 220) -> str:
        cleaned = " ".join(text.strip().split())
        return cleaned[:limit]

    @staticmethod
    def output_summary(text: str) -> str:
        return OrchestrationRuntime.summarize(text, limit=700)

    async def bootstrap(self) -> OrchestrationState:
        max_seq = self.db.scalar(select(func.max(Message.sequence_no)).where(Message.chat_thread_id == self.chat_thread_id)) or 0
        segment, divergence = maybe_start_new_segment(self.db, self.chat_thread_id, self.content_markdown)

        user_message = Message(
            project_id=self.project_id,
            chat_thread_id=self.chat_thread_id,
            segment_id=segment.id,
            role=RoleEnum.user,
            content_markdown=self.content_markdown,
            plain_text_cache=self.content_markdown,
            sequence_no=max_seq + 1,
            model_role=f"segment:{divergence.get('reason')}" if divergence.get('diverged') else None,
        )
        self.db.add(user_message)
        self.db.flush()

        assets = self._load_assets(user_message.id)
        has_image = any(a.mime_type.startswith("image/") for a in assets)
        image_payloads, image_asset_ids = self._encode_image_assets(assets)

        context_hits = retrieve_relevant_context(
            db=self.db,
            chat_thread_id=self.chat_thread_id,
            project_id=self.project_id,
            segment_id=segment.id,
            query=self.content_markdown,
            limit=10,
        )
        packed_context, retrieval_meta = pack_retrieval_context(context_hits)
        context_block = "\n".join(
            [f"asset#{h['asset_id']} chunk#{h['chunk_id']} {h['filename']} score={h['score']}: {h['snippet']}" for h in context_hits]
        )
        needs_reasoning = len(context_block) > 800

        run = OrchestrationRun(
            project_id=self.project_id,
            chat_thread_id=self.chat_thread_id,
            user_message_id=user_message.id,
            status="running",
            graph_name="langgraph_orchestrator_v1",
            started_at=datetime.utcnow(),
            approval_status="pending" if self.require_approval_before_publish else "not_required",
        )
        self.db.add(run)
        self.db.flush()
        self.run = run

        model_name, routing_reason = self.choose_model(
            selected_model_names=self.selected_model_names,
            orchestrator_model_name=self.orchestrator_model_name,
            requires_vision=has_image,
            needs_reasoning=needs_reasoning,
            gpu_enabled=get_gpu_enabled(),
        )
        gpu_enabled = get_gpu_enabled()
        if has_image and needs_reasoning:
            routing_reason = f"{routing_reason}+vision_and_reasoning"
        elif has_image:
            routing_reason = f"{routing_reason}+vision_priority"
        routing_reason = f"{routing_reason}+gpu_enabled={gpu_enabled}"

        parent_summary = ""
        if segment.parent_segment_id:
            parent = self.db.get(ConversationSegment, segment.parent_segment_id)
            if parent:
                parent_summary = parent.topic_summary[:200]

        should_run_specialist = bool(
            has_image
            or "```" in self.content_markdown
            or any(tok in self.content_markdown.lower() for tok in ["code", "python", "typescript", "javascript"])
            or bool(context_hits)
        )

        return {
            "project_id": self.project_id,
            "chat_thread_id": self.chat_thread_id,
            "run_id": run.id,
            "user_message_id": user_message.id,
            "segment_id": segment.id,
            "content_markdown": self.content_markdown,
            "selected_model_names": self.selected_model_names,
            "orchestrator_model_name": self.orchestrator_model_name,
            "require_approval_before_publish": self.require_approval_before_publish,
            "model_name": model_name,
            "routing_reason": routing_reason,
            "gpu_enabled": gpu_enabled,
            "has_image": has_image,
            "image_asset_ids": image_asset_ids,
            "image_payloads": image_payloads,
            "needs_reasoning": needs_reasoning,
            "context_hits": context_hits,
            "packed_context": packed_context,
            "retrieval_meta": retrieval_meta,
            "context_block": context_block,
            "parent_summary_used": bool(parent_summary),
            "step_outputs": [],
            "used_asset_ids": sorted({hit["asset_id"] for hit in context_hits}),
            "used_chunk_ids": [hit["chunk_id"] for hit in context_hits],
            "reviewer_decision": "approve",
            "critic_model": model_name,
            "revised": False,
            "final_text": "",
            "model_role": "final_responder",
            "should_run_specialist": should_run_specialist,
            "should_revise": False,
            "approval_status": "pending" if self.require_approval_before_publish else "not_required",
        }

    def choose_model(self, selected_model_names: list[str], orchestrator_model_name: str | None, requires_vision: bool, needs_reasoning: bool, gpu_enabled: bool) -> tuple[str, str]:
        q = select(ModelRegistry).where(ModelRegistry.enabled.is_(True), ModelRegistry.downloaded.is_(True))
        if selected_model_names:
            q = q.where(ModelRegistry.model_name.in_(selected_model_names))
        rows = self.db.scalars(q.order_by(ModelRegistry.sort_order.asc(), ModelRegistry.model_name.asc())).all()
        if not rows:
            raise ValueError("enabled/downloaded 모델이 없어 오케스트레이션을 실행할 수 없습니다.")
        if orchestrator_model_name:
            chosen = next((m for m in rows if m.model_name == orchestrator_model_name), None)
            if chosen:
                return chosen.model_name, "user_selected_orchestrator_model"
        if not gpu_enabled:
            cpu_safe = [m for m in rows if not m.supports_vision and not m.supports_reasoning]
            if cpu_safe:
                return cpu_safe[0].model_name, "gpu_disabled_cpu_fallback"
        if requires_vision:
            vision = next((m for m in rows if m.supports_vision), None)
            if vision:
                return vision.model_name, "vision_asset_detected"
        if needs_reasoning:
            reasoning = next((m for m in rows if m.supports_reasoning), None)
            if reasoning:
                return reasoning.model_name, "long_context_reasoning"
        return rows[0].model_name, "sort_order_fallback"

    def open_step(self, step_name: str, assigned_role: str, model_name: str | None, input_summary: str, depends_on: list[int] | None = None) -> StepContext:
        step = OrchestrationStep(
            orchestration_run_id=self.run.id,  # type: ignore[arg-type]
            step_name=step_name,
            assigned_role=assigned_role,
            model_name=model_name,
            status="running",
            input_summary=self.summarize(input_summary),
            started_at=datetime.utcnow(),
        )
        self.db.add(step)
        self.db.flush()
        if self.emit_event:
            started_event, _ = step_event_names(step)
            self.emit_event(
                {
                    "event_type": started_event,
                    "run_id": self.run.id,
                    "step_id": step.id,
                    "step_name": step.step_name,
                    "assigned_role": step.assigned_role,
                    "status": "running",
                    "model_name": step.model_name,
                    "retry_count": 0,
                    "approval_status": "pending" if self.require_approval_before_publish else "not_required",
                }
            )
        return StepContext(step=step, depends_on=depends_on or [])

    def close_step(self, ctx: StepContext, output: str, meta: dict[str, Any], retry_count: int = 0) -> int:
        ctx.step.status = "completed"
        ctx.step.output_summary = self.output_summary(output)
        ctx.step.retry_count = retry_count
        ctx.step.step_metadata_json = {
            **meta,
            "depends_on_step_ids": ctx.depends_on,
            "approval_required": self.require_approval_before_publish,
            "approval_status": "pending" if self.require_approval_before_publish else "not_required",
            "retry_count": retry_count,
        }
        ctx.step.ended_at = datetime.utcnow()
        self.db.flush()
        if self.emit_event:
            _, done_event = step_event_names(ctx.step)
            self.emit_event(
                {
                    "event_type": done_event,
                    "run_id": self.run.id,
                    "step_id": ctx.step.id,
                    "step_name": ctx.step.step_name,
                    "assigned_role": ctx.step.assigned_role,
                    "status": "completed",
                    "model_name": ctx.step.model_name,
                    "retry_count": retry_count,
                    "fallback_model_name": meta.get("fallback_model_name"),
                    "fallback_reason": meta.get("fallback_reason"),
                    "approval_status": "pending" if self.require_approval_before_publish else "not_required",
                }
            )
        return ctx.step.id

    async def chat_with_retry(self, model_name: str, prompt: str) -> tuple[str, int, str | None, str | None, str]:
        retry_count = 0
        fallback_model_name = None
        fallback_reason = None
        call_model = model_name
        resp = await self.client.chat(model_name=call_model, messages=[{"role": "user", "content": prompt}])
        output = resp.get("message", {}).get("content") or ""
        if not output.strip():
            retry_count = 1
            resp = await self.client.chat(model_name=call_model, messages=[{"role": "user", "content": prompt}])
            output = resp.get("message", {}).get("content") or ""
        if not output.strip():
            fallback = self.db.scalar(
                select(ModelRegistry)
                .where(ModelRegistry.enabled.is_(True), ModelRegistry.downloaded.is_(True), ModelRegistry.model_name != call_model)
                .order_by(ModelRegistry.sort_order.asc())
            )
            if fallback:
                fallback_model_name = fallback.model_name
                fallback_reason = "empty_response_after_retry"
                call_model = fallback_model_name
                resp = await self.client.chat(model_name=call_model, messages=[{"role": "user", "content": prompt}])
                output = resp.get("message", {}).get("content") or "(empty)"
            else:
                output = "(empty)"
        return output, retry_count, fallback_model_name, fallback_reason, call_model

    @staticmethod
    def review_decision(text: str) -> str:
        lowered = text.lower()
        if "append_missing_points" in lowered:
            return "append_missing_points"
        if "revise" in lowered:
            return "revise"
        return "approve"

    def append_provenance(self, state: OrchestrationState) -> str:
        line = (
            f"[Orchestration Provenance] segment={state['segment_id']}, assets={state['used_asset_ids'] or []}, "
            f"images={state['image_asset_ids'] or []}, chunks={state['used_chunk_ids'] or []}, retrieval_mode={state['retrieval_meta'].get('retrieval_mode')}, ocr_used={state['retrieval_meta'].get('ocr_used')}, "
            f"vision_used={state['has_image']}, routing_reason={state['routing_reason']}, parent_summary_used={state['parent_summary_used']}, "
            f"reviewer_decision={state['reviewer_decision']}, critic_model={state['critic_model']}, revised={state['revised']}, gpu_enabled={state['gpu_enabled']}"
        )
        return f"{state['final_text']}\n\n{line}"

    def mark_approval_pending(self, state: OrchestrationState) -> None:
        self.run.status = "approval_pending"  # type: ignore[union-attr]
        self.run.ended_at = None  # type: ignore[union-attr]
        pending_payload = {
            "project_id": state["project_id"],
            "chat_thread_id": state["chat_thread_id"],
            "segment_id": state["segment_id"],
            "content_markdown": state["final_text"],
            "model_name": state["model_name"],
            "model_role": state["model_role"],
            "approval_status": "pending",
        }
        self.run.approval_status = "pending"  # type: ignore[union-attr]
        self.run.pending_payload_json = pending_payload  # type: ignore[union-attr]
        if self.emit_event:
            self.emit_event({"event_type": "approval_pending", "run_id": self.run.id, "status": "approval_pending", "approval_status": "pending"})

    def finalize_run_status(self, status: str) -> None:
        self.run.status = status  # type: ignore[union-attr]
        self.run.ended_at = datetime.utcnow()  # type: ignore[union-attr]

    def publish_now(self, state: OrchestrationState) -> Message:
        max_seq = self.db.scalar(select(func.max(Message.sequence_no)).where(Message.chat_thread_id == state["chat_thread_id"])) or 0
        final_text = state["final_text"]
        msg = Message(
            project_id=state["project_id"],
            chat_thread_id=state["chat_thread_id"],
            segment_id=state["segment_id"],
            role=RoleEnum.assistant,
            content_markdown=final_text,
            plain_text_cache=final_text,
            sequence_no=max_seq + 1,
            model_name=state.get("model_name"),
            model_role=state.get("model_role"),
        )
        self.db.add(msg)
        self.db.flush()
        artifact = create_ai_generated_artifact(
            self.db,
            project_id=state["project_id"],
            chat_thread_id=state["chat_thread_id"],
            message_id=msg.id,
            content=final_text,
            model_name=state.get("model_name"),
            model_role=state.get("model_role"),
            orchestration_run_id=self.run.id,  # type: ignore[union-attr]
        )
        msg.content_markdown = f"{msg.content_markdown}\n[Generated artifact] #{artifact.id}:{artifact.original_filename}"
        msg.plain_text_cache = msg.content_markdown
        self.run.final_message_id = msg.id  # type: ignore[union-attr]
        self.finalize_run_status("completed")
        self.run.approval_status = "approved" if self.require_approval_before_publish else self.run.approval_status  # type: ignore[union-attr]
        self.run.pending_payload_json = None  # type: ignore[union-attr]
        self.run.approval_decided_at = datetime.utcnow() if self.require_approval_before_publish else self.run.approval_decided_at  # type: ignore[union-attr]
        update_segment_summary(self.db, state["segment_id"])
        return msg

    def _load_assets(self, message_id: int) -> list[Asset]:
        assets: list[Asset] = []
        if self.message_asset_ids:
            assets = self.db.scalars(
                select(Asset).where(Asset.id.in_(self.message_asset_ids), Asset.chat_thread_id == self.chat_thread_id)
            ).all()
            for asset in assets:
                asset.message_id = message_id
        return assets

    def _encode_image_assets(self, assets: list[Asset]) -> tuple[list[str], list[int]]:
        images: list[str] = []
        image_ids: list[int] = []
        for asset in assets:
            if not asset.mime_type.startswith("image/"):
                continue
            raw = Path(asset.stored_path).read_bytes()
            images.append(base64.b64encode(raw).decode("utf-8"))
            image_ids.append(asset.id)
        return images, image_ids
