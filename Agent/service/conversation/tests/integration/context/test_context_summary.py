import asyncio
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import create_async_engine

from app.application.use_cases.context import ContextMergeWorker
from app.bootstrap.app_factory import create_app
from app.bootstrap.settings import Settings
from app.infrastructure.persistence.sqlalchemy.models import (
    Base,
    ConversationContextDeltaModel,
    ConversationContextSnapshotModel,
    ConversationMessageModel,
    ConversationModel,
    ConversationMqOutboxModel,
)
from app.infrastructure.persistence.sqlalchemy.session import create_async_session_factory
from app.infrastructure.persistence.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWork

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
            snowflake_node_id=11,
            snowflake_epoch_ms=1_735_689_600_000,
            core_agent_service_token="agent-token",
        )
    )

    with TestClient(app) as test_client:
        yield test_client

    asyncio.run(app.state.container.database_engine().dispose())


def test_get_context_returns_current_snapshot_and_pending_delta(client: TestClient) -> None:
    created = _create_conversation_with_delta(client, "context-get")
    conversation_id = created["conversation_id"]
    asyncio.run(
        _insert_snapshot(
            client,
            conversation_id=int(conversation_id),
            snapshot_id=9_001,
            version=1,
            short_summary="Current summary",
            structured_state={"target_asset": "orders-db"},
        )
    )

    response = client.get(
        f"{API_PREFIX}/conversations/{conversation_id}/context",
        headers={"X-User": _x_user("user-001")},
    )
    forbidden = client.get(
        f"{API_PREFIX}/conversations/{conversation_id}/context",
        headers={"X-User": _x_user("other-user")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"] == conversation_id
    assert body["snapshot"]["snapshot_version"] == 1
    assert body["snapshot"]["short_summary"] == "Current summary"
    assert body["pending_delta_count"] == 1
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"


def test_context_merge_worker_creates_snapshot_and_marks_delta_merged(
    client: TestClient,
) -> None:
    created = _create_conversation_with_delta(client, "context-merge")
    conversation_id = int(created["conversation_id"])
    worker = _worker(client, lock=FakeLock(acquired=True))

    result = asyncio.run(worker.run_once(worker_id="worker-001", now_ms=1_800_000_100_000))

    snapshot = asyncio.run(_latest_snapshot(client, conversation_id))
    delta = asyncio.run(_latest_delta(client, conversation_id))
    assert result.lock_acquired is True
    assert result.merged_delta_count == 1
    assert snapshot.f_snapshot_version == 1
    assert snapshot.f_short_summary == "Agent recorded target asset."
    assert snapshot.f_structured_state["target_asset"] == "orders-db"
    assert delta.f_merge_status == "merged"


def test_context_merge_worker_respects_redis_lock(client: TestClient) -> None:
    _create_conversation_with_delta(client, "context-lock")
    worker = _worker(client, lock=FakeLock(acquired=False))

    result = asyncio.run(worker.run_once(worker_id="worker-001", now_ms=1_800_000_100_000))

    assert result.lock_acquired is False
    assert result.merged_delta_count == 0


def test_context_merge_failure_marks_delta_failed_without_replacing_messages(
    client: TestClient,
) -> None:
    created = _create_conversation_with_delta(client, "context-failed")
    conversation_id = int(created["conversation_id"])
    before_count = asyncio.run(_message_count(client, conversation_id))
    worker = _worker(client, lock=FakeLock(acquired=True), fail_merge=True)

    result = asyncio.run(worker.run_once(worker_id="worker-001", now_ms=1_800_000_100_000))

    delta = asyncio.run(_latest_delta(client, conversation_id))
    after_count = asyncio.run(_message_count(client, conversation_id))
    assert result.failed_delta_count == 1
    assert delta.f_merge_status == "failed"
    assert after_count == before_count


def test_next_user_message_outbox_uses_minimal_contract_payload(
    client: TestClient,
) -> None:
    created = _create_conversation_with_delta(client, "context-outbox")
    conversation_id = int(created["conversation_id"])
    asyncio.run(
        _insert_snapshot(
            client,
            conversation_id=conversation_id,
            snapshot_id=9_002,
            version=1,
            short_summary="Use latest orders-db backup.",
            structured_state={"target_asset": "orders-db"},
        )
    )
    asyncio.run(_set_conversation(client, conversation_id, f_active_run_id=None))

    response = client.post(
        f"{API_PREFIX}/conversations/{conversation_id}/messages",
        headers={"X-User": _x_user("user-001"), "Idempotency-Key": "context-next-msg"},
        json={
            "type": "user_message",
            "content": "Continue",
            "client_message_id": "context-next-msg",
        },
    )

    outbox = asyncio.run(_latest_outbox(client, conversation_id))
    assert response.status_code == 202
    message_id = response.json()["message"]["message_id"]
    assert outbox.f_payload == {
        "conversation_id": str(conversation_id),
        "message_id": message_id,
        "turn_id": response.json()["message"]["turn_id"],
        "content": "Continue",
    }


def _create_conversation_with_delta(client: TestClient, content: str) -> dict[str, str]:
    created = client.post(
        f"{API_PREFIX}/conversations",
        headers={"X-User": _x_user("user-001"), "Idempotency-Key": f"create-{content}"},
        json={
            "initial_message": {
                "type": "user_message",
                "content": content,
                "client_message_id": f"client-{content}",
            },
            "title": content,
            "tags": [],
            "source": "web",
        },
    )
    assert created.status_code == 201
    body = created.json()
    asyncio.run(
        _set_conversation(
            client,
            int(body["conversation"]["conversation_id"]),
            f_active_run_id="run-001",
        )
    )
    asyncio.run(_set_message(client, int(body["message"]["message_id"]), f_status="processing"))
    asyncio.run(
        _insert_context_delta(
            client,
            conversation_id=int(body["conversation"]["conversation_id"]),
            message_id=int(body["message"]["message_id"]),
            content=content,
        )
    )
    return {
        "conversation_id": body["conversation"]["conversation_id"],
        "message_id": body["message"]["message_id"],
    }


def _worker(
    client: TestClient,
    *,
    lock: "FakeLock",
    fail_merge: bool = False,
) -> ContextMergeWorker:
    engine = client.app.state.container.database_engine()
    session_factory = create_async_session_factory(engine)
    return ContextMergeWorker(
        unit_of_work_factory=lambda: SqlAlchemyUnitOfWork(session_factory),
        id_generator=FakeIdGenerator(start=20_000),
        lock=lock,
        lock_ttl_ms=30_000,
        fail_merge=fail_merge,
    )


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


async def _insert_snapshot(
    client: TestClient,
    *,
    conversation_id: int,
    snapshot_id: int,
    version: int,
    short_summary: str,
    structured_state: dict[str, Any],
) -> None:
    engine = client.app.state.container.database_engine()
    async with engine.begin() as connection:
        await connection.execute(
            ConversationContextSnapshotModel.__table__.insert().values(
                f_context_snapshot_id=snapshot_id,
                f_conversation_id=conversation_id,
                f_snapshot_version=version,
                f_short_summary=short_summary,
                f_structured_state=structured_state,
                f_last_message_id=None,
                f_status="current",
                f_created_by="summary_updater",
                f_trace_id="trace-snapshot",
                f_created_time=1_800_000_000_000,
                f_updated_time=1_800_000_000_000,
            )
        )


async def _insert_context_delta(
    client: TestClient,
    *,
    conversation_id: int,
    message_id: int,
    content: str,
) -> None:
    delta_id = 8_000 + sum(ord(char) for char in content)
    engine = client.app.state.container.database_engine()
    async with engine.begin() as connection:
        await connection.execute(
            ConversationContextDeltaModel.__table__.insert().values(
                f_context_delta_id=delta_id,
                f_conversation_id=conversation_id,
                f_turn_id=None,
                f_source_message_id=message_id,
                f_base_snapshot_version=None,
                f_delta_payload={
                    "summary_delta": "Agent recorded target asset.",
                    "key_variables": {"target_asset": "orders-db"},
                },
                f_merge_status="pending",
                f_created_by_agent="decision-agent",
                f_trace_id=f"trace-{content}",
                f_created_time=1_800_000_000_100,
                f_updated_time=1_800_000_000_100,
            )
        )


async def _set_conversation(client: TestClient, conversation_id: int, **values: object) -> None:
    engine = client.app.state.container.database_engine()
    async with engine.begin() as connection:
        await connection.execute(
            update(ConversationModel)
            .where(ConversationModel.f_conversation_id == conversation_id)
            .values(**values)
        )


async def _set_message(client: TestClient, message_id: int, **values: object) -> None:
    engine = client.app.state.container.database_engine()
    async with engine.begin() as connection:
        await connection.execute(
            update(ConversationMessageModel)
            .where(ConversationMessageModel.f_message_id == message_id)
            .values(**values)
        )


async def _latest_snapshot(
    client: TestClient,
    conversation_id: int,
) -> ConversationContextSnapshotModel:
    engine = client.app.state.container.database_engine()
    session_factory = create_async_session_factory(engine)
    async with session_factory() as session:
        row = await session.scalar(
            select(ConversationContextSnapshotModel)
            .where(ConversationContextSnapshotModel.f_conversation_id == conversation_id)
            .order_by(ConversationContextSnapshotModel.f_snapshot_version.desc())
            .limit(1)
        )
    assert row is not None
    return row


async def _latest_delta(client: TestClient, conversation_id: int) -> ConversationContextDeltaModel:
    engine = client.app.state.container.database_engine()
    session_factory = create_async_session_factory(engine)
    async with session_factory() as session:
        row = await session.scalar(
            select(ConversationContextDeltaModel)
            .where(ConversationContextDeltaModel.f_conversation_id == conversation_id)
            .order_by(ConversationContextDeltaModel.f_created_time.desc())
            .limit(1)
        )
    assert row is not None
    return row


async def _message_count(client: TestClient, conversation_id: int) -> int:
    engine = client.app.state.container.database_engine()
    async with engine.connect() as connection:
        count = await connection.scalar(
            select(func.count(ConversationMessageModel.f_message_id)).where(
                ConversationMessageModel.f_conversation_id == conversation_id
            )
        )
    return int(count or 0)


async def _latest_outbox(client: TestClient, conversation_id: int) -> ConversationMqOutboxModel:
    engine = client.app.state.container.database_engine()
    session_factory = create_async_session_factory(engine)
    async with session_factory() as session:
        row = await session.scalar(
            select(ConversationMqOutboxModel)
            .where(ConversationMqOutboxModel.f_conversation_id == conversation_id)
            .order_by(ConversationMqOutboxModel.f_created_time.desc())
            .limit(1)
        )
    assert row is not None
    return row


class FakeIdGenerator:
    def __init__(self, *, start: int) -> None:
        self._next = start

    def next_id(self) -> int:
        current = self._next
        self._next += 1
        return current


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
