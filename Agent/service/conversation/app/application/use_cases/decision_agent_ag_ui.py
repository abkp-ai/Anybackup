import hashlib
import json
import logging
from collections.abc import Callable
from dataclasses import replace
from time import time
from typing import Any

from app.application.commands.agent_events import DecisionAgentAgUiEventCommand
from app.application.models.conversation import ConversationStatusEventRecord
from app.application.models.writeback import (
    ConversationWritebackIdempotencyRecord,
    DecisionAgentAgUiEventResult,
)
from app.application.ports.id_generator import IdGenerator
from app.application.ports.unit_of_work import UnitOfWork
from app.domain.conversation import ConversationStatus
from app.domain.shared.errors import DomainError, ErrorReason

logger = logging.getLogger(__name__)

_TERMINAL_EVENT_TYPES = frozenset({"RUN_FINISHED", "RUN_ERROR"})
_ALLOWED_EVENT_TYPES = frozenset(
    {
        "RUN_STARTED",
        "RUN_FINISHED",
        "RUN_ERROR",
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_CONTENT",
        "TEXT_MESSAGE_END",
        "THINKING_START",
        "THINKING_TEXT_MESSAGE_CONTENT",
        "THINKING_END",
        "STATE_SNAPSHOT",
        "STATE_DELTA",
        "ACTIVITY_SNAPSHOT",
        "ACTIVITY_DELTA",
        "TOOL_CALL_START",
        "TOOL_CALL_ARGS",
        "TOOL_CALL_END",
        "TOOL_CALL_RESULT",
        "RAW",
    }
)


class DecisionAgentAgUiEventHandler:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], UnitOfWork],
        id_generator: IdGenerator,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._id_generator = id_generator

    async def handle(
        self,
        command: DecisionAgentAgUiEventCommand,
    ) -> DecisionAgentAgUiEventResult:
        logger.info(
            "decision_agent_ag_ui_event_handle_enter",
            extra={
                "event_id": command.event_id,
                "conversation_id": command.conversation_id,
                "run_id": command.ag_ui_event.get("runId"),
                "sequence": command.sequence,
            },
        )
        ag_ui_event = _validate_ag_ui_event(command)
        request_hash = calculate_ag_ui_event_hash(command)
        output_id = _ag_ui_output_id(
            command.conversation_id,
            command.turn_id,
            command.message_id,
            command.sequence,
        )

        async with self._unit_of_work_factory() as unit_of_work:
            existing = await unit_of_work.writebacks.get_by_key(command.event_id)
            if existing is not None:
                return DecisionAgentAgUiEventResult(
                    result_status=existing.result_status,
                    idempotent=True,
                    reject_code=existing.reject_code,
                    reject_reason=existing.reject_reason,
                )

            conversation = await unit_of_work.conversations.get_record_by_id(
                command.conversation_id
            )
            if conversation is None:
                raise DomainError(ErrorReason.CONVERSATION_NOT_FOUND)
            source_message = await unit_of_work.messages.get_by_id(command.turn_id)
            if (
                source_message is None
                or source_message.conversation_id != command.conversation_id
                or source_message.role != "user"
            ):
                raise DomainError(ErrorReason.CHILD_CONVERSATION_MISMATCH)

            reject_reason = _conversation_reject_reason(conversation)
            if reject_reason is not None:
                await _persist_rejection(
                    unit_of_work,
                    id_generator=self._id_generator,
                    command=command,
                    output_id=output_id,
                    request_hash=request_hash,
                    reject_reason=reject_reason,
                )
                await unit_of_work.commit()
                raise DomainError(reject_reason)

            sequence_record = await unit_of_work.writebacks.get_by_conversation_output_id(
                conversation_id=command.conversation_id,
                output_id=output_id,
            )
            max_sequence = await unit_of_work.writebacks.max_accepted_output_sequence(
                command.conversation_id,
                turn_id=command.turn_id,
                message_id=command.message_id,
            )
            is_update = sequence_record is not None
            if not is_update and command.sequence != max_sequence + 1:
                await _persist_rejection(
                    unit_of_work,
                    id_generator=self._id_generator,
                    command=command,
                    output_id=output_id,
                    request_hash=request_hash,
                    reject_reason=ErrorReason.CONVERSATION_WRITEBACK_STALE,
                )
                await unit_of_work.commit()
                raise DomainError(ErrorReason.CONVERSATION_WRITEBACK_STALE)

            now_ms = command.occurred_time or _current_time_ms()
            event_type = str(ag_ui_event["type"])
            updated_conversation = replace(
                conversation,
                active_run_id=None
                if event_type in _TERMINAL_EVENT_TYPES
                else str(ag_ui_event["runId"]),
                updated_time=now_ms,
                last_active_time=now_ms,
            )
            if updated_conversation != conversation:
                await unit_of_work.conversations.update_record(updated_conversation)

            status_event = ConversationStatusEventRecord(
                status_event_id=self._id_generator.next_id(),
                conversation_id=command.conversation_id,
                message_id=command.message_id,
                turn_id=command.turn_id,
                event_type=event_type,
                sequence=await unit_of_work.status_events.next_sequence(
                    command.conversation_id
                ),
                title=event_type,
                detail=None,
                payload=ag_ui_event,
                trace_id=command.trace_id,
                correlation_id=command.correlation_id,
                created_time=now_ms,
                updated_time=now_ms,
            )
            idempotency = ConversationWritebackIdempotencyRecord(
                writeback_id=self._id_generator.next_id(),
                idempotency_key=command.event_id,
                conversation_id=command.conversation_id,
                output_id=output_id,
                request_hash=request_hash,
                result_status="accepted",
                result_message_id=None,
                trace_id=command.trace_id,
                correlation_id=command.correlation_id,
                created_time=now_ms,
                updated_time=now_ms,
            )

            await unit_of_work.status_events.add(status_event)
            await unit_of_work.writebacks.add(idempotency)
            await unit_of_work.commit()
            logger.info(
                "decision_agent_ag_ui_event_persisted",
                extra={
                    "event_id": command.event_id,
                    "status_event_id": status_event.status_event_id,
                    "event_type": event_type,
                },
            )
            return DecisionAgentAgUiEventResult(
                result_status="accepted",
                idempotent=False,
                conversation=updated_conversation,
                status_event=status_event,
            )


def calculate_ag_ui_event_hash(command: DecisionAgentAgUiEventCommand) -> str:
    body = {
        "event_id": command.event_id,
        "event_type": command.event_type,
        "source_service": command.source_service,
        "conversation_id": command.conversation_id,
        "turn_id": command.turn_id,
        "message_id": command.message_id,
        "sequence": command.sequence,
        "ag_ui_event": command.ag_ui_event,
        "occurred_time": command.occurred_time,
    }
    encoded = json.dumps(body, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


async def _persist_rejection(
    unit_of_work: UnitOfWork,
    *,
    id_generator: IdGenerator,
    command: DecisionAgentAgUiEventCommand,
    output_id: str,
    request_hash: str,
    reject_reason: ErrorReason,
    reject_detail: str | None = None,
) -> None:
    now_ms = command.occurred_time or _current_time_ms()
    await unit_of_work.writebacks.add(
        ConversationWritebackIdempotencyRecord(
            writeback_id=id_generator.next_id(),
            idempotency_key=command.event_id,
            conversation_id=command.conversation_id,
            output_id=output_id,
            request_hash=request_hash,
            result_status="rejected",
            reject_code=reject_reason.value,
            reject_reason=reject_detail or reject_reason.value,
            trace_id=command.trace_id,
            correlation_id=command.correlation_id,
            created_time=now_ms,
            updated_time=now_ms,
        )
    )


def _conversation_reject_reason(conversation: Any) -> ErrorReason | None:
    if conversation.status is ConversationStatus.ARCHIVED:
        return ErrorReason.CONVERSATION_ARCHIVED
    if conversation.status is ConversationStatus.EXPIRED:
        return ErrorReason.CONVERSATION_EXPIRED
    return None


def _validate_ag_ui_event(command: DecisionAgentAgUiEventCommand) -> dict[str, Any]:
    event = dict(command.ag_ui_event)
    event_type = event.get("type")
    if event_type not in _ALLOWED_EVENT_TYPES:
        raise ValueError("AG-UI event type is unsupported")
    if str(event.get("threadId")) != str(command.conversation_id):
        raise ValueError("AG-UI threadId must match conversation_id")
    run_id = event.get("runId")
    if not isinstance(run_id, str) or not run_id:
        raise ValueError("AG-UI runId must be a non-empty string")
    event_sequence = event.get("sequence")
    if event_sequence is not None and int(event_sequence) != command.sequence:
        raise ValueError("AG-UI sequence must match MQ payload sequence")
    if event_type in {"RUN_STARTED", "RUN_FINISHED", "RUN_ERROR"}:
        event["threadId"] = str(command.conversation_id)
    if event_type == "STATE_SNAPSHOT" and "state" not in event:
        raise ValueError("STATE_SNAPSHOT must use state")
    if "snapshot" in event:
        raise ValueError("AG-UI events must not use snapshot")
    if event_type == "TOOL_CALL_RESULT":
        result = event.get("result")
        if not isinstance(result, dict):
            raise ValueError("TOOL_CALL_RESULT.result must be an object")
        if "approved" not in result and "approvalStatus" not in result:
            raise ValueError("TOOL_CALL_RESULT.result must contain approval audit fields")
    _reject_rich_payload(event)
    return event


def _reject_rich_payload(value: object) -> None:
    if isinstance(value, dict):
        if "rich_payload" in value:
            raise ValueError("rich_payload is not an SSE wire-format field")
        for child in value.values():
            _reject_rich_payload(child)
    elif isinstance(value, list):
        for child in value:
            _reject_rich_payload(child)


def _ag_ui_output_id(conversation_id: int, turn_id: int, message_id: int, sequence: int) -> str:
    return f"agui:{conversation_id}:{turn_id}:{message_id}:{sequence}"


def _current_time_ms() -> int:
    return int(time() * 1000)
