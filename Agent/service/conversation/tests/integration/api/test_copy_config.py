import asyncio
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import create_async_engine

from app.bootstrap.app_factory import create_app
from app.bootstrap.settings import Settings
from app.infrastructure.persistence.sqlalchemy.models import (
    Base,
    ConversationContextSnapshotModel,
    ConversationMessageModel,
    ConversationModel,
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
            snowflake_node_id=14,
            snowflake_epoch_ms=1_735_689_600_000,
        )
    )

    with TestClient(app) as test_client:
        yield test_client

    asyncio.run(app.state.container.database_engine().dispose())


def test_copy_config_creates_new_conversation_without_history_or_private_input(
    client: TestClient,
) -> None:
    source = _create_source_conversation(client, owner="source-owner", title="Backup plan")
    source_id = int(source["conversation_id"])

    response = client.post(
        f"{API_PREFIX}/conversations/{source_id}/copy-config",
        headers={"X-User": _x_user("source-owner"), "Idempotency-Key": "copy-config-001"},
        json={"title": "Copied backup plan", "additional_tags": ["copied"]},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["conversation_id"] != str(source_id)
    assert body["owner_user_id"] == "source-owner"
    assert body["title"] == "Copied backup plan"
    assert body["status"] == "active"
    assert body["has_active_run"] is False
    assert body["scenario_binding"]["scenario_id"] == "backup_recovery"
    assert body["scenario_binding"]["task_type"] == "restore_drill"
    assert body["scenario_binding"]["asset_refs"] == ["vm-001", "db-002"]
    assert body["scenario_binding"]["preferences"] == {
        "restore_priority": "latest_safe_point"
    }
    assert body["tags"] == ["gold", "production", "copied"]
    assert body["latest_messages"] == []
    assert "do not copy this private token" not in json.dumps(body)
    assert asyncio.run(_message_count(client, int(body["conversation_id"]))) == 0

    source_after = client.get(
        f"{API_PREFIX}/conversations/{source_id}",
        headers={"X-User": _x_user("source-owner")},
    )
    assert source_after.status_code == 200
    assert source_after.json()["tags"] == ["gold", "production"]
    assert source_after.json()["title"] == "Backup plan"


def test_copy_config_blocks_expired_source(client: TestClient) -> None:
    source = _create_source_conversation(client, owner="source-owner", title="Expired")
    source_id = int(source["conversation_id"])
    asyncio.run(_set_conversation(client, source_id, f_status="expired"))

    response = client.post(
        f"{API_PREFIX}/conversations/{source_id}/copy-config",
        headers={"X-User": _x_user("source-owner"), "Idempotency-Key": "copy-config-expired"},
        json={},
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "CONVERSATION_EXPIRED"


def test_copy_config_rejects_non_owner_source(client: TestClient) -> None:
    source = _create_source_conversation(client, owner="owner-a", title="Cross user")

    response = client.post(
        f"{API_PREFIX}/conversations/{source['conversation_id']}/copy-config",
        headers={"X-User": _x_user("owner-b"), "Idempotency-Key": "copy-config-cross-user"},
        json={"copy_tags": False},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_context_endpoint_returns_frontend_panel_fields(client: TestClient) -> None:
    source = _create_source_conversation(client, owner="source-owner", title="Panel")
    conversation_id = int(source["conversation_id"])
    asyncio.run(
        _insert_snapshot(
            client,
            conversation_id=conversation_id,
            structured_state={
                "key_variables": {"target_asset": "db-002", "rpo": "15m"},
                "confirmed_facts": ["Latest safe restore point is available."],
                "pending_questions": ["Confirm maintenance window."],
                "current_candidates": [
                    {"candidate_option_id": "opt-a", "title": "Restore to staging"}
                ],
                "next_actions": ["Confirm candidate opt-a"],
                "latest_reasoning_summary": "Staging restore has the lowest risk.",
                "memory_refs": [
                    {
                        "ref_type": "asset",
                        "ref_id": "db-002",
                        "title": "Orders database",
                    }
                ],
                "internal_reasoning": "must not leak",
            },
        )
    )

    response = client.get(
        f"{API_PREFIX}/conversations/{conversation_id}/context",
        headers={"X-User": _x_user("source-owner")},
    )
    forbidden = client.get(
        f"{API_PREFIX}/conversations/{conversation_id}/context",
        headers={"X-User": _x_user("other-user")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["conversation_id"] == str(conversation_id)
    assert body["panel"]["short_summary"] == "Restore plan summary"
    assert body["panel"]["scenario_binding"]["scenario_id"] == "backup_recovery"
    assert body["panel"]["key_variables"] == {"target_asset": "db-002", "rpo": "15m"}
    assert body["panel"]["confirmed_facts"] == ["Latest safe restore point is available."]
    assert body["panel"]["pending_questions"] == ["Confirm maintenance window."]
    assert body["panel"]["current_candidates"][0]["candidate_option_id"] == "opt-a"
    assert body["panel"]["next_actions"] == ["Confirm candidate opt-a"]
    assert body["panel"]["latest_reasoning_summary"] == "Staging restore has the lowest risk."
    assert body["panel"]["memory_refs"][0]["ref_id"] == "db-002"
    assert "internal_reasoning" not in json.dumps(body)
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"


def _create_source_conversation(
    client: TestClient,
    *,
    owner: str,
    title: str,
) -> dict[str, str]:
    response = client.post(
        f"{API_PREFIX}/conversations",
        headers={"X-User": _x_user(owner), "Idempotency-Key": f"create-{owner}-{title}"},
        json={
            "initial_message": {
                "type": "user_message",
                "content": "do not copy this private token",
                "client_message_id": f"client-{owner}-{title}",
            },
            "title": title,
            "scenario_binding": {
                "scenario_id": "backup_recovery",
                "task_type": "restore_drill",
                "asset_refs": ["vm-001", "db-002"],
            },
            "tags": ["gold", "production"],
            "source": "web",
        },
    )
    assert response.status_code == 201
    body = response.json()
    conversation_id = int(body["conversation"]["conversation_id"])
    asyncio.run(
        _set_conversation(
            client,
            conversation_id,
            f_active_run_id=None,
            f_scenario_binding={
                "scenario_id": "backup_recovery",
                "task_type": "restore_drill",
                "asset_refs": ["vm-001", "db-002"],
                "preferences": {"restore_priority": "latest_safe_point"},
                "private_input": "should not copy",
            },
        )
    )
    return {
        "conversation_id": body["conversation"]["conversation_id"],
        "message_id": body["message"]["message_id"],
    }


async def _set_conversation(client: TestClient, conversation_id: int, **values: object) -> None:
    engine = client.app.state.container.database_engine()
    async with engine.begin() as connection:
        await connection.execute(
            update(ConversationModel)
            .where(ConversationModel.f_conversation_id == conversation_id)
            .values(**values)
        )


async def _insert_snapshot(
    client: TestClient,
    *,
    conversation_id: int,
    structured_state: dict[str, Any],
) -> None:
    engine = client.app.state.container.database_engine()
    async with engine.begin() as connection:
        await connection.execute(
            ConversationContextSnapshotModel.__table__.insert().values(
                f_context_snapshot_id=91_001,
                f_conversation_id=conversation_id,
                f_snapshot_version=3,
                f_short_summary="Restore plan summary",
                f_structured_state=structured_state,
                f_last_message_id=None,
                f_status="current",
                f_created_by="summary_updater",
                f_trace_id="trace-panel",
                f_created_time=1_800_000_000_000,
                f_updated_time=1_800_000_000_000,
            )
        )


async def _message_count(client: TestClient, conversation_id: int) -> int:
    engine = client.app.state.container.database_engine()
    async with engine.connect() as connection:
        count = await connection.scalar(
            select(func.count(ConversationMessageModel.f_message_id)).where(
                ConversationMessageModel.f_conversation_id == conversation_id
            )
        )
    return int(count or 0)


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
