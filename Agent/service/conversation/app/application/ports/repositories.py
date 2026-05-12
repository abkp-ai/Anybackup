from typing import Protocol

from app.application.models.conversation import (
    ConversationListQuery,
    ConversationMessageListQuery,
    ConversationMessageListResult,
    ConversationMessageRecord,
    ConversationRecord,
    ConversationStatusEventRecord,
    MqOutboxRecord,
    Page,
)
from app.application.models.writeback import (
    ConversationCandidateSelectionRecord,
    ConversationContextDeltaRecord,
    ConversationContextSnapshotRecord,
    ConversationReasoningTraceRecord,
    ConversationWritebackIdempotencyRecord,
)
from app.domain.conversation import Conversation


class ConversationRepository(Protocol):
    async def add(self, conversation: Conversation) -> None:
        raise NotImplementedError

    async def add_record(self, conversation: ConversationRecord) -> None:
        raise NotImplementedError

    async def update_record(self, conversation: ConversationRecord) -> None:
        raise NotImplementedError

    async def get_by_id(self, conversation_id: int) -> Conversation | None:
        raise NotImplementedError

    async def get_record_by_id(self, conversation_id: int) -> ConversationRecord | None:
        raise NotImplementedError

    async def list_records(
        self,
        query: ConversationListQuery,
        *,
        owner_user_id: str,
    ) -> tuple[tuple[ConversationRecord, ...], Page]:
        raise NotImplementedError

    async def list_auto_archive_candidates(
        self,
        *,
        last_active_before_ms: int,
        limit: int,
    ) -> tuple[ConversationRecord, ...]:
        raise NotImplementedError

    async def list_expire_candidates(
        self,
        *,
        archived_before_ms: int,
        limit: int,
    ) -> tuple[ConversationRecord, ...]:
        raise NotImplementedError


class MessageRepository(Protocol):
    async def add(self, message: ConversationMessageRecord) -> None:
        raise NotImplementedError

    async def update(self, message: ConversationMessageRecord) -> None:
        raise NotImplementedError

    async def get_by_id(self, message_id: int) -> ConversationMessageRecord | None:
        raise NotImplementedError

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> ConversationMessageRecord | None:
        raise NotImplementedError

    async def list_by_conversation(
        self,
        conversation_id: int,
        *,
        limit: int,
    ) -> tuple[ConversationMessageRecord, ...]:
        raise NotImplementedError

    async def list_page(
        self,
        query: ConversationMessageListQuery,
    ) -> ConversationMessageListResult:
        raise NotImplementedError


class StatusEventRepository(Protocol):
    async def add(self, event: ConversationStatusEventRecord) -> None:
        raise NotImplementedError

    async def exists_by_core_event_id(self, core_event_id: str) -> bool:
        raise NotImplementedError

    async def next_sequence(self, conversation_id: int) -> int:
        raise NotImplementedError

    async def max_sequence(self, conversation_id: int) -> int:
        raise NotImplementedError

    async def get_first_by_message_id(
        self,
        message_id: int,
    ) -> ConversationStatusEventRecord | None:
        raise NotImplementedError

    async def list_by_conversation(
        self,
        conversation_id: int,
        *,
        limit: int,
    ) -> tuple[ConversationStatusEventRecord, ...]:
        raise NotImplementedError

    async def list_after_sequence(
        self,
        conversation_id: int,
        *,
        after_sequence: int,
        limit: int,
    ) -> tuple[tuple[ConversationStatusEventRecord, ...], Page]:
        raise NotImplementedError

    async def list_ag_ui_after_sequence(
        self,
        conversation_id: int,
        *,
        run_id: str,
        after_sequence: int,
        limit: int,
    ) -> tuple[ConversationStatusEventRecord, ...]:
        raise NotImplementedError


class MqOutboxRepository(Protocol):
    async def add(self, event: MqOutboxRecord) -> None:
        raise NotImplementedError

    async def list_publishable(self, *, limit: int, now_ms: int) -> tuple[MqOutboxRecord, ...]:
        raise NotImplementedError

    async def mark_published(self, *, outbox_id: int, now_ms: int) -> None:
        raise NotImplementedError

    async def mark_retry(
        self,
        *,
        outbox_id: int,
        attempt_count: int,
        next_retry_time: int,
        error_code: str,
        now_ms: int,
    ) -> None:
        raise NotImplementedError

    async def mark_dlq(
        self,
        *,
        outbox_id: int,
        attempt_count: int,
        error_code: str,
        now_ms: int,
    ) -> None:
        raise NotImplementedError


class WritebackIdempotencyRepository(Protocol):
    async def add(self, record: ConversationWritebackIdempotencyRecord) -> None:
        raise NotImplementedError

    async def get_by_key(
        self,
        idempotency_key: str,
    ) -> ConversationWritebackIdempotencyRecord | None:
        raise NotImplementedError

    async def get_by_conversation_output_id(
        self,
        *,
        conversation_id: int,
        output_id: str,
    ) -> ConversationWritebackIdempotencyRecord | None:
        raise NotImplementedError

    async def max_accepted_output_sequence(
        self,
        conversation_id: int,
        *,
        turn_id: int,
        message_id: int,
    ) -> int:
        raise NotImplementedError


class ContextDeltaRepository(Protocol):
    async def add(self, record: ConversationContextDeltaRecord) -> None:
        raise NotImplementedError

    async def list_pending(self, *, limit: int) -> tuple[ConversationContextDeltaRecord, ...]:
        raise NotImplementedError

    async def count_pending_by_conversation(self, conversation_id: int) -> int:
        raise NotImplementedError

    async def mark_status(
        self,
        *,
        context_delta_id: int,
        merge_status: str,
        now_ms: int,
    ) -> None:
        raise NotImplementedError


class ContextSnapshotRepository(Protocol):
    async def add(self, record: ConversationContextSnapshotRecord) -> None:
        raise NotImplementedError

    async def get_current_by_conversation(
        self,
        conversation_id: int,
    ) -> ConversationContextSnapshotRecord | None:
        raise NotImplementedError

    async def next_version(self, conversation_id: int) -> int:
        raise NotImplementedError


class ReasoningTraceRepository(Protocol):
    async def add(self, record: ConversationReasoningTraceRecord) -> None:
        raise NotImplementedError

    async def get_by_id(
        self,
        reasoning_trace_id: str,
    ) -> ConversationReasoningTraceRecord | None:
        raise NotImplementedError

    async def list_by_conversation(
        self,
        conversation_id: int,
        *,
        limit: int,
    ) -> tuple[ConversationReasoningTraceRecord, ...]:
        raise NotImplementedError


class CandidateSelectionRepository(Protocol):
    async def add(self, record: ConversationCandidateSelectionRecord) -> None:
        raise NotImplementedError

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> ConversationCandidateSelectionRecord | None:
        raise NotImplementedError
