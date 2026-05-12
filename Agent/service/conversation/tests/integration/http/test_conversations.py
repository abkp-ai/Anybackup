import asyncio
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import create_async_engine

from app.bootstrap.app_factory import create_app
from app.bootstrap.settings import Settings
from app.infrastructure.persistence.sqlalchemy.models import (
    Base,
    ConversationMessageModel,
    ConversationModel,
    ConversationMqOutboxModel,
    ConversationStatusEventModel,
)

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
            snowflake_node_id=7,
            snowflake_epoch_ms=1_735_689_600_000,
        )
    )

    with TestClient(app) as test_client:
        yield test_client

    asyncio.run(app.state.container.database_engine().dispose())


def test_create_conversation_persists_initial_message_event_and_outbox(
    client: TestClient,
) -> None:
    response = client.post(
        f"{API_PREFIX}/conversations",
        headers={
            "X-User": _x_user("user-001"),
            "Idempotency-Key": "create-001",
            "X-Request-Id": "req-create-001",
        },
        json=_create_payload(
            content="Restore the order database",
            title="Order DB restore",
            tags=["restore", "order"],
        ),
    )

    assert response.status_code == 201
    body = response.json()
    conversation = body["conversation"]
    message = body["message"]
    status_event = body["status_event"]

    assert conversation["conversation_id"]
    assert conversation["owner_user_id"] == "user-001"
    assert conversation["title"] == "Order DB restore"
    assert conversation["status"] == "active"
    assert conversation["has_active_run"] is True
    assert conversation["tags"] == ["restore", "order"]
    assert message["conversation_id"] == conversation["conversation_id"]
    assert message["role"] == "user"
    assert message["content_type"] == "text"
    assert message["content"] == "Restore the order database"
    assert message["status"] == "persisted"
    assert status_event["conversation_id"] == conversation["conversation_id"]
    assert status_event["message_id"] == message["message_id"]
    assert status_event["event_type"] == "message.created"
    assert status_event["sequence"] == 1
    assert body["next_poll_after_ms"] == 1000

    counts = asyncio.run(_table_counts(client))
    assert counts == {
        "conversations": 1,
        "messages": 1,
        "status_events": 1,
        "outbox": 1,
    }


def test_create_conversation_is_idempotent(client: TestClient) -> None:
    headers = {
        "X-User": _x_user("user-001"),
        "Idempotency-Key": "create-idempotent-001",
    }
    payload = _create_payload(content="Check backup status")

    first = client.post(f"{API_PREFIX}/conversations", headers=headers, json=payload)
    second = client.post(f"{API_PREFIX}/conversations", headers=headers, json=payload)

    assert first.status_code == 201
    assert second.status_code == 201
    assert (
        second.json()["conversation"]["conversation_id"]
        == first.json()["conversation"]["conversation_id"]
    )
    assert second.json()["message"]["message_id"] == first.json()["message"]["message_id"]
    assert asyncio.run(_table_counts(client))["conversations"] == 1


def test_create_conversation_idempotency_key_does_not_leak_cross_user_conversation(
    client: TestClient,
) -> None:
    payload = _create_payload(content="Check backup status")
    first = client.post(
        f"{API_PREFIX}/conversations",
        headers={
            "X-User": _x_user("user-001"),
            "Idempotency-Key": "create-cross-user-idempotent",
        },
        json=payload,
    )

    second = client.post(
        f"{API_PREFIX}/conversations",
        headers={
            "X-User": _x_user("other-user"),
            "Idempotency-Key": "create-cross-user-idempotent",
        },
        json=payload,
    )

    assert first.status_code == 201
    assert second.status_code == 403
    assert second.json()["error"]["code"] == "FORBIDDEN"
    assert asyncio.run(_table_counts(client))["conversations"] == 1


def test_create_conversation_rejects_high_risk_credentials(client: TestClient) -> None:
    response = client.post(
        f"{API_PREFIX}/conversations",
        headers={"X-User": _x_user("user-001"), "Idempotency-Key": "create-sensitive-001"},
        json=_create_payload(content="please store password=SuperSecret123"),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"
    assert asyncio.run(_table_counts(client)) == {
        "conversations": 0,
        "messages": 0,
        "status_events": 0,
        "outbox": 0,
    }


def test_blank_workspace_does_not_create_conversation(client: TestClient) -> None:
    assert asyncio.run(_table_counts(client))["conversations"] == 0


def test_list_conversations_sorts_and_filters(client: TestClient) -> None:
    older = _create(
        client,
        "user-001",
        "older-key",
        "Restore PostgreSQL",
        ["restore"],
        "restore_db",
    )
    newer = _create(client, "user-002", "newer-key", "Analyze incident", ["incident"], "incident")
    archived = _create(
        client,
        "user-003",
        "archived-key",
        "Archived restore",
        ["restore"],
        "restore_db",
    )

    asyncio.run(
        _update_conversations(
            client,
            {
                int(older["conversation"]["conversation_id"]): {
                    "f_last_active_time": 1_800_000_000_000,
                },
                int(newer["conversation"]["conversation_id"]): {
                    "f_last_active_time": 1_800_000_100_000,
                },
                int(archived["conversation"]["conversation_id"]): {
                    "f_status": "archived",
                    "f_last_active_time": 1_800_000_200_000,
                },
            },
        )
    )

    default_response = client.get(
        f"{API_PREFIX}/conversations",
        headers={"X-User": _x_user("user-001")},
    )
    restore_response = client.get(
        f"{API_PREFIX}/conversations",
        headers={"X-User": _x_user("user-001")},
        params={
            "keyword": "restore",
            "tag": "restore",
            "task_type": "restore_db",
            "status": "active",
        },
    )
    archived_response = client.get(
        f"{API_PREFIX}/conversations",
        headers={"X-User": _x_user("user-003")},
        params={"archived": "true"},
    )
    other_user_response = client.get(
        f"{API_PREFIX}/conversations",
        headers={"X-User": _x_user("other-user")},
        params={"keyword": "restore", "tag": "restore"},
    )

    assert default_response.status_code == 200
    assert [item["title"] for item in default_response.json()["items"]] == [
        "Restore PostgreSQL",
    ]
    assert restore_response.status_code == 200
    assert [item["conversation_id"] for item in restore_response.json()["items"]] == [
        older["conversation"]["conversation_id"]
    ]
    assert archived_response.status_code == 200
    assert [item["conversation_id"] for item in archived_response.json()["items"]] == [
        archived["conversation"]["conversation_id"]
    ]
    assert other_user_response.status_code == 200
    assert other_user_response.json()["items"] == []


def test_get_conversation_detail_returns_conversation_messages_and_events(
    client: TestClient,
) -> None:
    created = _create(client, "user-001", "detail-key", "Restore VM", ["restore"], "restore_vm")
    conversation_id = created["conversation"]["conversation_id"]

    response = client.get(
        f"{API_PREFIX}/conversations/{conversation_id}",
        headers={"X-User": _x_user("user-001")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"] == conversation_id
    assert body["title"] == "Restore VM"
    assert [message["message_id"] for message in body["latest_messages"]] == [
        created["message"]["message_id"]
    ]
    assert [event["status_event_id"] for event in body["latest_events"]] == [
        created["status_event"]["status_event_id"]
    ]
    assert body["context"] is None


def test_get_conversation_detail_rejects_non_owner(client: TestClient) -> None:
    created = _create(client, "user-001", "detail-forbidden", "Restore VM", [], "restore_vm")
    conversation_id = created["conversation"]["conversation_id"]

    response = client.get(
        f"{API_PREFIX}/conversations/{conversation_id}",
        headers={"X-User": _x_user("other-user")},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_patch_conversation_updates_title_in_place(client: TestClient) -> None:
    created = _create(client, "user-001", "rename-key", "Restore VM", ["restore"], "restore_vm")
    conversation_id = created["conversation"]["conversation_id"]

    response = client.patch(
        f"{API_PREFIX}/conversations/{conversation_id}",
        headers={"X-User": _x_user("user-001")},
        json={"title": "  Restore VM   P1  "},
    )
    detail = client.get(
        f"{API_PREFIX}/conversations/{conversation_id}",
        headers={"X-User": _x_user("user-001")},
    )

    assert response.status_code == 200
    assert response.json()["conversation_id"] == conversation_id
    assert response.json()["title"] == "Restore VM P1"
    assert response.json()["tags"] == ["restore"]
    assert detail.status_code == 200
    assert detail.json()["title"] == "Restore VM P1"


def test_patch_conversation_rejects_non_owner(client: TestClient) -> None:
    created = _create(client, "user-001", "rename-forbidden", "Restore VM", [], "restore_vm")
    conversation_id = created["conversation"]["conversation_id"]

    response = client.patch(
        f"{API_PREFIX}/conversations/{conversation_id}",
        headers={"X-User": _x_user("other-user")},
        json={"title": "Cross user title"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


@pytest.mark.parametrize(
    ("status_value", "error_code"),
    [
        ("archived", "CONVERSATION_ARCHIVED"),
        ("expired", "CONVERSATION_EXPIRED"),
    ],
)
def test_patch_conversation_rejects_readonly_statuses(
    client: TestClient,
    status_value: str,
    error_code: str,
) -> None:
    created = _create(client, "user-001", f"rename-{status_value}", "Restore VM", [], "restore_vm")
    conversation_id = int(created["conversation"]["conversation_id"])
    asyncio.run(
        _update_conversations(
            client,
            {
                conversation_id: {
                    "f_status": status_value,
                    "f_active_run_id": None,
                }
            },
        )
    )

    response = client.patch(
        f"{API_PREFIX}/conversations/{conversation_id}",
        headers={"X-User": _x_user("user-001")},
        json={"title": "New title"},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == error_code


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"X-User": "not-json"},
        {"X-User": json.dumps({"preferred_username": "missing-sub"})},
    ],
)
def test_user_api_requires_valid_x_user(
    client: TestClient,
    headers: dict[str, str],
) -> None:
    response = client.get(f"{API_PREFIX}/conversations", headers=headers)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHORIZED"
    assert response.json()["error"]["message"] == "身份信息缺失或无效。"
    assert response.headers["Content-Language"] == "zh-CN"


def _create(
    client: TestClient,
    user_id: str,
    idempotency_key: str,
    title: str,
    tags: list[str],
    task_type: str,
) -> dict[str, object]:
    response = client.post(
        f"{API_PREFIX}/conversations",
        headers={"X-User": _x_user(user_id), "Idempotency-Key": idempotency_key},
        json=_create_payload(
            content=title,
            title=title,
            tags=tags,
            task_type=task_type,
        ),
    )
    assert response.status_code == 201
    return response.json()


def _create_payload(
    *,
    content: str,
    title: str | None = None,
    tags: list[str] | None = None,
    task_type: str | None = None,
) -> dict[str, object]:
    return {
        "initial_message": {
            "type": "user_message",
            "content": content,
            "client_message_id": f"client-{content[:12].lower().replace(' ', '-')}",
        },
        "title": title,
        "tags": tags or [],
        "scenario_binding": {
            "scenario_id": "scenario-001",
            "task_type": task_type,
            "asset_refs": [],
        },
        "source": "web",
    }


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


async def _table_counts(client: TestClient) -> dict[str, int]:
    engine = client.app.state.container.database_engine()
    async with engine.connect() as connection:
        conversation_count = await connection.scalar(
            select(func.count(ConversationModel.f_conversation_id))
        )
        message_count = await connection.scalar(
            select(func.count(ConversationMessageModel.f_message_id))
        )
        event_count = await connection.scalar(
            select(func.count(ConversationStatusEventModel.f_status_event_id))
        )
        outbox_count = await connection.scalar(
            select(func.count(ConversationMqOutboxModel.f_outbox_id))
        )
    return {
        "conversations": int(conversation_count or 0),
        "messages": int(message_count or 0),
        "status_events": int(event_count or 0),
        "outbox": int(outbox_count or 0),
    }


async def _update_conversations(
    client: TestClient,
    updates: dict[int, dict[str, object]],
) -> None:
    engine = client.app.state.container.database_engine()
    async with engine.begin() as connection:
        for conversation_id, values in updates.items():
            await connection.execute(
                update(ConversationModel)
                .where(ConversationModel.f_conversation_id == conversation_id)
                .values(**values)
            )
