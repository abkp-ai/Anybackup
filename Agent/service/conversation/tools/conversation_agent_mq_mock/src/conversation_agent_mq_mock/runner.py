from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import replace
from typing import Any, Protocol

from conversation_agent_mq_mock.messages import (
    BusinessDataStep,
    IncomingConversationMessage,
    OutgoingMqMessage,
    build_business_data_message,
    build_core_status_message,
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
    ) -> None:
        self._settings = settings
        self._publisher = publisher
        self._tracker = tracker or SessionTracker()

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
        steps = scenario.business_data_steps or _convert_ag_ui_steps(scenario.ag_ui_steps)
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
                exchange=self._settings.ag_ui_exchange,
                routing_key=self._settings.ag_ui_routing_key,
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


def _convert_ag_ui_steps(steps: tuple[AgUiStep, ...]) -> tuple[BusinessDataStep, ...]:
    converted: list[BusinessDataStep] = []
    for step in steps:
        schema_type, data = _extract_business_data(step)
        converted.append(
            BusinessDataStep(
                sequence=step.sequence,
                content=step.content,
                schema_type=schema_type,
                data=data,
            )
        )
    return tuple(converted)


def _extract_business_data(step: AgUiStep) -> tuple[str, dict[str, Any]]:
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
            return ("plan_candidates", {"heading": step.content, "candidates": [{"candidate_option_id": "a", "title": step.content, "summary": step.content, "recommendation_level": "recommended", "risk_level": "medium"}]})
        if intent == "progress":
            return ("progress_report", {"heading": step.content, "stage": "processing", "steps": [{"step_id": "1", "label": step.content, "status": "running"}]})
        if intent == "clarification":
            return ("clarification_request", {"question": step.content, "options": [{"option_id": "1", "label": step.content}]})
        if intent == "tool_call":
            return ("text_message", {"text": step.content})
    for event in step.events:
        if event.get("type") == "ACTIVITY_DELTA":
            patch = event.get("content", {}).get("patch", [])
            return ("incremental_update", {"target_block_id": "unknown", "patch": patch})
        if event.get("type") in ("TEXT_MESSAGE_START", "TEXT_MESSAGE_CONTENT", "TEXT_MESSAGE_END"):
            return ("text_message", {"text": step.content})
    return ("text_message", {"text": step.content})
