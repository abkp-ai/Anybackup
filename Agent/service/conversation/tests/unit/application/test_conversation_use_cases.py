from dataclasses import replace

import pytest
from sqlalchemy.exc import IntegrityError

from app.application.commands.conversation import SendUserMessageCommand
from app.application.models.conversation import (
    AuthenticatedUser,
    ConversationMessageRecord,
    ConversationRecord,
    ConversationStatusEventRecord,
    MqOutboxRecord,
)
from app.application.use_cases.conversation import SendUserMessageHandler
from app.domain.conversation import ConversationStatus
from app.domain.message import MessageStatus


@pytest.mark.asyncio
async def test_send_user_message_returns_existing_record_after_idempotency_race() -> None:
    existing_message = ConversationMessageRecord(
        message_id=9_001,
        conversation_id=7_001,
        role="user",
        content_type="text",
        content="retry restore",
        status=MessageStatus.PERSISTED,
        client_message_id="client-race",
        idempotency_key="message-race-001",
        trace_id="trace-race",
        correlation_id="corr-race",
        created_time=1_800_000_000_100,
        updated_time=1_800_000_000_100,
    )
    existing_conversation = ConversationRecord(
        conversation_id=7_001,
        owner_user_id="user-001",
        title="restore-db",
        status=ConversationStatus.ACTIVE,
        tags=(),
        created_time=1_800_000_000_000,
        updated_time=1_800_000_000_100,
        last_active_time=1_800_000_000_100,
        active_run_id="9001",
    )
    existing_status_event = ConversationStatusEventRecord(
        status_event_id=9_101,
        conversation_id=7_001,
        message_id=9_001,
        event_type="message.created",
        sequence=2,
        message_status=MessageStatus.PERSISTED,
        title="Message created",
        detail="User message accepted",
        payload={"client_message_id": "client-race"},
        trace_id="trace-race",
        correlation_id="corr-race",
        created_time=1_800_000_000_100,
        updated_time=1_800_000_000_100,
    )
    unit_of_work = FakeUnitOfWork(
        conversation=replace(
            existing_conversation,
            active_run_id=None,
            updated_time=1_800_000_000_000,
            last_active_time=1_800_000_000_000,
        ),
        existing_conversation=existing_conversation,
        existing_message=existing_message,
        existing_status_event=existing_status_event,
    )
    handler = SendUserMessageHandler(
        unit_of_work_factory=lambda: unit_of_work,
        id_generator=FakeIdGenerator(start=10_000),
    )

    result = await handler.handle(
        SendUserMessageCommand(
            conversation_id=7_001,
            content="retry restore",
            client_message_id="client-race",
            parent_message_id=None,
            idempotency_key="message-race-001",
            request_id="req-race",
        ),
        AuthenticatedUser(user_id="user-001"),
    )

    assert result is not None
    assert result.message.message_id == 9_001
    assert result.status_event.status_event_id == 9_101
    assert result.conversation.active_run_id == "9001"
    assert unit_of_work.rollback_calls == 1


class FakeIdGenerator:
    def __init__(self, *, start: int) -> None:
        self._current = start

    def next_id(self) -> int:
        value = self._current
        self._current += 1
        return value


class FakeUnitOfWork:
    def __init__(
        self,
        *,
        conversation: ConversationRecord,
        existing_conversation: ConversationRecord,
        existing_message: ConversationMessageRecord,
        existing_status_event: ConversationStatusEventRecord,
    ) -> None:
        self.conversations = FakeConversationRepository(conversation, existing_conversation)
        self.messages = FakeMessageRepository(existing_message)
        self.status_events = FakeStatusEventRepository(existing_status_event)
        self.outbox = FakeOutboxRepository()
        self.writebacks = FakeWritebackRepository()
        self.context_deltas = FakeContextDeltaRepository()
        self.context_snapshots = FakeContextSnapshotRepository()
        self.reasoning_traces = FakeReasoningTraceRepository()
        self.candidate_selections = FakeCandidateSelectionRepository()
        self.rollback_calls = 0
        self._commit_attempts = 0

    async def __aenter__(self) -> "FakeUnitOfWork":
        return self

    async def __aexit__(self, exc_type, exc, traceback) -> None:
        del exc, traceback
        if exc_type is None:
            await self.commit()
        else:
            await self.rollback()

    async def commit(self) -> None:
        self._commit_attempts += 1
        if self._commit_attempts == 1:
            self.conversations.persist_existing()
            self.messages.persist_existing()
            self.status_events.persist_existing()
            raise IntegrityError("idempotency race", {}, Exception("duplicate"))

    async def rollback(self) -> None:
        self.rollback_calls += 1


class FakeConversationRepository:
    def __init__(
        self,
        conversation: ConversationRecord,
        existing_conversation: ConversationRecord,
    ) -> None:
        self._conversation = conversation
        self._existing_conversation = existing_conversation

    async def get_record_by_id(self, conversation_id: int) -> ConversationRecord | None:
        if conversation_id != self._conversation.conversation_id:
            return None
        return self._conversation

    async def update_record(self, conversation: ConversationRecord) -> None:
        self._conversation = conversation

    def persist_existing(self) -> None:
        self._conversation = self._existing_conversation


class FakeMessageRepository:
    def __init__(self, existing_message: ConversationMessageRecord) -> None:
        self._existing_message = existing_message
        self._messages_by_idempotency_key: dict[str, ConversationMessageRecord] = {}

    async def add(self, message: ConversationMessageRecord) -> None:
        if message.idempotency_key is not None:
            self._messages_by_idempotency_key[message.idempotency_key] = message

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> ConversationMessageRecord | None:
        return self._messages_by_idempotency_key.get(idempotency_key)

    async def list_by_conversation(
        self,
        conversation_id: int,
        *,
        limit: int,
    ) -> tuple[ConversationMessageRecord, ...]:
        del conversation_id, limit
        return ()

    def persist_existing(self) -> None:
        self._messages_by_idempotency_key[self._existing_message.idempotency_key or ""] = (
            self._existing_message
        )


class FakeStatusEventRepository:
    def __init__(self, existing_status_event: ConversationStatusEventRecord) -> None:
        self._existing_status_event = existing_status_event
        self._events_by_message_id: dict[int, ConversationStatusEventRecord] = {}

    async def next_sequence(self, conversation_id: int) -> int:
        del conversation_id
        return 2

    async def add(self, event: ConversationStatusEventRecord) -> None:
        if event.message_id is not None:
            self._events_by_message_id[event.message_id] = event

    async def get_first_by_message_id(
        self,
        message_id: int,
    ) -> ConversationStatusEventRecord | None:
        return self._events_by_message_id.get(message_id)

    def persist_existing(self) -> None:
        if self._existing_status_event.message_id is not None:
            self._events_by_message_id[self._existing_status_event.message_id] = (
                self._existing_status_event
            )


class FakeOutboxRepository:
    def __init__(self) -> None:
        self.events: list[MqOutboxRecord] = []

    async def add(self, event: MqOutboxRecord) -> None:
        self.events.append(event)


class FakeWritebackRepository:
    pass


class FakeContextDeltaRepository:
    pass


class FakeContextSnapshotRepository:
    async def get_current_by_conversation(self, conversation_id: int):
        del conversation_id
        return None


class FakeReasoningTraceRepository:
    pass


class FakeCandidateSelectionRepository:
    pass
