from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, replace
from typing import Any, Literal, Protocol

from conversation_agent_mq_mock.messages import (
    BusinessDataStep,
    IncomingConversationMessage,
    KweaverStep,
    OutgoingMqMessage,
    build_business_data_message,
    build_core_status_message,
    build_kweaver_message,
    AgUiStep,
)
from conversation_agent_mq_mock.scenario import (
    build_scenario,
    should_fail,
    should_reject,
    should_replay,
)
from conversation_agent_mq_mock.settings import Settings
from conversation_agent_mq_mock.state import SessionTracker, core_agent_run_id

logger = logging.getLogger(__name__)

RunMode = Literal["business_data", "kweaver", "both"]


class MessagePublisher(Protocol):
    async def publish(self, message: OutgoingMqMessage) -> None:
        raise NotImplementedError


class AgentMqMockRunner:
    def __init__(
        self,
        *,
        settings: Settings,
        publisher: MessagePublisher,
        tracker: SessionTracker | None = None,
        mode: RunMode = "business_data",
    ) -> None:
        self._settings = settings
        self._publisher = publisher
        self._tracker = tracker or SessionTracker()
        self._mode = mode

    async def handle_body(self, body: dict[str, Any]) -> None:
        incoming = IncomingConversationMessage.from_body(body)
        if not self._tracker.mark_seen(incoming.event_id):
            logger.info(
                "mock_duplicate_input_skipped",
                extra={
                    "event_id": incoming.event_id,
                    "conversation_id": incoming.conversation_id,
                    "message_id": incoming.message_id,
                },
            )
            return

        run_id = core_agent_run_id(incoming.conversation_id, incoming.message_id)
        logger.info(
            "mock_input_accepted",
            extra={
                "event_id": incoming.event_id,
                "conversation_id": incoming.conversation_id,
                "message_id": incoming.message_id,
                "core_agent_run_id": run_id,
            },
        )

        if should_reject(incoming):
            await self._publisher.publish(
                build_core_status_message(
                    incoming,
                    kind="rejected",
                    core_agent_run_id=run_id,
                    now_ms=_now_ms(),
                    status_queue=self._settings.core_status_queue,
                    error_code="UNSUPPORTED_TASK",
                    error_message="Mock core agent rejected this unsupported task.",
                    retryable=False,
                )
            )
            return

        await self._publisher.publish(
            build_core_status_message(
                incoming,
                kind="accepted",
                core_agent_run_id=run_id,
                now_ms=_now_ms(),
                status_queue=self._settings.core_status_queue,
            )
        )
        await _sleep_ms(self._settings.delay_ms)

        if should_fail(incoming):
            await self._publisher.publish(
                build_core_status_message(
                    incoming,
                    kind="failed",
                    core_agent_run_id=run_id,
                    now_ms=_now_ms(),
                    status_queue=self._settings.core_status_queue,
                    error_code="CORE_AGENT_MOCK_FAILURE",
                    error_message="Mock core agent generated a simulated failure.",
                    retryable=True,
                )
            )
            return

        scenario = build_scenario(incoming, core_agent_run_id=run_id)

        if self._mode in ("business_data", "both"):
            await self._publish_business_data_steps(incoming, scenario, run_id)

        if self._mode in ("kweaver", "both"):
            await self._publish_kweaver_steps(incoming, scenario, run_id)

        await self._publisher.publish(
            build_core_status_message(
                incoming,
                kind="completed",
                core_agent_run_id=run_id,
                now_ms=_now_ms(),
                status_queue=self._settings.core_status_queue,
            )
        )
        logger.info(
            "mock_run_completed",
            extra={
                "conversation_id": incoming.conversation_id,
                "message_id": incoming.message_id,
                "core_agent_run_id": run_id,
                "mode": self._mode,
            },
        )

    async def _publish_business_data_steps(
        self,
        incoming: IncomingConversationMessage,
        scenario: Any,
        run_id: str,
    ) -> None:
        steps = scenario.business_data_steps or _convert_ag_ui_steps(
            scenario.ag_ui_steps, scenario_id=scenario.scenario_id
        )
        sequence_numbers = self._tracker.reserve_ag_ui_sequences(
            incoming.conversation_id,
            len(steps),
        )
        replay_output = should_replay(incoming)
        for step, sequence in zip(steps, sequence_numbers, strict=True):
            message = build_business_data_message(
                incoming,
                step=replace(step, sequence=sequence),
                now_ms=_now_ms(),
                exchange=self._settings.bizdata_exchange,
                routing_key=self._settings.bizdata_routing_key,
            )
            await self._publisher.publish(message)
            logger.info(
                "mock_business_data_published",
                extra={
                    "conversation_id": incoming.conversation_id,
                    "message_id": incoming.message_id,
                    "sequence": step.sequence,
                    "schema_type": step.schema_type,
                    "scenario_id": scenario.scenario_id,
                },
            )
            if replay_output:
                await self._publisher.publish(message)
                logger.info(
                    "mock_business_data_replayed",
                    extra={
                        "conversation_id": incoming.conversation_id,
                        "message_id": incoming.message_id,
                        "sequence": step.sequence,
                        "scenario_id": scenario.scenario_id,
                    },
                )
            await _sleep_ms(self._settings.delay_ms)

    async def _publish_kweaver_steps(
        self,
        incoming: IncomingConversationMessage,
        scenario: Any,
        run_id: str,
    ) -> None:
        kweaver_steps = _convert_ag_ui_to_kweaver(scenario.ag_ui_steps, run_id=run_id)
        for chunk_index, kw_step in enumerate(kweaver_steps):
            message = build_kweaver_message(
                incoming,
                step=KweaverStep(
                    sequence=kw_step.sequence,
                    content=kw_step.content,
                    kweaver_event=kw_step.kweaver_event,
                    chunk_index=chunk_index,
                ),
                core_agent_run_id=run_id,
                now_ms=_now_ms(),
                exchange=self._settings.kweaver_exchange,
                routing_key=self._settings.kweaver_routing_key,
            )
            await self._publisher.publish(message)
            logger.info(
                "mock_kweaver_published",
                extra={
                    "conversation_id": incoming.conversation_id,
                    "message_id": incoming.message_id,
                    "sequence": kw_step.sequence,
                    "scenario_id": scenario.scenario_id,
                    "chunk_index": chunk_index,
                },
            )
            await _sleep_ms(self._settings.delay_ms)


def decode_json_body(raw: bytes) -> dict[str, Any]:
    body = json.loads(raw.decode("utf-8"))
    if not isinstance(body, dict):
        raise ValueError("MQ body must be a JSON object")
    return body


async def _sleep_ms(delay_ms: int) -> None:
    if delay_ms > 0:
        await asyncio.sleep(delay_ms / 1000)


def _now_ms() -> int:
    return int(time.time() * 1000)


_SCHEMA_TYPE_BY_SCENARIO: dict[str, str] = {
    "thought": "text_message",
    "tool_call": "text_message",
    "progress": "progress_report",
    "clarifying": "clarification_request",
    "restore": "plan_candidates",
    "capacity": "capacity_forecast",
    "attachment": "attachment_list",
    "visible_error": "progress_report",
    "doc_candidate_compare": "plan_candidates",
    "doc_report_detail": "report_detail",
    "incremental": "incremental_update",
    "text_only": "text_message",
    "general": "text_message",
}


def _convert_ag_ui_steps(
    steps: tuple[AgUiStep, ...],
    *,
    scenario_id: str = "",
) -> tuple[BusinessDataStep, ...]:
    result_schema_type = _SCHEMA_TYPE_BY_SCENARIO.get(scenario_id, "text_message")
    converted: list[BusinessDataStep] = []
    for step in steps:
        schema_type, data = _extract_business_data(step, result_schema_type=result_schema_type)
        converted.append(
            BusinessDataStep(
                sequence=step.sequence,
                content=step.content,
                schema_type=schema_type,
                data=data,
            )
        )
    return tuple(converted)


def _extract_business_data(
    step: AgUiStep,
    *,
    result_schema_type: str = "text_message",
) -> tuple[str, dict[str, Any]]:
    for event in step.events:
        if event.get("type") != "ACTIVITY_SNAPSHOT":
            continue
        content = event.get("content")
        if not isinstance(content, dict):
            continue
        meta = content.get("meta")
        if not isinstance(meta, dict):
            continue
        intent = meta.get("intent")
        if intent == "result":
            return (result_schema_type, {"heading": step.content, "candidates": [{"candidate_option_id": "a", "title": step.content, "summary": step.content, "recommendation_level": "recommended", "risk_level": "medium"}]})
        if intent == "progress":
            return ("progress_report", {"heading": step.content, "stage": "processing", "steps": [{"step_id": "1", "label": step.content, "status": "in_progress"}]})
        if intent == "clarification":
            return ("clarification_request", {"question": step.content, "options": [{"option_id": "1", "label": step.content}]})
        if intent == "tool_call":
            return ("text_message", {"text": step.content})
        if intent == "thought":
            return ("text_message", {"text": step.content})
        if intent == "error":
            return ("progress_report", {"heading": step.content, "stage": "failed", "steps": [{"step_id": "1", "label": step.content, "status": "failed"}], "error": {"message": step.content, "tone": "danger"}})
    for event in step.events:
        if event.get("type") == "ACTIVITY_DELTA":
            patch = event.get("content", {}).get("patch", [])
            return ("incremental_update", {"target_block_id": "unknown", "patch": patch})
        if event.get("type") in ("TEXT_MESSAGE_START", "TEXT_MESSAGE_CONTENT", "TEXT_MESSAGE_END"):
            return ("text_message", {"text": step.content})
    return ("text_message", {"text": step.content})


@dataclass(frozen=True, slots=True)
class _KweaverStepData:
    sequence: int
    content: str
    kweaver_event: dict[str, Any]


def _convert_ag_ui_to_kweaver(
    steps: tuple[AgUiStep, ...],
    *,
    run_id: str,
) -> list[_KweaverStepData]:
    """Convert AG-UI layout-tree events to KWeaver streaming format.

    Each AgUiStep's events are wrapped into a single KWeaver payload
    that the conversation service's KweaverToAgUiConverter can process.
    """
    result: list[_KweaverStepData] = []
    for step in steps:
        progress_items: list[dict[str, Any]] = []
        answer_text: str | None = None
        finished = False

        for event in step.events:
            event_type = event.get("type")
            if event_type == "ACTIVITY_SNAPSHOT":
                content = event.get("content")
                if isinstance(content, dict):
                    meta = content.get("meta")
                    if isinstance(meta, dict):
                        intent = meta.get("intent")
                        terminal = meta.get("terminal", False)
                        if terminal:
                            finished = True
                        ui = content.get("ui")
                        if isinstance(ui, dict) and intent in ("thought", "tool_call"):
                            paragraphs = _extract_paragraph_text(ui)
                            if paragraphs:
                                answer_text = paragraphs

            elif event_type == "TEXT_MESSAGE_CONTENT":
                delta = event.get("delta")
                if isinstance(delta, str):
                    answer_text = (answer_text or "") + delta

        kweaver_event: dict[str, Any] = {
            "key": f"step-{step.sequence}",
            "content": {},
        }
        if answer_text:
            kweaver_event["content"]["answer"] = {"answer": {"text": answer_text}}
        if progress_items:
            kweaver_event["content"]["progress"] = progress_items
        if finished:
            kweaver_event["finished"] = True

        result.append(_KweaverStepData(
            sequence=step.sequence,
            content=step.content,
            kweaver_event=kweaver_event,
        ))
    return result


def _extract_paragraph_text(ui: dict[str, Any]) -> str | None:
    """Extract text from a paragraph node in a layout-tree."""
    if ui.get("type") == "paragraph":
        props = ui.get("props")
        if isinstance(props, dict):
            return props.get("text")
    for child in ui.get("children", []):
        result = _extract_paragraph_text(child)
        if result:
            return result
    return None
