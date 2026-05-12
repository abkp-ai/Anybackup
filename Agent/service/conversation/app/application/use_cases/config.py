import logging
from collections.abc import Callable
from dataclasses import replace
from time import time
from typing import Any

from app.application.commands.config import (
    CopyConversationConfigCommand,
    UpdateConversationCommand,
)
from app.application.models.conversation import (
    AuthenticatedUser,
    ConversationDetailResult,
    ConversationRecord,
    ConversationStatusEventRecord,
)
from app.application.ports.id_generator import IdGenerator
from app.application.ports.unit_of_work import UnitOfWork
from app.application.use_cases.access import ensure_conversation_owner
from app.domain.conversation import Conversation, ConversationStatus
from app.domain.shared.errors import DomainError, ErrorReason

logger = logging.getLogger(__name__)

_COPYABLE_SCENARIO_KEYS = frozenset(
    {
        "scenario_id",
        "scenario_name",
        "task_type",
        "asset_refs",
        "business_refs",
        "preferences",
        "reusable_preferences",
    }
)


class CopyConversationConfigHandler:
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
        command: CopyConversationConfigCommand,
        user: AuthenticatedUser,
    ) -> ConversationDetailResult | None:
        logger.info(
            "conversation_copy_config_enter",
            extra={
                "source_conversation_id": command.source_conversation_id,
                "user_id": user.user_id,
                "request_id": command.request_id,
            },
        )
        async with self._unit_of_work_factory() as unit_of_work:
            source = await unit_of_work.conversations.get_record_by_id(
                command.source_conversation_id
            )
            if source is None:
                return None
            ensure_conversation_owner(source, user)
            if source.status is ConversationStatus.EXPIRED:
                raise DomainError(ErrorReason.CONVERSATION_EXPIRED)

            now_ms = _current_time_ms()
            conversation_id = self._id_generator.next_id()
            status_event_id = self._id_generator.next_id()
            scenario_binding = (
                _copyable_scenario_binding(source.scenario_binding)
                if command.copy_scenario_binding
                else None
            )
            tags = (
                _merge_tags(source.tags, command.additional_tags)
                if command.copy_tags
                else tuple(command.additional_tags)
            )
            conversation = ConversationRecord(
                conversation_id=conversation_id,
                owner_user_id=user.user_id,
                title=command.title or f"{source.title} copy",
                status=ConversationStatus.ACTIVE,
                tags=tags,
                scenario_binding=scenario_binding,
                summary=None,
                latest_message_summary=None,
                retention_policy="conversation_default_v1",
                legal_hold=False,
                last_active_time=now_ms,
                created_time=now_ms,
                updated_time=now_ms,
            )
            status_event = ConversationStatusEventRecord(
                status_event_id=status_event_id,
                conversation_id=conversation_id,
                event_type="conversation.config_copied",
                sequence=1,
                title="Conversation config copied",
                detail="Copied reusable configuration from source conversation",
                payload={
                    "source_conversation_id": str(source.conversation_id),
                    "copied_fields": _copied_fields(
                        copy_tags=command.copy_tags,
                        copy_scenario_binding=command.copy_scenario_binding,
                    ),
                },
                trace_id=command.request_id,
                correlation_id=f"conversation-{conversation_id}-copy-config",
                created_time=now_ms,
                updated_time=now_ms,
            )

            await unit_of_work.conversations.add_record(conversation)
            await unit_of_work.status_events.add(status_event)
            logger.info(
                "conversation_copy_config_created",
                extra={
                    "source_conversation_id": source.conversation_id,
                    "conversation_id": conversation_id,
                    "status_event_id": status_event_id,
                    "request_id": command.request_id,
                },
            )
            return ConversationDetailResult(
                conversation=conversation,
                latest_messages=(),
                latest_events=(status_event,),
                context=None,
            )


class UpdateConversationHandler:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], UnitOfWork],
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def handle(
        self,
        command: UpdateConversationCommand,
        user: AuthenticatedUser,
    ) -> ConversationRecord | None:
        logger.info(
            "conversation_update_enter",
            extra={
                "conversation_id": command.conversation_id,
                "user_id": user.user_id,
                "request_id": command.request_id,
            },
        )
        async with self._unit_of_work_factory() as unit_of_work:
            conversation = await unit_of_work.conversations.get_record_by_id(
                command.conversation_id
            )
            if conversation is None:
                return None
            ensure_conversation_owner(conversation, user)

            _conversation_guard(conversation).ensure_metadata_update_allowed()
            now_ms = _current_time_ms()
            updated = replace(
                conversation,
                title=_normalize_title(command.title),
                updated_time=now_ms,
            )
            await unit_of_work.conversations.update_record(updated)
            logger.info(
                "conversation_update_persisted",
                extra={
                    "conversation_id": updated.conversation_id,
                    "user_id": user.user_id,
                    "request_id": command.request_id,
                },
            )
            return updated


def _copyable_scenario_binding(raw_value: dict[str, Any] | None) -> dict[str, Any] | None:
    if raw_value is None:
        return None
    copied = {
        key: value
        for key, value in raw_value.items()
        if key in _COPYABLE_SCENARIO_KEYS and value is not None
    }
    return copied or None


def _merge_tags(source_tags: tuple[str, ...], additional_tags: tuple[str, ...]) -> tuple[str, ...]:
    merged: list[str] = []
    for tag in (*source_tags, *additional_tags):
        normalized = tag.strip()
        if normalized and normalized not in merged:
            merged.append(normalized)
    return tuple(merged[:20])


def _copied_fields(*, copy_tags: bool, copy_scenario_binding: bool) -> list[str]:
    fields: list[str] = []
    if copy_scenario_binding:
        fields.extend(["scenario_binding", "task_type", "asset_refs", "preferences"])
    if copy_tags:
        fields.append("tags")
    return fields


def _current_time_ms() -> int:
    return int(time() * 1000)


def _normalize_title(value: str) -> str:
    return " ".join(value.strip().split())


def _conversation_guard(record: ConversationRecord) -> Conversation:
    return Conversation(
        conversation_id=record.conversation_id,
        owner_user_id=record.owner_user_id,
        title=record.title,
        status=record.status,
        last_active_time=record.last_active_time,
        active_run_id=record.active_run_id,
        archived_time=record.archived_time,
        archived_by=record.archived_by,
        archive_reason=record.archive_reason,
        expires_time=record.expires_time,
        expired_time=record.expired_time,
        created_time=record.created_time,
        updated_time=record.updated_time,
    )
