import asyncio
import json
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from app.application.commands.agent_events import (
    CoreAgentStatusEventCommand,
    DecisionAgentAgUiEventCommand,
)
from app.application.models.outbox import OutboxPublishMessage
from app.application.use_cases.outbox import OutboxPublisherWorker
from app.bootstrap.app_factory import create_app
from app.bootstrap.settings import Settings
from app.infrastructure.persistence.sqlalchemy.models import (
    Base,
    ConversationModel,
)
from app.infrastructure.persistence.sqlalchemy.session import create_async_session_factory
from app.infrastructure.persistence.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWork
from app.interfaces.mq.agent_status_consumer import CoreAgentStatusMessageConsumer
from app.interfaces.mq.decision_agent_ag_ui_consumer import DecisionAgentAgUiMessageConsumer

MOCK_SRC_PATH = Path(__file__).resolve().parents[2] / "tools" / "conversation_agent_mq_mock" / "src"
sys.path.insert(0, str(MOCK_SRC_PATH))

from conversation_agent_mq_mock.runner import AgentMqMockRunner  # noqa: E402
from conversation_agent_mq_mock.settings import Settings as MockSettings  # noqa: E402

API_PREFIX = "/api/conversation_service/v1"


@pytest.fixture()
def client(tmp_path: Path) -> Iterator[TestClient]:
    database_path = tmp_path / "conversation.db"
    database_url = f"sqlite+aiosqlite:///{database_path.as_posix()}"

    async def create_schema() -> None:
        engine = create_async_engine(database_url)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(create_schema())
    app = create_app(
        Settings(
            database_url=database_url,
            snowflake_node_id=16,
            core_agent_service_token="agent-token",
        )
    )

    with TestClient(app) as test_client:
        yield test_client

    asyncio.run(app.state.container.database_engine().dispose())


def test_user_message_to_decision_agent_ag_ui_is_visible_to_frontend(
    client: TestClient,
) -> None:
    created = client.post(
        f"{API_PREFIX}/conversations",
        headers={
            "X-User": _x_user("user-001"),
            "Idempotency-Key": "e2e-create",
            "X-Request-Id": "req-e2e-001",
        },
        json={
            "initial_message": {
                "type": "user_message",
                "content": "Find the latest safe restore point",
                "client_message_id": "client-e2e-001",
            },
            "title": "E2E restore",
            "tags": ["e2e"],
            "source": "web",
        },
    )
    assert created.status_code == 201
    created_body = created.json()
    conversation_id = created_body["conversation"]["conversation_id"]
    message_id = created_body["message"]["message_id"]
    output_message_id = _assistant_output_message_id(message_id)

    asyncio.run(_publish_outbox(client))
    asyncio.run(
        _mark_agent_accepted(
            client,
            conversation_id=conversation_id,
            message_id=message_id,
        )
    )

    asyncio.run(
        _persist_decision_agent_ag_ui(
            client,
            conversation_id=conversation_id,
            turn_id=int(message_id),
            message_id=output_message_id,
        )
    )

    messages = client.get(
        f"{API_PREFIX}/conversations/{conversation_id}/messages",
        headers={"X-User": _x_user("user-001")},
    )
    events = client.get(
        f"{API_PREFIX}/conversations/{conversation_id}/events",
        headers={"X-User": _x_user("user-001")},
    )

    assert messages.status_code == 200
    message_items = messages.json()["items"]
    assert [item["role"] for item in message_items] == ["user", "assistant"]
    assert message_items[0]["status"] == "responded"
    assert message_items[1]["status"] == "responded"
    assert events.status_code == 200
    assert {item["event_type"] for item in events.json()["items"]} >= {
        "message.created",
        "message.updated",
    }


def test_visible_error_mock_runner_closes_turn_as_completed(client: TestClient) -> None:
    created = client.post(
        f"{API_PREFIX}/conversations",
        headers={
            "X-User": _x_user("user-001"),
            "Idempotency-Key": "e2e-visible-error",
            "X-Request-Id": "req-e2e-visible-error",
        },
        json={
            "initial_message": {
                "type": "user_message",
                "content": "visible error panel",
                "client_message_id": "client-e2e-visible-error",
            },
            "title": "E2E visible error",
            "tags": ["e2e", "mock"],
            "source": "web",
        },
    )
    assert created.status_code == 201
    created_body = created.json()
    conversation_id = created_body["conversation"]["conversation_id"]
    message_id = created_body["message"]["message_id"]
    asyncio.run(_publish_outbox(client))

    publisher = CollectingPublisher()
    runner = AgentMqMockRunner(
        settings=MockSettings(
            rabbitmq_url="amqp://guest:guest@localhost:5672/",
            conversation_exchange="conversation.message.events",
            core_status_queue="conversation.core_agent.run_status",
            delay_ms=0,
        ),
        publisher=publisher,
    )
    asyncio.run(
        runner.handle_body(
            {
                "event_id": f"conversation.message.sent.{message_id}",
                "event_type": "conversation.message.sent",
                "trace_id": "trace-e2e-mock-visible-error",
                "correlation_id": "corr-e2e-mock-visible-error",
                "payload": {
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "turn_id": message_id,
                    "content": "visible error panel",
                },
            }
        )
    )

    core_consumer = CoreAgentStatusMessageConsumer(
        handler=client.app.state.container.core_agent_status_handler()
    )
    ag_ui_consumer = DecisionAgentAgUiMessageConsumer(
        handler=client.app.state.container.decision_agent_ag_ui_handler()
    )
    asyncio.run(_consume_mock_messages(publisher.messages, core_consumer, ag_ui_consumer))

    messages = client.get(
        f"{API_PREFIX}/conversations/{conversation_id}/messages",
        headers={"X-User": _x_user("user-001")},
    )
    events = client.get(
        f"{API_PREFIX}/conversations/{conversation_id}/events",
        headers={"X-User": _x_user("user-001")},
    )

    conversation = asyncio.run(_conversation_record(client, int(conversation_id)))
    assert conversation.f_active_run_id is None
    assert conversation.f_active_turn_id is None
    assert messages.status_code == 200
    message_items = messages.json()["items"]
    assert [item["status"] for item in message_items] == ["responded", "responded"]
    assert events.status_code == 200
    events_body = events.json()
    assert events_body["has_active_run"] is False
    assert {item["event_type"] for item in events_body["items"]} >= {
        "message.created",
        "message.updated",
        "rich_content.created",
    }


async def _persist_decision_agent_ag_ui(
    client: TestClient,
    *,
    conversation_id: str,
    turn_id: int,
    message_id: int,
) -> None:
    handler = client.app.state.container.decision_agent_ag_ui_handler()
    await handler.handle(
        DecisionAgentAgUiEventCommand(
            event_id="decision-agent.agui.e2e.1",
            event_type="decision_agent.session.ag_ui_event",
            source_service="decision_agent_session",
            conversation_id=int(conversation_id),
            turn_id=turn_id,
            message_id=message_id,
            content="Use restore point rp-001.",
            sequence=1,
            ag_ui="# Restore plan\n\nUse restore point rp-001.",
            trace_id="trace-e2e",
            correlation_id="corr-e2e",
            occurred_time=1_800_000_000_100,
        )
    )


async def _mark_agent_accepted(
    client: TestClient,
    *,
    conversation_id: str,
    message_id: str,
) -> None:
    handler = client.app.state.container.core_agent_status_handler()
    await handler.handle(
        CoreAgentStatusEventCommand(
            event_id=f"core-agent.accepted.{message_id}",
            event_type="core_agent.run.accepted",
            event_version="v1",
            conversation_id=int(conversation_id),
            payload={"conversation_id": conversation_id, "content": "accepted"},
            occurred_time=1_800_000_000_000,
        )
    )


async def _publish_outbox(client: TestClient) -> None:
    engine = client.app.state.container.database_engine()
    session_factory = create_async_session_factory(engine)
    worker = OutboxPublisherWorker(
        unit_of_work_factory=lambda: SqlAlchemyUnitOfWork(session_factory),
        publisher=FakePublisher(),
        lock=FakeLock(acquired=True),
        exchange_name="conversation.message.events",
        batch_size=10,
        max_attempts=3,
        retry_delay_ms=1_000,
        lock_ttl_ms=30_000,
    )
    result = await worker.run_once(worker_id="e2e-worker", now_ms=1_800_000_000_000)
    assert result.published == 1


def _assistant_output_message_id(source_message_id: str) -> int:
    return int(source_message_id) + 10_000


async def _conversation_record(client: TestClient, conversation_id: int) -> ConversationModel:
    session_factory = client.app.state.container.async_session_factory()
    async with session_factory() as session:
        row = await session.scalar(
            select(ConversationModel).where(
                ConversationModel.f_conversation_id == conversation_id
            )
        )
    assert row is not None
    return row


def _x_user(user_id: str) -> str:
    return json.dumps(
        {
            "sub": user_id,
            "preferred_username": user_id,
            "name": user_id,
            "email": f"{user_id}@example.com",
            "email_verified": True,
            "roles": ["backup_admin"],
        }
    )


class FakePublisher:
    async def publish(self, message: OutboxPublishMessage) -> None:
        self.message = message


class CollectingPublisher:
    def __init__(self) -> None:
        self.messages: list[object] = []

    async def publish(self, message: object) -> None:
        self.messages.append(message)


class FakeLease:
    async def release(self) -> None:
        return None


class FakeLock:
    def __init__(self, *, acquired: bool) -> None:
        self.acquired = acquired

    async def acquire(self, key: str, ttl_ms: int) -> FakeLease | None:
        self.acquire_call = {"key": key, "ttl_ms": ttl_ms}
        if not self.acquired:
            return None
        return FakeLease()


class FakeIncomingMessage:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.ack_calls = 0
        self.reject_calls: list[dict[str, bool]] = []

    async def ack(self) -> None:
        self.ack_calls += 1

    async def reject(self, *, requeue: bool) -> None:
        self.reject_calls.append({"requeue": requeue})


async def _consume_mock_messages(
    messages: list[object],
    core_consumer: CoreAgentStatusMessageConsumer,
    ag_ui_consumer: DecisionAgentAgUiMessageConsumer,
) -> None:
    for message in messages:
        body = json.dumps(message.body).encode("utf-8")
        incoming = FakeIncomingMessage(body)
        if getattr(message, "routing_key", "") == "conversation.core_agent.run_status":
            await core_consumer.process_message(incoming)
        elif getattr(message, "exchange", None) == "decision_agent.bizdata.events":
            await ag_ui_consumer.process_message(incoming)
        else:
            raise AssertionError(f"unexpected mock output message: {message!r}")
        assert incoming.ack_calls == 1
        assert incoming.reject_calls == []
