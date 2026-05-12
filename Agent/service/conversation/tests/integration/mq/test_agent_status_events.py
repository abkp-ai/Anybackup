import asyncio
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import create_async_engine

from app.application.commands.agent_events import CoreAgentStatusEventCommand
from app.application.use_cases.agent_status import CoreAgentStatusEventHandler
from app.domain.message import MessageStatus
from app.infrastructure.persistence.sqlalchemy.models import (
    Base,
    ConversationMessageModel,
    ConversationModel,
    ConversationStatusEventModel,
)
from app.infrastructure.persistence.sqlalchemy.session import create_async_session_factory
from app.infrastructure.persistence.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWork
from app.interfaces.mq.agent_status_consumer import CoreAgentStatusMessageConsumer


@pytest.fixture()
def database_url(tmp_path: Path) -> Iterator[str]:
    database_path = tmp_path / "conversation.db"
    url = f"sqlite+aiosqlite:///{database_path.as_posix()}"

    async def create_schema() -> None:
        engine = create_async_engine(url)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(create_schema())
    yield url


@pytest.mark.asyncio
async def test_accepted_event_marks_user_message_processing(database_url: str) -> None:
    await _insert_conversation_with_message(database_url, message_status="published")
    handler = _handler(database_url)

    result = await handler.handle(
        _command(
            event_id="core-accepted-001",
            event_type="core_agent.run.accepted",
            payload={"conversation_id": "100", "content": "accepted"},
        )
    )

    message = await _get_message(database_url, 200)
    conversation = await _get_conversation(database_url, 100)
    event_types = await _event_types(database_url, 100)
    assert result.idempotent is False
    assert message.f_status == MessageStatus.PROCESSING.value
    assert message.f_turn_id == 200
    assert conversation.f_active_run_id == "200"
    event = await _latest_event(database_url, 100)
    assert event_types[-1:] == ["message.updated"]
    assert event.f_event_type == "message.updated"
    assert event.f_sequence == 2
    assert event.f_turn_id == 200
    assert event.f_payload["core_event_id"] == "core-accepted-001"


@pytest.mark.asyncio
async def test_rejected_non_retryable_event_marks_message_failed(database_url: str) -> None:
    await _insert_conversation_with_message(database_url, message_status="published")
    handler = _handler(database_url)

    await handler.handle(
        _command(
            event_id="core-rejected-001",
            event_type="core_agent.run.rejected",
            payload={
                "conversation_id": "100",
                "content": "Task cannot be handled by Core Agent",
            },
        )
    )

    message = await _get_message(database_url, 200)
    conversation = await _get_conversation(database_url, 100)
    event_types = await _event_types(database_url, 100)
    assert message.f_status == MessageStatus.FAILED.value
    assert message.f_error_code == "CORE_AGENT_REJECTED"
    assert conversation.f_active_run_id is None
    event = await _latest_event(database_url, 100)
    assert event_types[-1:] == ["error"]
    assert event.f_event_type == "error"
    assert event.f_turn_id == 200
    assert event.f_payload["retryable"] is False
    assert event.f_payload["error_code"] == "CORE_AGENT_REJECTED"


@pytest.mark.asyncio
async def test_completed_event_closes_turn_without_ag_ui_content(
    database_url: str,
) -> None:
    await _insert_conversation_with_message(
        database_url,
        message_status="processing",
        interaction_status="executing",
    )
    handler = _handler(database_url)

    result = await handler.handle(
        _command(
            event_id="core-completed-001",
            event_type="core_agent.run.completed",
            payload={"conversation_id": "100", "content": "completed"},
        )
    )

    message = await _get_message(database_url, 200)
    conversation = await _get_conversation(database_url, 100)
    event_types = await _event_types(database_url, 100)
    event = await _latest_event(database_url, 100)
    assert result.idempotent is False
    assert message.f_status == MessageStatus.RESPONDED.value
    assert conversation.f_active_run_id is None
    assert event_types[-1:] == ["message.updated"]
    assert event.f_event_type == "message.updated"
    assert event.f_message_id == 200
    assert event.f_turn_id == 200
    assert event.f_payload["core_event_id"] == "core-completed-001"
    assert event.f_payload["core_event_type"] == "core_agent.run.completed"
    assert event.f_payload["content"] == "completed"


@pytest.mark.asyncio
async def test_failed_retryable_event_records_retryable_failure(database_url: str) -> None:
    await _insert_conversation_with_message(database_url, message_status="processing")
    handler = _handler(database_url)

    await handler.handle(
        _command(
            event_id="core-failed-001",
            event_type="core_agent.run.failed",
            payload={"conversation_id": "100", "content": "Core Agent timed out"},
        )
    )

    message = await _get_message(database_url, 200)
    event = await _latest_event(database_url, 100)
    assert message.f_status == MessageStatus.FAILED.value
    assert message.f_error_code == "CORE_AGENT_FAILED"
    assert event.f_event_type == "error"
    assert event.f_turn_id == 200
    assert event.f_payload["retryable"] is False
    assert event.f_payload["error_code"] == "CORE_AGENT_FAILED"


@pytest.mark.asyncio
async def test_duplicate_core_event_is_idempotent(database_url: str) -> None:
    await _insert_conversation_with_message(database_url, message_status="published")
    handler = _handler(database_url)
    command = _command(
        event_id="core-accepted-duplicate",
        event_type="core_agent.run.accepted",
        payload={"conversation_id": "100", "content": "accepted"},
    )

    first = await handler.handle(command)
    second = await handler.handle(command)

    status_event_count = await _status_event_count(database_url)
    assert first.idempotent is False
    assert second.idempotent is True
    assert status_event_count == 2


@pytest.mark.asyncio
async def test_late_accepted_event_does_not_regress_responded_message(database_url: str) -> None:
    await _insert_conversation_with_message(
        database_url,
        message_status="responded",
        interaction_status="completed",
    )
    handler = _handler(database_url)

    await handler.handle(
        _command(
            event_id="core-accepted-late",
            event_type="core_agent.run.accepted",
            payload={"conversation_id": "100", "content": "accepted"},
        )
    )

    message = await _get_message(database_url, 200)
    conversation = await _get_conversation(database_url, 100)
    event = await _latest_event(database_url, 100)
    assert message.f_status == MessageStatus.RESPONDED.value
    assert conversation.f_active_run_id is None
    assert event.f_payload["core_event_id"] == "core-accepted-late"
    assert event.f_payload["message_status"] == "responded"


@pytest.mark.asyncio
async def test_consumer_acks_after_successful_manual_processing(database_url: str) -> None:
    await _insert_conversation_with_message(database_url, message_status="published")
    consumer = CoreAgentStatusMessageConsumer(handler=_handler(database_url))
    incoming = FakeIncomingMessage(
        _event_body(
            event_id="core-consumer-accepted",
            event_type="core_agent.run.accepted",
            payload={"conversation_id": "100", "content": "accepted"},
        )
    )

    await consumer.process_message(incoming)

    assert incoming.ack_calls == 1
    assert incoming.reject_calls == []


@pytest.mark.asyncio
async def test_consumer_rejects_to_dlq_when_processing_raises() -> None:
    consumer = CoreAgentStatusMessageConsumer(handler=FailingHandler())
    incoming = FakeIncomingMessage(
        _event_body(
            event_id="core-consumer-failed",
            event_type="core_agent.run.accepted",
            payload={"conversation_id": "100", "content": "accepted"},
        )
    )

    await consumer.process_message(incoming)

    assert incoming.ack_calls == 0
    assert incoming.reject_calls == [{"requeue": False}]


def _handler(database_url: str) -> CoreAgentStatusEventHandler:
    engine = create_async_engine(database_url)
    session_factory = create_async_session_factory(engine)
    return CoreAgentStatusEventHandler(
        unit_of_work_factory=lambda: SqlAlchemyUnitOfWork(session_factory),
        id_generator=FakeIdGenerator(start=1_000),
    )


def _command(
    *,
    event_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> CoreAgentStatusEventCommand:
    return CoreAgentStatusEventCommand(
        event_id=event_id,
        event_type=event_type,
        event_version="v1",
        conversation_id=100,
        payload=payload,
        occurred_time=1_800_000_000_100,
    )


def _event_body(
    *,
    event_id: str,
    event_type: str,
    payload: dict[str, Any],
) -> bytes:
    return json.dumps(
        {
            "event_id": event_id,
            "event_type": event_type,
            "occurred_at": "2026-04-23T10:00:00Z",
            "source_service": "core_agent_service",
            "payload": payload,
        }
    ).encode("utf-8")


async def _insert_conversation_with_message(
    database_url: str,
    *,
    message_status: str,
    interaction_status: str = "thinking",
) -> None:
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(
            ConversationModel.__table__.insert().values(
                f_conversation_id=100,
                f_owner_user_id="user-001",
                f_tenant_id=None,
                f_title="restore backup",
                f_display_summary=None,
                f_status="active",
                f_active_run_id=(
                    "200"
                    if interaction_status in {"thinking", "executing", "clarifying"}
                    else None
                ),
                f_scenario_binding=None,
                f_tags=[],
                f_retention_policy="conversation_default_v1",
                f_legal_hold=False,
                f_last_active_time=1_800_000_000_000,
                f_archived_time=None,
                f_archived_by=None,
                f_archive_reason=None,
                f_expires_time=None,
                f_expired_time=None,
                f_purge_after_time=None,
                f_purged_time=None,
                f_version=1,
                f_created_time=1_800_000_000_000,
                f_updated_time=1_800_000_000_000,
            )
        )
        await connection.execute(
            ConversationMessageModel.__table__.insert().values(
                f_message_id=200,
                f_conversation_id=100,
                f_parent_message_id=None,
                f_turn_id=200,
                f_role="user",
                f_content_type="text",
                f_content="restore backup",
                f_rich_payload=None,
                f_status=message_status,
                f_client_message_id="client-001",
                f_idempotency_key="idem-001",
                f_trace_id="trace-001",
                f_correlation_id="corr-001",
                f_error_code=None,
                f_created_time=1_800_000_000_000,
                f_updated_time=1_800_000_000_000,
            )
        )
        await connection.execute(
            ConversationStatusEventModel.__table__.insert().values(
                f_status_event_id=300,
                f_conversation_id=100,
                f_sequence=1,
                f_event_type="message.created",
                f_event_version="v1",
                f_message_id=200,
                f_turn_id=200,
                f_payload={"message_status": message_status},
                f_visible_to_user=True,
                f_trace_id="trace-001",
                f_correlation_id="corr-001",
                f_created_time=1_800_000_000_000,
                f_updated_time=1_800_000_000_000,
            )
        )
    await engine.dispose()


async def _get_message(database_url: str, message_id: int) -> ConversationMessageModel:
    engine = create_async_engine(database_url)
    session_factory = create_async_session_factory(engine)
    async with session_factory() as session:
        row = await session.scalar(
            select(ConversationMessageModel).where(
                ConversationMessageModel.f_message_id == message_id
            )
        )
    await engine.dispose()
    assert row is not None
    return row


async def _get_conversation(database_url: str, conversation_id: int) -> ConversationModel:
    engine = create_async_engine(database_url)
    session_factory = create_async_session_factory(engine)
    async with session_factory() as session:
        row = await session.scalar(
            select(ConversationModel).where(
                ConversationModel.f_conversation_id == conversation_id
            )
        )
    await engine.dispose()
    assert row is not None
    return row


async def _latest_event(database_url: str, conversation_id: int) -> ConversationStatusEventModel:
    engine = create_async_engine(database_url)
    session_factory = create_async_session_factory(engine)
    async with session_factory() as session:
        row = await session.scalar(
            select(ConversationStatusEventModel)
            .where(ConversationStatusEventModel.f_conversation_id == conversation_id)
            .order_by(ConversationStatusEventModel.f_sequence.desc())
            .limit(1)
        )
    await engine.dispose()
    assert row is not None
    return row


async def _event_types(database_url: str, conversation_id: int) -> list[str]:
    engine = create_async_engine(database_url)
    session_factory = create_async_session_factory(engine)
    async with session_factory() as session:
        rows = await session.scalars(
            select(ConversationStatusEventModel.f_event_type)
            .where(ConversationStatusEventModel.f_conversation_id == conversation_id)
            .order_by(ConversationStatusEventModel.f_sequence.asc())
        )
    await engine.dispose()
    return list(rows.all())


async def _status_event_count(database_url: str) -> int:
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        count = await connection.scalar(
            select(func.count(ConversationStatusEventModel.f_status_event_id))
        )
    await engine.dispose()
    return int(count or 0)


class FakeIdGenerator:
    def __init__(self, *, start: int) -> None:
        self._next = start

    def next_id(self) -> int:
        current = self._next
        self._next += 1
        return current


class FakeIncomingMessage:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.ack_calls = 0
        self.reject_calls: list[dict[str, bool]] = []

    async def ack(self) -> None:
        self.ack_calls += 1

    async def reject(self, *, requeue: bool) -> None:
        self.reject_calls.append({"requeue": requeue})


class FailingHandler:
    async def handle(self, command: CoreAgentStatusEventCommand) -> object:
        del command
        raise RuntimeError("boom")
