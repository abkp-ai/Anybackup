import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from time import time

from app.application.models.conversation import (
    AuthenticatedUser,
    ConversationRecord,
    ConversationStatusEventRecord,
)
from app.application.ports.id_generator import IdGenerator
from app.application.ports.locking import GlobalLock
from app.application.ports.unit_of_work import UnitOfWork
from app.application.use_cases.access import ensure_conversation_owner
from app.domain.conversation import ConversationStatus
from app.domain.shared.errors import DomainError, ErrorReason

logger = logging.getLogger(__name__)

DAY_MS = 86_400_000


@dataclass(frozen=True, slots=True)
class RetentionRunResult:
    lock_acquired: bool
    archived_count: int = 0
    expired_count: int = 0


class ArchiveConversationHandler:
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
        conversation_id: int,
        user: AuthenticatedUser,
        *,
        reason: str | None,
    ) -> ConversationRecord | None:
        logger.info(
            "conversation_archive_enter",
            extra={"conversation_id": conversation_id, "user_id": user.user_id},
        )
        async with self._unit_of_work_factory() as unit_of_work:
            conversation = await unit_of_work.conversations.get_record_by_id(conversation_id)
            if conversation is None:
                return None
            ensure_conversation_owner(conversation, user)
            if conversation.legal_hold:
                raise DomainError(ErrorReason.CONVERSATION_BUSY)
            if conversation.active_run_id is not None:
                raise DomainError(ErrorReason.CONVERSATION_BUSY)
            now_ms = _current_time_ms()
            archived = replace(
                conversation,
                status=ConversationStatus.ARCHIVED,
                archived_time=now_ms,
                archived_by="user",
                archive_reason=reason,
                updated_time=now_ms,
            )
            await unit_of_work.conversations.update_record(archived)
            await _add_status_event(
                unit_of_work,
                id_generator=self._id_generator,
                conversation=archived,
                event_type="conversation.archived",
                now_ms=now_ms,
                title="Conversation archived",
                detail=reason,
            )
            return archived


class RestoreConversationHandler:
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
        conversation_id: int,
        user: AuthenticatedUser,
        *,
        reason: str | None,
    ) -> ConversationRecord | None:
        logger.info(
            "conversation_restore_enter",
            extra={"conversation_id": conversation_id, "user_id": user.user_id},
        )
        async with self._unit_of_work_factory() as unit_of_work:
            conversation = await unit_of_work.conversations.get_record_by_id(conversation_id)
            if conversation is None:
                return None
            ensure_conversation_owner(conversation, user)
            if conversation.status is ConversationStatus.EXPIRED:
                raise DomainError(ErrorReason.CONVERSATION_EXPIRED)
            if conversation.status is not ConversationStatus.ARCHIVED:
                raise DomainError(ErrorReason.CONVERSATION_STATE_CONFLICT)
            now_ms = _current_time_ms()
            restored = replace(
                conversation,
                status=ConversationStatus.ACTIVE,
                archived_time=None,
                archived_by=None,
                archive_reason=None,
                updated_time=now_ms,
                last_active_time=now_ms,
            )
            await unit_of_work.conversations.update_record(restored)
            await _add_status_event(
                unit_of_work,
                id_generator=self._id_generator,
                conversation=restored,
                event_type="conversation.restored",
                now_ms=now_ms,
                title="Conversation restored",
                detail=reason,
            )
            return restored


class SetLegalHoldHandler:
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
        conversation_id: int,
        user: AuthenticatedUser,
        *,
        enabled: bool,
        reason: str | None,
    ) -> ConversationRecord | None:
        logger.info(
            "conversation_legal_hold_enter",
            extra={"conversation_id": conversation_id, "user_id": user.user_id, "enabled": enabled},
        )
        async with self._unit_of_work_factory() as unit_of_work:
            conversation = await unit_of_work.conversations.get_record_by_id(conversation_id)
            if conversation is None:
                return None
            ensure_conversation_owner(conversation, user)
            now_ms = _current_time_ms()
            updated = replace(conversation, legal_hold=enabled, updated_time=now_ms)
            await unit_of_work.conversations.update_record(updated)
            await _add_status_event(
                unit_of_work,
                id_generator=self._id_generator,
                conversation=updated,
                event_type="conversation.legal_hold_updated",
                now_ms=now_ms,
                title="Legal hold updated",
                detail=reason,
                payload={"legal_hold": enabled},
            )
            return updated


class RetentionWorker:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], UnitOfWork],
        id_generator: IdGenerator,
        lock: GlobalLock,
        lock_ttl_ms: int,
        auto_archive_after_days: int = 30,
        archive_retention_days: int = 365,
        batch_size: int = 100,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._id_generator = id_generator
        self._lock = lock
        self._lock_ttl_ms = lock_ttl_ms
        self._auto_archive_after_days = auto_archive_after_days
        self._archive_retention_days = archive_retention_days
        self._batch_size = batch_size

    async def run_once(self, *, worker_id: str, now_ms: int) -> RetentionRunResult:
        logger.info("retention_worker_enter", extra={"worker_id": worker_id})
        lease = await self._lock.acquire(
            "conversation_service:lock:retention:worker",
            ttl_ms=self._lock_ttl_ms,
        )
        if lease is None:
            return RetentionRunResult(lock_acquired=False)
        archived_count = 0
        expired_count = 0
        try:
            async with self._unit_of_work_factory() as unit_of_work:
                archive_cutoff = now_ms - self._auto_archive_after_days * DAY_MS
                expire_cutoff = now_ms - self._archive_retention_days * DAY_MS
                archive_candidates = await unit_of_work.conversations.list_auto_archive_candidates(
                    last_active_before_ms=archive_cutoff,
                    limit=self._batch_size,
                )
                expire_candidates = await unit_of_work.conversations.list_expire_candidates(
                    archived_before_ms=expire_cutoff,
                    limit=self._batch_size,
                )
                for conversation in archive_candidates:
                    archived = replace(
                        conversation,
                        status=ConversationStatus.ARCHIVED,
                        archived_time=now_ms,
                        archived_by="system",
                        archive_reason="inactivity_30d",
                        updated_time=now_ms,
                    )
                    await unit_of_work.conversations.update_record(archived)
                    await _add_status_event(
                        unit_of_work,
                        id_generator=self._id_generator,
                        conversation=archived,
                        event_type="conversation.archived",
                        now_ms=now_ms,
                        title="Conversation auto archived",
                        detail="inactivity_30d",
                    )
                    archived_count += 1
                for conversation in expire_candidates:
                    expired = replace(
                        conversation,
                        status=ConversationStatus.EXPIRED,
                        expired_time=now_ms,
                        updated_time=now_ms,
                    )
                    await unit_of_work.conversations.update_record(expired)
                    await _add_status_event(
                        unit_of_work,
                        id_generator=self._id_generator,
                        conversation=expired,
                        event_type="conversation.expired",
                        now_ms=now_ms,
                        title="Conversation expired",
                        detail="retention_expired",
                    )
                    expired_count += 1
            return RetentionRunResult(
                lock_acquired=True,
                archived_count=archived_count,
                expired_count=expired_count,
            )
        finally:
            await lease.release()


async def _add_status_event(
    unit_of_work: UnitOfWork,
    *,
    id_generator: IdGenerator,
    conversation: ConversationRecord,
    event_type: str,
    now_ms: int,
    title: str,
    detail: str | None,
    payload: dict[str, object] | None = None,
) -> None:
    sequence = await unit_of_work.status_events.next_sequence(conversation.conversation_id)
    await unit_of_work.status_events.add(
        ConversationStatusEventRecord(
            status_event_id=id_generator.next_id(),
            conversation_id=conversation.conversation_id,
            event_type=event_type,
            sequence=sequence,
            title=title,
            detail=detail,
            payload=payload,
            created_time=now_ms,
            updated_time=now_ms,
        )
    )


def _current_time_ms() -> int:
    return int(time() * 1000)
