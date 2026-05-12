import asyncio
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import create_async_engine

from app.application.commands.agent_events import DecisionAgentAgUiEventCommand
from app.application.use_cases.decision_agent_ag_ui import DecisionAgentAgUiEventHandler
from app.domain.shared.errors import DomainError, ErrorReason
from app.infrastructure.persistence.sqlalchemy.models import (
    Base,
    ConversationMessageModel,
    ConversationModel,
    ConversationStatusEventModel,
    ConversationWritebackIdempotencyModel,
)
from app.infrastructure.persistence.sqlalchemy.session import create_async_session_factory
from app.infrastructure.persistence.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWork
from app.interfaces.mq.decision_agent_ag_ui_consumer import DecisionAgentAgUiMessageConsumer


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
async def test_ag_ui_event_is_persisted_as_wire_event_payload(database_url: str) -> None:
    await _insert_processing_conversation(database_url)
    handler = _handler(database_url)

    result = await handler.handle(_command(event_id="state-snapshot-001", sequence=1))

    assert result.idempotent is False
    assert result.result_status == "accepted"
    event = await _latest_status_event(database_url)
    assert event.f_event_type == "STATE_SNAPSHOT"
    assert event.f_payload == _ag_ui_event(
        event_id="state-snapshot-001",
        event_type="STATE_SNAPSHOT",
        sequence=1,
    )
    assert await _count(database_url, ConversationWritebackIdempotencyModel.f_writeback_id) == 1


@pytest.mark.asyncio
async def test_run_finished_event_closes_active_run(database_url: str) -> None:
    await _insert_processing_conversation(database_url)
    handler = _handler(database_url)

    await handler.handle(
        _command(
            event_id="run-finished-001",
            sequence=1,
            ag_ui_event=_ag_ui_event(
                event_id="run-finished-001",
                event_type="RUN_FINISHED",
                sequence=1,
            ),
        )
    )

    conversation = await _get_conversation(database_url)
    assert conversation.f_active_run_id is None


@pytest.mark.asyncio
async def test_ag_ui_event_rejects_sequence_gap(database_url: str) -> None:
    await _insert_processing_conversation(database_url)
    handler = _handler(database_url)

    with pytest.raises(DomainError) as exc_info:
        await handler.handle(_command(event_id="state-snapshot-gap", sequence=2))

    assert exc_info.value.reason is ErrorReason.CONVERSATION_WRITEBACK_STALE
    assert await _count(database_url, ConversationWritebackIdempotencyModel.f_writeback_id) == 1


@pytest.mark.asyncio
async def test_duplicate_ag_ui_event_is_idempotent(database_url: str) -> None:
    await _insert_processing_conversation(database_url)
    handler = _handler(database_url)
    command = _command(event_id="state-snapshot-duplicate", sequence=1)

    first = await handler.handle(command)
    second = await handler.handle(command)

    assert first.idempotent is False
    assert second.idempotent is True
    assert await _count(database_url, ConversationWritebackIdempotencyModel.f_writeback_id) == 1


@pytest.mark.asyncio
async def test_consumer_acks_after_successful_ag_ui_event_processing(database_url: str) -> None:
    await _insert_processing_conversation(database_url)
    consumer = DecisionAgentAgUiMessageConsumer(handler=_handler(database_url))
    incoming = FakeIncomingMessage(_event_body(event_id="consumer-accepted", sequence=1))

    await consumer.process_message(incoming)

    assert incoming.ack_calls == 1
    assert incoming.reject_calls == []


@pytest.mark.asyncio
async def test_consumer_rejects_snapshot_field_to_dlq(database_url: str) -> None:
    await _insert_processing_conversation(database_url)
    consumer = DecisionAgentAgUiMessageConsumer(handler=_handler(database_url))
    invalid_event = {
        **_ag_ui_event(event_id="consumer-invalid", event_type="STATE_SNAPSHOT", sequence=2),
        "snapshot": {},
    }
    invalid_event.pop("state")
    incoming = FakeIncomingMessage(
        _event_body(event_id="consumer-invalid", sequence=2, ag_ui_event=invalid_event)
    )

    await consumer.process_message(incoming)

    assert incoming.ack_calls == 0
    assert incoming.reject_calls == [{"requeue": False}]


@pytest.mark.asyncio
async def test_consumer_rejects_to_dlq_when_processing_raises() -> None:
    consumer = DecisionAgentAgUiMessageConsumer(handler=FailingHandler())
    incoming = FakeIncomingMessage(_event_body(event_id="consumer-failed", sequence=2))

    await consumer.process_message(incoming)

    assert incoming.ack_calls == 0
    assert incoming.reject_calls == [{"requeue": False}]


def _handler(database_url: str) -> DecisionAgentAgUiEventHandler:
    engine = create_async_engine(database_url)
    session_factory = create_async_session_factory(engine)
    return DecisionAgentAgUiEventHandler(
        unit_of_work_factory=lambda: SqlAlchemyUnitOfWork(session_factory),
        id_generator=FakeIdGenerator(start=1_000),
    )


def _command(
    *,
    event_id: str,
    sequence: int,
    ag_ui_event: dict[str, object] | None = None,
) -> DecisionAgentAgUiEventCommand:
    return DecisionAgentAgUiEventCommand(
        event_id=event_id,
        event_type="decision_agent.session.ag_ui_event",
        source_service="decision_agent_session",
        conversation_id=100,
        turn_id=200,
        message_id=901,
        sequence=sequence,
        ag_ui_event=ag_ui_event
        or _ag_ui_event(event_id=event_id, event_type="STATE_SNAPSHOT", sequence=sequence),
        trace_id="trace-agui",
        correlation_id="corr-agui",
        occurred_time=1_800_000_000_100,
    )


def _ag_ui_event(
    *,
    event_id: str,
    event_type: str,
    sequence: int,
) -> dict[str, object]:
    event: dict[str, object] = {
        "type": event_type,
        "eventId": event_id,
        "threadId": "100",
        "runId": "run-100",
        "sequence": sequence,
    }
    if event_type == "STATE_SNAPSHOT":
        event["state"] = {"selection": {"required": False}}
    if event_type == "TOOL_CALL_RESULT":
        event["result"] = {
            "decision": "approved",
            "actorRef": "user-001",
            "occurredAt": "2026-05-12T10:00:00Z",
            "summary": "User approved the tool call",
        }
    return event


def _event_body(
    *,
    event_id: str,
    sequence: int,
    ag_ui_event: dict[str, object] | None = None,
) -> bytes:
    return json.dumps(
        {
            "event_id": event_id,
            "event_type": "decision_agent.session.ag_ui_event",
            "occurred_at": "2026-04-23T10:00:00Z",
            "source_service": "decision_agent_session",
            "trace_id": "trace-agui",
            "correlation_id": "corr-agui",
            "payload": {
                "conversation_id": "100",
                "turn_id": "200",
                "message_id": "901",
                "sequence": sequence,
                "ag_ui_event": ag_ui_event
                or _ag_ui_event(event_id=event_id, event_type="STATE_SNAPSHOT", sequence=sequence),
            },
        }
    ).encode("utf-8")


async def _insert_processing_conversation(database_url: str) -> None:
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
                f_active_run_id="run-100",
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
                f_status="processing",
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
                f_event_type="RUN_STARTED",
                f_event_version="v1",
                f_message_id=200,
                f_turn_id=200,
                f_payload={
                    "type": "RUN_STARTED",
                    "eventId": "run-started",
                    "threadId": "100",
                    "runId": "run-100",
                    "sequence": 1,
                },
                f_visible_to_user=True,
                f_trace_id="trace-001",
                f_correlation_id="corr-001",
                f_created_time=1_800_000_000_000,
                f_updated_time=1_800_000_000_000,
            )
        )
    await engine.dispose()


async def _latest_status_event(database_url: str) -> ConversationStatusEventModel:
    engine = create_async_engine(database_url)
    session_factory = create_async_session_factory(engine)
    async with session_factory() as session:
        row = await session.scalar(
            select(ConversationStatusEventModel).order_by(
                ConversationStatusEventModel.f_sequence.desc()
            )
        )
    await engine.dispose()
    assert row is not None
    return row


async def _get_conversation(database_url: str) -> ConversationModel:
    engine = create_async_engine(database_url)
    session_factory = create_async_session_factory(engine)
    async with session_factory() as session:
        row = await session.scalar(
            select(ConversationModel).where(ConversationModel.f_conversation_id == 100)
        )
    await engine.dispose()
    assert row is not None
    return row


async def _count(database_url: str, column: object) -> int:
    engine = create_async_engine(database_url)
    async with engine.connect() as connection:
        count = await connection.scalar(select(func.count(column)))
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
    async def handle(self, command: DecisionAgentAgUiEventCommand) -> object:
        del command
        raise RuntimeError("boom")
