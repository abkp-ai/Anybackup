import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from time import time
from typing import Any

from app.application.commands.agent_events import CoreAgentStatusEventCommand
from app.application.models.conversation import (
    ConversationMessageRecord,
    ConversationStatusEventRecord,
)
from app.application.ports.id_generator import IdGenerator
from app.application.ports.unit_of_work import UnitOfWork
from app.domain.message import ConversationMessage, MessageStatus
from app.domain.shared.errors import DomainError, ErrorReason

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CoreAgentStatusEventResult:
    idempotent: bool
    status_event: ConversationStatusEventRecord | None = None


class CoreAgentStatusEventHandler:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], UnitOfWork],
        id_generator: IdGenerator,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._id_generator = id_generator

    async def handle(self, command: CoreAgentStatusEventCommand) -> CoreAgentStatusEventResult:
        logger.info(
            "core_agent_status_event_handle_enter",
            extra={
                "event_id": command.event_id,
                "event_type": command.event_type,
                "conversation_id": command.conversation_id,
                "message_id": command.message_id,
            },
        )
        async with self._unit_of_work_factory() as unit_of_work:
            if await unit_of_work.status_events.exists_by_core_event_id(command.event_id):
                logger.info(
                    "core_agent_status_event_idempotent_hit",
                    extra={"event_id": command.event_id},
                )
                return CoreAgentStatusEventResult(idempotent=True)

            conversation = await unit_of_work.conversations.get_record_by_id(
                command.conversation_id
            )
            if conversation is None:
                logger.info(
                    "core_agent_status_event_target_missing",
                    extra={
                        "event_id": command.event_id,
                        "conversation_id": command.conversation_id,
                        "message_id": command.message_id,
                    },
                )
                raise DomainError(ErrorReason.CONVERSATION_NOT_FOUND)
            message = await _resolve_target_message(unit_of_work, conversation, command)
            if message is None:
                logger.info(
                    "core_agent_status_event_target_missing",
                    extra={
                        "event_id": command.event_id,
                        "conversation_id": command.conversation_id,
                        "message_id": command.message_id,
                    },
                )
                raise DomainError(ErrorReason.CONVERSATION_NOT_FOUND)
            if message.conversation_id != conversation.conversation_id:
                raise DomainError(ErrorReason.CHILD_CONVERSATION_MISMATCH)

            now_ms = command.occurred_time or _current_time_ms()
            event_kind = _event_kind(command.event_type)
            turn_id = message.turn_id
            if event_kind == "accepted":
                if message.status in {MessageStatus.RESPONDED, MessageStatus.FAILED}:
                    target_message = message
                    target_active_run_id = conversation.active_run_id
                    event_type = "message.updated"
                    title = "Core Agent accepted"
                    detail = (
                        "Core Agent accepted after the user message already reached "
                        "a terminal state"
                    )
                    payload = {
                        **_accepted_payload(command),
                        "message_status": target_message.status.value,
                        "late": True,
                    }
                else:
                    target_message = _transition_message(message, MessageStatus.PROCESSING, now_ms)
                    target_active_run_id = _core_run_id(command, turn_id)
                    event_type = "message.updated"
                    title = "Core Agent accepted"
                    detail = "Core Agent accepted the user message"
                    payload = _accepted_payload(command)
            elif event_kind == "completed":
                target_message = _transition_message(message, MessageStatus.RESPONDED, now_ms)
                target_active_run_id = None
                event_type = "message.updated"
                title = "Core Agent completed"
                detail = "Core Agent run completed"
                payload = _completed_payload(command)
            elif event_kind in {"rejected", "failed"}:
                error_payload = _error_payload(command, event_kind)
                target_message = replace(
                    _transition_message(message, MessageStatus.FAILED, now_ms),
                    error_code=error_payload["error_code"],
                )
                target_active_run_id = None
                event_type = "error"
                title = "Core Agent failed"
                detail = str(error_payload.get("error_message") or "Core Agent returned failure")
                payload = error_payload
            else:
                raise ValueError(f"unsupported core agent event_type: {command.event_type}")

            target_conversation = (
                conversation
                if target_active_run_id == conversation.active_run_id
                else replace(
                    conversation,
                    active_run_id=target_active_run_id,
                    updated_time=now_ms,
                    last_active_time=now_ms,
                )
            )
            sequence = await unit_of_work.status_events.next_sequence(command.conversation_id)
            primary_event = ConversationStatusEventRecord(
                status_event_id=self._id_generator.next_id(),
                conversation_id=command.conversation_id,
                message_id=target_message.message_id,
                turn_id=turn_id,
                event_type=event_type,
                sequence=sequence,
                message_status=target_message.status,
                title=title,
                detail=detail,
                payload={
                    "core_event_id": command.event_id,
                    "core_event_type": command.event_type,
                    "core_event_version": command.event_version,
                    **payload,
                },
                trace_id=command.trace_id,
                correlation_id=command.correlation_id,
                created_time=now_ms,
                updated_time=now_ms,
            )
            if target_conversation != conversation:
                await unit_of_work.conversations.update_record(target_conversation)
            if target_message != message:
                await unit_of_work.messages.update(target_message)
            await unit_of_work.status_events.add(primary_event)
            logger.info(
                "core_agent_status_event_persisted",
                extra={
                    "event_id": command.event_id,
                    "status_event_id": primary_event.status_event_id,
                    "message_status": target_message.status.value,
                    "active_run_id": target_active_run_id,
                },
            )
            return CoreAgentStatusEventResult(
                idempotent=False,
                status_event=primary_event,
            )


def _transition_message(
    message: ConversationMessageRecord,
    target: MessageStatus,
    now_ms: int,
) -> ConversationMessageRecord:
    domain_message = ConversationMessage(
        message_id=message.message_id,
        conversation_id=message.conversation_id,
        status=message.status,
    )
    if domain_message.status is not target:
        domain_message.transition_to(target)
    return replace(message, status=domain_message.status, updated_time=now_ms)


def _event_kind(event_type: str) -> str:
    return event_type.rsplit(".", maxsplit=1)[-1]


def _accepted_payload(command: CoreAgentStatusEventCommand) -> dict[str, Any]:
    accepted = _section(command.payload, "accepted")
    content = command.payload.get("content")
    return {
        "input_event_id": accepted.get("input_event_id"),
        "core_agent_run_id": accepted.get("core_agent_run_id"),
        "estimated_status": accepted.get("estimated_status", "processing"),
        "content": content if isinstance(content, str) and content else None,
    }


def _completed_payload(command: CoreAgentStatusEventCommand) -> dict[str, Any]:
    completed = _section(command.payload, "completed")
    content = command.payload.get("content")
    return {
        "core_agent_run_id": completed.get("core_agent_run_id"),
        "content": content if isinstance(content, str) and content else None,
    }


def _core_run_id(command: CoreAgentStatusEventCommand, fallback_turn_id: int | None) -> str | None:
    accepted = _section(command.payload, "accepted")
    run_id = accepted.get("core_agent_run_id")
    if isinstance(run_id, str) and run_id:
        return run_id
    return str(fallback_turn_id) if fallback_turn_id is not None else None


def _error_payload(command: CoreAgentStatusEventCommand, section_name: str) -> dict[str, Any]:
    section = _section(command.payload, section_name)
    fallback_code = "CORE_AGENT_REJECTED" if section_name == "rejected" else "CORE_AGENT_FAILED"
    content = command.payload.get("content")
    return {
        "error_code": str(section.get("code") or fallback_code),
        "error_message": section.get("message")
        if isinstance(section.get("message"), str)
        else content,
        "retryable": bool(section.get("retryable", False)),
    }


def _section(payload: dict[str, Any], section_name: str) -> dict[str, Any]:
    section = payload.get(section_name)
    if section is None:
        return {}
    if not isinstance(section, dict):
        raise ValueError(f"core agent {section_name} payload must be an object")
    return section


async def _resolve_target_message(
    unit_of_work: UnitOfWork,
    conversation: Any,
    command: CoreAgentStatusEventCommand,
) -> ConversationMessageRecord | None:
    candidate_ids = []
    if command.message_id is not None:
        candidate_ids.append(command.message_id)
    if conversation.active_run_id is not None and conversation.active_run_id.isdigit():
        candidate_ids.append(int(conversation.active_run_id))

    seen: set[int] = set()
    for message_id in candidate_ids:
        if message_id in seen:
            continue
        seen.add(message_id)
        message = await unit_of_work.messages.get_by_id(message_id)
        if message is not None and message.role == "user":
            return message

    messages = await unit_of_work.messages.list_by_conversation(
        conversation.conversation_id,
        limit=100,
    )
    for message in messages:
        if message.role != "user":
            continue
        if message.status in {
            MessageStatus.PERSISTED,
            MessageStatus.PUBLISHED,
            MessageStatus.PROCESSING,
            MessageStatus.RESPONDED,
        }:
            return message
    return None


def _current_time_ms() -> int:
    return int(time() * 1000)
