import logging
from collections.abc import Callable
from dataclasses import replace
from time import time

from app.application.commands.conversation import CreateConversationCommand, SendUserMessageCommand
from app.application.models.conversation import (
    AuthenticatedUser,
    ConversationDetailResult,
    ConversationListQuery,
    ConversationListResult,
    ConversationMessageListQuery,
    ConversationMessageListResult,
    ConversationMessageRecord,
    ConversationRecord,
    ConversationStatusEventListResult,
    ConversationStatusEventRecord,
    MessageAcceptedResult,
    MqOutboxRecord,
)
from app.application.ports.id_generator import IdGenerator
from app.application.ports.unit_of_work import UnitOfWork
from app.application.use_cases.access import ensure_conversation_owner
from app.domain.conversation import Conversation, ConversationStatus
from app.domain.message import MessageStatus
from app.domain.shared.errors import DomainError, ErrorReason
from app.domain.shared.redaction import RedactionAction, RedactionPolicy

logger = logging.getLogger(__name__)
_redaction_policy = RedactionPolicy()


class CreateConversationHandler:
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
        command: CreateConversationCommand,
        user: AuthenticatedUser,
    ) -> MessageAcceptedResult:
        logger.info(
            "conversation_create_enter",
            extra={
                "user_id": user.user_id,
                "has_idempotency_key": command.idempotency_key is not None,
                "request_id": command.request_id,
            },
        )
        async with self._unit_of_work_factory() as unit_of_work:
            if command.idempotency_key is not None:
                existing = await unit_of_work.messages.get_by_idempotency_key(
                    command.idempotency_key
                )
                if existing is not None:
                    logger.info(
                        "conversation_create_idempotent_hit",
                        extra={
                            "conversation_id": existing.conversation_id,
                            "message_id": existing.message_id,
                            "request_id": command.request_id,
                        },
                    )
                    return await _load_message_accepted_result(unit_of_work, existing, user)

            _ensure_user_text_allowed(command.initial_message_content)
            now_ms = _current_time_ms()
            conversation_id = self._id_generator.next_id()
            message_id = self._id_generator.next_id()
            turn_id = message_id
            status_event_id = self._id_generator.next_id()
            outbox_id = self._id_generator.next_id()
            trace_id = command.request_id or f"conversation-{conversation_id}"
            correlation_id = f"conversation-{conversation_id}-message-{message_id}"
            title = command.title or _derive_title(command.initial_message_content)

            conversation = ConversationRecord(
                conversation_id=conversation_id,
                owner_user_id=user.user_id,
                title=title,
                summary=None,
                scenario_binding=command.scenario_binding,
                tags=command.tags,
                status=ConversationStatus.ACTIVE,
                latest_message_summary=command.initial_message_content[:200],
                retention_policy="conversation_default_v1",
                legal_hold=False,
                last_active_time=now_ms,
                active_run_id=str(turn_id),
                created_time=now_ms,
                updated_time=now_ms,
            )
            message = ConversationMessageRecord(
                message_id=message_id,
                conversation_id=conversation_id,
                turn_id=turn_id,
                role="user",
                content_type="text",
                content=command.initial_message_content,
                status=MessageStatus.PERSISTED,
                client_message_id=command.initial_message_client_id,
                idempotency_key=command.idempotency_key,
                trace_id=trace_id,
                correlation_id=correlation_id,
                created_time=now_ms,
                updated_time=now_ms,
            )
            status_event = ConversationStatusEventRecord(
                status_event_id=status_event_id,
                conversation_id=conversation_id,
                message_id=message_id,
                turn_id=turn_id,
                event_type="message.created",
                sequence=1,
                message_status=MessageStatus.PERSISTED,
                title="Message created",
                detail="User message accepted",
                payload={
                    "source": command.source,
                    "client_message_id": command.initial_message_client_id,
                    "message": _message_snapshot(message),
                },
                trace_id=trace_id,
                correlation_id=correlation_id,
                created_time=now_ms,
                updated_time=now_ms,
            )
            outbox = MqOutboxRecord(
                outbox_id=outbox_id,
                event_id=f"conversation.message.sent.{message_id}",
                event_type="conversation.message.sent.v1",
                routing_key="conversation.message.sent.v1",
                conversation_id=conversation_id,
                message_id=message_id,
                payload={
                    "conversation_id": str(conversation_id),
                    "message_id": str(message_id),
                    "turn_id": str(turn_id),
                    "content": command.initial_message_content,
                },
                status="pending",
                trace_id=trace_id,
                correlation_id=correlation_id,
                idempotency_key=command.idempotency_key,
                created_time=now_ms,
                updated_time=now_ms,
            )

            await unit_of_work.conversations.add_record(conversation)
            await unit_of_work.messages.add(message)
            await unit_of_work.status_events.add(status_event)
            await unit_of_work.outbox.add(outbox)
            logger.info(
                "conversation_create_persisted",
                extra={
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "status_event_id": status_event_id,
                    "outbox_id": outbox_id,
                    "request_id": command.request_id,
                },
            )
            return await _commit_message_accepted_result(
                unit_of_work,
                result=MessageAcceptedResult(
                    message=message,
                    conversation=conversation,
                    status_event=status_event,
                ),
                idempotency_key=command.idempotency_key,
                user=user,
            )


class ListConversationsHandler:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], UnitOfWork],
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def handle(
        self,
        query: ConversationListQuery,
        user: AuthenticatedUser,
    ) -> ConversationListResult:
        logger.info(
            "conversation_list_enter",
            extra={
                "user_id": user.user_id,
                "keyword_present": query.keyword is not None,
                "limit": query.limit,
            },
        )
        async with self._unit_of_work_factory() as unit_of_work:
            items, page = await unit_of_work.conversations.list_records(
                query,
                owner_user_id=user.user_id,
            )
        return ConversationListResult(items=items, page=page)


class SendUserMessageHandler:
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
        command: SendUserMessageCommand,
        user: AuthenticatedUser,
    ) -> MessageAcceptedResult | None:
        logger.info(
            "conversation_message_send_enter",
            extra={
                "user_id": user.user_id,
                "conversation_id": command.conversation_id,
                "has_idempotency_key": command.idempotency_key is not None,
                "request_id": command.request_id,
            },
        )
        async with self._unit_of_work_factory() as unit_of_work:
            if command.idempotency_key is not None:
                existing = await unit_of_work.messages.get_by_idempotency_key(
                    command.idempotency_key
                )
                if existing is not None:
                    logger.info(
                        "conversation_message_send_idempotent_hit",
                        extra={
                            "conversation_id": existing.conversation_id,
                            "message_id": existing.message_id,
                            "request_id": command.request_id,
                        },
                    )
                    return await _load_message_accepted_result(unit_of_work, existing, user)

            conversation = await unit_of_work.conversations.get_record_by_id(
                command.conversation_id
            )
            if conversation is None:
                logger.info(
                    "conversation_message_send_not_found",
                    extra={"conversation_id": command.conversation_id},
                )
                return None
            ensure_conversation_owner(conversation, user)

            if command.submission_type == "clarification_response":
                if conversation.status is ConversationStatus.ARCHIVED:
                    raise DomainError(ErrorReason.CONVERSATION_ARCHIVED)
                if conversation.status is ConversationStatus.EXPIRED:
                    raise DomainError(ErrorReason.CONVERSATION_EXPIRED)
                if conversation.active_run_id is not None:
                    raise DomainError(ErrorReason.CONVERSATION_BUSY)
            else:
                _conversation_guard(conversation).ensure_user_message_allowed()
            _ensure_user_text_allowed(command.content)

            now_ms = _current_time_ms()
            message_id = self._id_generator.next_id()
            turn_id = message_id
            status_event_id = self._id_generator.next_id()
            outbox_id = self._id_generator.next_id()
            trace_id = command.request_id or f"conversation-{command.conversation_id}"
            correlation_id = f"conversation-{command.conversation_id}-message-{message_id}"
            sequence = await unit_of_work.status_events.next_sequence(command.conversation_id)

            updated_conversation = replace(
                conversation,
                last_active_time=now_ms,
                active_run_id=str(turn_id),
                updated_time=now_ms,
            )
            message = ConversationMessageRecord(
                message_id=message_id,
                conversation_id=command.conversation_id,
                parent_message_id=command.parent_message_id,
                turn_id=turn_id,
                role="user",
                content_type="text",
                content=command.content,
                status=MessageStatus.PERSISTED,
                client_message_id=command.client_message_id,
                idempotency_key=command.idempotency_key,
                trace_id=trace_id,
                correlation_id=correlation_id,
                created_time=now_ms,
                updated_time=now_ms,
            )
            status_payload = {
                "client_message_id": command.client_message_id,
                "parent_message_id": str(command.parent_message_id)
                if command.parent_message_id is not None
                else None,
                "message": _message_snapshot(message),
            }
            if command.submission_type != "user_message":
                status_payload["submission_type"] = command.submission_type

            outbox_payload = {
                "conversation_id": str(command.conversation_id),
                "message_id": str(message_id),
                "turn_id": str(turn_id),
                "content": command.content,
            }

            status_event = ConversationStatusEventRecord(
                status_event_id=status_event_id,
                conversation_id=command.conversation_id,
                message_id=message_id,
                turn_id=turn_id,
                event_type="message.created",
                sequence=sequence,
                message_status=MessageStatus.PERSISTED,
                title="Message created",
                detail="User message accepted",
                payload=status_payload,
                trace_id=trace_id,
                correlation_id=correlation_id,
                created_time=now_ms,
                updated_time=now_ms,
            )
            outbox = MqOutboxRecord(
                outbox_id=outbox_id,
                event_id=f"conversation.message.sent.{message_id}",
                event_type="conversation.message.sent.v1",
                routing_key="conversation.message.sent.v1",
                conversation_id=command.conversation_id,
                message_id=message_id,
                payload=outbox_payload,
                status="pending",
                trace_id=trace_id,
                correlation_id=correlation_id,
                idempotency_key=command.idempotency_key,
                created_time=now_ms,
                updated_time=now_ms,
            )

            await unit_of_work.conversations.update_record(updated_conversation)
            await unit_of_work.messages.add(message)
            await unit_of_work.status_events.add(status_event)
            await unit_of_work.outbox.add(outbox)
            logger.info(
                "conversation_message_send_persisted",
                extra={
                    "conversation_id": command.conversation_id,
                    "message_id": message_id,
                    "status_event_id": status_event_id,
                    "outbox_id": outbox_id,
                    "request_id": command.request_id,
                },
            )
            return await _commit_message_accepted_result(
                unit_of_work,
                result=MessageAcceptedResult(
                    message=message,
                    conversation=updated_conversation,
                    status_event=status_event,
                ),
                idempotency_key=command.idempotency_key,
                user=user,
            )


class ListConversationMessagesHandler:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], UnitOfWork],
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def handle(
        self,
        query: ConversationMessageListQuery,
        user: AuthenticatedUser,
    ) -> ConversationMessageListResult | None:
        logger.info(
            "conversation_message_list_enter",
            extra={
                "user_id": user.user_id,
                "conversation_id": query.conversation_id,
                "limit": query.limit,
            },
        )
        async with self._unit_of_work_factory() as unit_of_work:
            conversation = await unit_of_work.conversations.get_record_by_id(query.conversation_id)
            if conversation is None:
                logger.info(
                    "conversation_message_list_not_found",
                    extra={"conversation_id": query.conversation_id},
                )
                return None
            ensure_conversation_owner(conversation, user)
            return await unit_of_work.messages.list_page(query)


class GetConversationHandler:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], UnitOfWork],
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def handle(
        self,
        conversation_id: int,
        user: AuthenticatedUser,
        *,
        include_latest_messages: bool,
        latest_message_limit: int,
        include_latest_events: bool,
    ) -> ConversationDetailResult | None:
        logger.info(
            "conversation_get_enter",
            extra={"user_id": user.user_id, "conversation_id": conversation_id},
        )
        async with self._unit_of_work_factory() as unit_of_work:
            conversation = await unit_of_work.conversations.get_record_by_id(conversation_id)
            if conversation is None:
                logger.info(
                    "conversation_get_not_found",
                    extra={"conversation_id": conversation_id},
                )
                return None
            ensure_conversation_owner(conversation, user)

            latest_messages: tuple[ConversationMessageRecord, ...] = ()
            latest_events: tuple[ConversationStatusEventRecord, ...] = ()
            if include_latest_messages:
                latest_messages = await unit_of_work.messages.list_by_conversation(
                    conversation_id,
                    limit=latest_message_limit,
                )
            if include_latest_events:
                latest_events = await unit_of_work.status_events.list_by_conversation(
                    conversation_id,
                    limit=latest_message_limit,
                )

        return ConversationDetailResult(
            conversation=conversation,
            latest_messages=latest_messages,
            latest_events=latest_events,
            context=None,
        )


class ListConversationEventsHandler:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], UnitOfWork],
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def handle(
        self,
        conversation_id: int,
        user: AuthenticatedUser,
        *,
        cursor: str | None,
        limit: int,
    ) -> ConversationStatusEventListResult | None:
        logger.info(
            "conversation_event_list_enter",
            extra={"user_id": user.user_id, "conversation_id": conversation_id, "limit": limit},
        )
        async with self._unit_of_work_factory() as unit_of_work:
            conversation = await unit_of_work.conversations.get_record_by_id(conversation_id)
            if conversation is None:
                return None
            ensure_conversation_owner(conversation, user)
            events, page = await unit_of_work.status_events.list_after_sequence(
                conversation_id,
                after_sequence=int(cursor or 0),
                limit=limit,
            )
            latest_sequence = await unit_of_work.status_events.max_sequence(conversation_id)
            return ConversationStatusEventListResult(
                items=events,
                page=page,
                latest_sequence=latest_sequence,
                recommended_poll_interval_ms=_recommended_poll_interval_ms(
                    conversation.active_run_id
                ),
            )


async def _load_message_accepted_result(
    unit_of_work: UnitOfWork,
    message: ConversationMessageRecord,
    user: AuthenticatedUser,
) -> MessageAcceptedResult:
    conversation = await unit_of_work.conversations.get_record_by_id(message.conversation_id)
    status_event = await unit_of_work.status_events.get_first_by_message_id(message.message_id)
    if conversation is None or status_event is None:
        raise RuntimeError("idempotency record is incomplete")
    ensure_conversation_owner(conversation, user)
    return MessageAcceptedResult(
        message=message,
        conversation=conversation,
        status_event=status_event,
    )


async def _commit_message_accepted_result(
    unit_of_work: UnitOfWork,
    *,
    result: MessageAcceptedResult,
    idempotency_key: str | None,
    user: AuthenticatedUser,
) -> MessageAcceptedResult:
    try:
        await unit_of_work.commit()
    except Exception as exc:
        if not _is_integrity_error(exc):
            raise
        await unit_of_work.rollback()
        if idempotency_key is None:
            raise
        existing = await unit_of_work.messages.get_by_idempotency_key(idempotency_key)
        if existing is None:
            raise
        logger.warning(
            "conversation_message_idempotency_race_recovered",
            extra={
                "conversation_id": existing.conversation_id,
                "message_id": existing.message_id,
                "idempotency_key": idempotency_key,
            },
        )
        return await _load_message_accepted_result(unit_of_work, existing, user)
    return result


def _ensure_user_text_allowed(text: str) -> None:
    decision = _redaction_policy.inspect_user_text(text)
    if decision.action is RedactionAction.REJECT:
        raise DomainError(ErrorReason.SENSITIVE_INPUT_REJECTED)


def _is_integrity_error(exc: Exception) -> bool:
    # Keep the application layer free of direct SQLAlchemy imports.
    return exc.__class__.__name__ == "IntegrityError"


def _derive_title(content: str) -> str:
    normalized = " ".join(content.strip().split())
    if len(normalized) <= 60:
        return normalized
    return normalized[:57].rstrip() + "..."


def _current_time_ms() -> int:
    return int(time() * 1000)


async def _load_agent_context_payload(
    unit_of_work: UnitOfWork,
    conversation_id: int,
) -> dict[str, object]:
    snapshot = await unit_of_work.context_snapshots.get_current_by_conversation(conversation_id)
    recent_messages = await unit_of_work.messages.list_by_conversation(conversation_id, limit=5)
    context: dict[str, object] = {"summary": None, "structured_state": {}}
    if snapshot is not None:
        context = {
            "summary": snapshot.short_summary,
            "structured_state": snapshot.structured_state,
            "snapshot_version": snapshot.snapshot_version,
        }
    return {
        "context": context,
        "recent_message_refs": [
            {
                "message_id": str(message.message_id),
                "role": message.role,
                "status": message.status.value,
            }
            for message in recent_messages
        ],
    }


def _conversation_guard(record: ConversationRecord) -> Conversation:
    return Conversation(
        conversation_id=record.conversation_id,
        owner_user_id=record.owner_user_id,
        title=record.title,
        status=record.status,
        last_active_time=record.last_active_time,
        active_run_id=record.active_run_id,
        created_time=record.created_time,
        updated_time=record.updated_time,
    )


def _message_snapshot(message: ConversationMessageRecord) -> dict[str, str | None]:
    return {
        "message_id": str(message.message_id),
        "conversation_id": str(message.conversation_id),
        "parent_message_id": (
            str(message.parent_message_id) if message.parent_message_id is not None else None
        ),
        "turn_id": str(message.turn_id) if message.turn_id is not None else None,
        "client_message_id": message.client_message_id,
        "role": message.role,
        "content_type": message.content_type,
        "content": message.content,
        "status": message.status.value,
    }


def _recommended_poll_interval_ms(active_run_id: str | None) -> int:
    if active_run_id is not None:
        return 1000
    return 5000
