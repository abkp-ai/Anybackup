import asyncio
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import create_async_engine

from app.application.use_cases.retention import RetentionWorker
from app.bootstrap.app_factory import create_app
from app.bootstrap.settings import Settings
from app.infrastructure.persistence.sqlalchemy.models import (
    Base,
    ConversationMessageModel,
    ConversationModel,
    ConversationStatusEventModel,
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
            snowflake_node_id=13,
            snowflake_epoch_ms=1_735_689_600_000,
        )
    )

    with TestClient(app) as test_client:
        yield test_client

    asyncio.run(app.state.container.database_engine().dispose())


def test_manual_archive_and_restore_create_status_events(client: TestClient) -> None:
    created = _create_idle_conversation(client, "manual-archive")
    conversation_id = created["conversation_id"]

    archived = client.post(
        f"{API_PREFIX}/conversations/{conversation_id}/archive",
        headers={"X-User": _x_user("user-001")},
        json={"reason": "done"},
    )
    restored = client.post(
        f"{API_PREFIX}/conversations/{conversation_id}/restore",
        headers={"X-User": _x_user("user-001")},
        json={"reason": "continue"},
    )

    assert archived.status_code == 200
    assert archived.json()["status"] == "archived"
    assert archived.json()["archived_by"] == "user"
    assert restored.status_code == 200
    assert restored.json()["status"] == "active"
    assert restored.json()["has_active_run"] is False
    assert asyncio.run(_status_event_count(client, int(conversation_id))) == 3


def test_archive_restore_and_legal_hold_reject_non_owner(client: TestClient) -> None:
    conversation_id = _create_idle_conversation(client, "owner-boundary-retention")[
        "conversation_id"
    ]

    archive = client.post(
        f"{API_PREFIX}/conversations/{conversation_id}/archive",
        headers={"X-User": _x_user("other-user")},
        json={"reason": "cross-user"},
    )
    restore = client.post(
        f"{API_PREFIX}/conversations/{conversation_id}/restore",
        headers={"X-User": _x_user("other-user")},
        json={"reason": "cross-user"},
    )
    legal_hold = client.post(
        f"{API_PREFIX}/conversations/{conversation_id}/legal-hold",
        headers={"X-User": _x_user("other-user")},
        json={"enabled": True, "reason": "cross-user"},
    )

    assert archive.status_code == 403
    assert archive.json()["error"]["code"] == "FORBIDDEN"
    assert restore.status_code == 403
    assert restore.json()["error"]["code"] == "FORBIDDEN"
    assert legal_hold.status_code == 403
    assert legal_hold.json()["error"]["code"] == "FORBIDDEN"


def test_restore_blocks_active_conversation(client: TestClient) -> None:
    created = _create_idle_conversation(client, "restore-active")
    conversation_id = created["conversation_id"]

    response = client.post(
        f"{API_PREFIX}/conversations/{conversation_id}/restore",
        headers={"X-User": _x_user("user-001")},
        json={"reason": "continue"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONVERSATION_STATE_CONFLICT"


def test_manual_archive_blocks_in_progress_conversation(client: TestClient) -> None:
    created = _create_idle_conversation(client, "archive-busy")
    conversation_id = int(created["conversation_id"])
    asyncio.run(_set_conversation(client, conversation_id, f_active_run_id="run-001"))

    response = client.post(
        f"{API_PREFIX}/conversations/{conversation_id}/archive",
        headers={"X-User": _x_user("user-001")},
        json={"reason": "done"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONVERSATION_BUSY"


def test_manual_archive_blocks_legal_hold_conversation(client: TestClient) -> None:
    created = _create_idle_conversation(client, "archive-legal-hold")
    conversation_id = int(created["conversation_id"])
    asyncio.run(_set_conversation(client, conversation_id, f_legal_hold=True))

    response = client.post(
        f"{API_PREFIX}/conversations/{conversation_id}/archive",
        headers={"X-User": _x_user("user-001")},
        json={"reason": "done"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONVERSATION_BUSY"


def test_retention_worker_archives_and_expires_with_redis_lock(client: TestClient) -> None:
    active_id = int(_create_idle_conversation(client, "auto-archive")["conversation_id"])
    archived_id = int(_create_idle_conversation(client, "auto-expire")["conversation_id"])
    now_ms = 1_800_000_000_000
    asyncio.run(
        _set_conversation(
            client,
            active_id,
            f_last_active_time=now_ms - 31 * 86_400_000,
        )
    )
    asyncio.run(
        _set_conversation(
            client,
            archived_id,
            f_status="archived",
            f_archived_time=now_ms - 366 * 86_400_000,
            f_active_run_id=None,
        )
    )
    worker = _worker(client, lock=FakeLock(acquired=True))

    result = asyncio.run(worker.run_once(worker_id="worker-001", now_ms=now_ms))

    active = asyncio.run(_get_conversation(client, active_id))
    archived = asyncio.run(_get_conversation(client, archived_id))
    assert result.lock_acquired is True
    assert result.archived_count == 1
    assert result.expired_count == 1
    assert active.f_status == "archived"
    assert active.f_archived_by == "system"
    assert active.f_archive_reason == "inactivity_30d"
    assert archived.f_status == "expired"
    assert archived.f_expired_time == now_ms


def test_retention_worker_skips_legal_hold_and_held_lock(client: TestClient) -> None:
    conversation_id = int(_create_idle_conversation(client, "legal-hold")["conversation_id"])
    now_ms = 1_800_000_000_000
    asyncio.run(
        _set_conversation(
            client,
            conversation_id,
            f_last_active_time=now_ms - 31 * 86_400_000,
            f_legal_hold=True,
        )
    )
    skipped = asyncio.run(_worker(client, lock=FakeLock(acquired=False)).run_once(
        worker_id="worker-001",
        now_ms=now_ms,
    ))
    result = asyncio.run(_worker(client, lock=FakeLock(acquired=True)).run_once(
        worker_id="worker-002",
        now_ms=now_ms,
    ))

    row = asyncio.run(_get_conversation(client, conversation_id))
    assert skipped.lock_acquired is False
    assert result.archived_count == 0
    assert row.f_status == "active"


def test_legal_hold_api_updates_flag(client: TestClient) -> None:
    conversation_id = _create_idle_conversation(client, "hold-api")["conversation_id"]

    held = client.post(
        f"{API_PREFIX}/conversations/{conversation_id}/legal-hold",
        headers={"X-User": _x_user("user-001")},
        json={"enabled": True, "reason": "audit"},
    )
    released = client.post(
        f"{API_PREFIX}/conversations/{conversation_id}/legal-hold",
        headers={"X-User": _x_user("user-001")},
        json={"enabled": False, "reason": "done"},
    )

    assert held.status_code == 200
    assert held.json()["legal_hold"] is True
    assert released.status_code == 200
    assert released.json()["legal_hold"] is False


def test_expired_conversation_remains_readonly_and_not_hard_deleted(client: TestClient) -> None:
    conversation_id = int(_create_idle_conversation(client, "expired-readonly")["conversation_id"])
    asyncio.run(_set_conversation(client, conversation_id, f_status="expired"))

    response = client.post(
        f"{API_PREFIX}/conversations/{conversation_id}/messages",
        headers={"X-User": _x_user("user-001"), "Idempotency-Key": "expired-message"},
        json={
            "type": "user_message",
            "content": "try write",
            "client_message_id": "expired-message",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONVERSATION_EXPIRED"
    assert asyncio.run(_conversation_count(client, conversation_id)) == 1


def _create_idle_conversation(client: TestClient, content: str) -> dict[str, str]:
    response = client.post(
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
    assert response.status_code == 201
    body = response.json()
    asyncio.run(
        _set_conversation(
            client,
            int(body["conversation"]["conversation_id"]),
            f_active_run_id=None,
        )
    )
    asyncio.run(_set_message(client, int(body["message"]["message_id"]), f_status="responded"))
    return {
        "conversation_id": body["conversation"]["conversation_id"],
        "message_id": body["message"]["message_id"],
    }


def _worker(client: TestClient, *, lock: "FakeLock") -> RetentionWorker:
    engine = client.app.state.container.database_engine()
    session_factory = create_async_session_factory(engine)
    return RetentionWorker(
        unit_of_work_factory=lambda: SqlAlchemyUnitOfWork(session_factory),
        id_generator=FakeIdGenerator(start=30_000),
        lock=lock,
        lock_ttl_ms=30_000,
        auto_archive_after_days=30,
        archive_retention_days=365,
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


async def _get_conversation(client: TestClient, conversation_id: int) -> ConversationModel:
    engine = client.app.state.container.database_engine()
    session_factory = create_async_session_factory(engine)
    async with session_factory() as session:
        row = await session.scalar(
            select(ConversationModel).where(
                ConversationModel.f_conversation_id == conversation_id
            )
        )
    assert row is not None
    return row


async def _status_event_count(client: TestClient, conversation_id: int) -> int:
    engine = client.app.state.container.database_engine()
    async with engine.connect() as connection:
        count = await connection.scalar(
            select(func.count(ConversationStatusEventModel.f_status_event_id)).where(
                ConversationStatusEventModel.f_conversation_id == conversation_id
            )
        )
    return int(count or 0)


async def _conversation_count(client: TestClient, conversation_id: int) -> int:
    engine = client.app.state.container.database_engine()
    async with engine.connect() as connection:
        count = await connection.scalar(
            select(func.count(ConversationModel.f_conversation_id)).where(
                ConversationModel.f_conversation_id == conversation_id
            )
        )
    return int(count or 0)


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
