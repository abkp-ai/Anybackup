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
    ConversationCandidateSelectionModel,
    ConversationMessageModel,
    ConversationModel,
    ConversationMqOutboxModel,
    ConversationReasoningTraceModel,
)
from app.infrastructure.persistence.sqlalchemy.session import create_async_session_factory

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
            snowflake_node_id=12,
            snowflake_epoch_ms=1_735_689_600_000,
            core_agent_service_token="agent-token",
        )
    )

    with TestClient(app) as test_client:
        yield test_client

    asyncio.run(app.state.container.database_engine().dispose())


def test_reasoning_trace_query_returns_user_visible_summary_only(client: TestClient) -> None:
    created = _create_conversation_with_reasoning_trace(client, "trace-query")
    conversation_id = created["conversation_id"]

    response = client.get(
        f"{API_PREFIX}/conversations/{conversation_id}/reasoning-traces",
        headers={"X-User": _x_user("user-001")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["items"][0]["objective"] == "Select restore plan"
    assert body["items"][0]["decision_summary"] == "Compared RPO and RTO."
    assert body["items"][0]["pending_confirmations"][0]["prompt"] == "Use candidate-a?"
    assert "internal_reasoning" not in json.dumps(body, ensure_ascii=False)
    assert "system_prompt" not in json.dumps(body, ensure_ascii=False)


def test_reasoning_trace_query_rejects_non_owner(client: TestClient) -> None:
    created = _create_conversation_with_reasoning_trace(client, "trace-forbidden")

    response = client.get(
        f"{API_PREFIX}/conversations/{created['conversation_id']}/reasoning-traces",
        headers={"X-User": _x_user("other-user")},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"


def test_candidate_selection_persists_and_publishes_outbox(client: TestClient) -> None:
    created = _create_conversation_with_reasoning_trace(client, "candidate-confirm")
    conversation_id = created["conversation_id"]
    reasoning_trace_id = created["reasoning_trace_id"]

    response = client.post(
        f"{API_PREFIX}/conversations/{conversation_id}/candidate-selections",
        headers={"X-User": _x_user("user-001"), "Idempotency-Key": "candidate-select-001"},
        json={
            "reasoning_trace_id": reasoning_trace_id,
            "candidate_option_id": "candidate-a",
            "action": "confirm",
            "comment": "Use this plan",
        },
    )

    outbox = asyncio.run(_latest_outbox(client, int(conversation_id)))
    assert response.status_code == 202
    assert response.json()["selection"]["action"] == "confirm"
    assert asyncio.run(_count(client, ConversationCandidateSelectionModel.f_selection_id)) == 1
    assert outbox.f_event_type == "conversation.candidate_selection.created.v1"
    assert outbox.f_routing_key == "conversation.candidate_selection.created.v1"
    assert outbox.f_payload["candidate_option_id"] == "candidate-a"


def test_candidate_selection_is_idempotent(client: TestClient) -> None:
    created = _create_conversation_with_reasoning_trace(client, "candidate-idem")
    headers = {"X-User": _x_user("user-001"), "Idempotency-Key": "candidate-select-idem"}
    payload = {
        "reasoning_trace_id": created["reasoning_trace_id"],
        "candidate_option_id": "candidate-a",
        "action": "reject",
    }

    first = client.post(
        f"{API_PREFIX}/conversations/{created['conversation_id']}/candidate-selections",
        headers=headers,
        json=payload,
    )
    second = client.post(
        f"{API_PREFIX}/conversations/{created['conversation_id']}/candidate-selections",
        headers=headers,
        json=payload,
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["idempotent"] is True
    assert second.json()["selection"]["selection_id"] == first.json()["selection"]["selection_id"]
    assert asyncio.run(_count(client, ConversationCandidateSelectionModel.f_selection_id)) == 1


def test_candidate_selection_rejects_non_owner_and_idempotency_reuse(
    client: TestClient,
) -> None:
    created = _create_conversation_with_reasoning_trace(client, "candidate-owner-boundary")
    payload = {
        "reasoning_trace_id": created["reasoning_trace_id"],
        "candidate_option_id": "candidate-a",
        "action": "confirm",
    }

    forbidden = client.post(
        f"{API_PREFIX}/conversations/{created['conversation_id']}/candidate-selections",
        headers={"X-User": _x_user("other-user"), "Idempotency-Key": "candidate-forbidden"},
        json=payload,
    )
    owner_response = client.post(
        f"{API_PREFIX}/conversations/{created['conversation_id']}/candidate-selections",
        headers={"X-User": _x_user("user-001"), "Idempotency-Key": "candidate-owner-key"},
        json=payload,
    )
    leaked_retry = client.post(
        f"{API_PREFIX}/conversations/{created['conversation_id']}/candidate-selections",
        headers={"X-User": _x_user("other-user"), "Idempotency-Key": "candidate-owner-key"},
        json=payload,
    )

    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"
    assert owner_response.status_code == 202
    assert leaked_retry.status_code == 403
    assert leaked_retry.json()["error"]["code"] == "FORBIDDEN"


def test_candidate_selection_rejects_trace_from_other_conversation(client: TestClient) -> None:
    first = _create_conversation_with_reasoning_trace(client, "candidate-first")
    second = _create_conversation_with_reasoning_trace(client, "candidate-second")

    response = client.post(
        f"{API_PREFIX}/conversations/{second['conversation_id']}/candidate-selections",
        headers={"X-User": _x_user("user-001"), "Idempotency-Key": "candidate-cross"},
        json={
            "reasoning_trace_id": first["reasoning_trace_id"],
            "candidate_option_id": "candidate-a",
            "action": "confirm",
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"


@pytest.mark.parametrize(
    ("status_value", "expected_code"),
    [
        ("archived", "CONVERSATION_ARCHIVED"),
        ("expired", "CONVERSATION_EXPIRED"),
    ],
)
def test_candidate_selection_rejects_archived_and_expired_conversations(
    client: TestClient,
    status_value: str,
    expected_code: str,
) -> None:
    created = _create_conversation_with_reasoning_trace(client, f"candidate-{status_value}")
    conversation_id = int(created["conversation_id"])
    asyncio.run(_set_conversation(client, conversation_id, f_status=status_value))

    response = client.post(
        f"{API_PREFIX}/conversations/{created['conversation_id']}/candidate-selections",
        headers={
            "X-User": _x_user("user-001"),
            "Idempotency-Key": f"candidate-{status_value}-guard",
        },
        json={
            "reasoning_trace_id": created["reasoning_trace_id"],
            "candidate_option_id": "candidate-a",
            "action": "confirm",
        },
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == expected_code
    assert asyncio.run(_count(client, ConversationCandidateSelectionModel.f_selection_id)) == 0


def _create_conversation_with_reasoning_trace(client: TestClient, content: str) -> dict[str, str]:
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
    reasoning_trace_id = f"trace-{9_000 + sum(ord(char) for char in content)}"
    asyncio.run(
        _insert_reasoning_trace(
            client,
            conversation_id=int(body["conversation"]["conversation_id"]),
            message_id=int(body["message"]["message_id"]),
            reasoning_trace_id=reasoning_trace_id,
        )
    )
    return {
        "conversation_id": body["conversation"]["conversation_id"],
        "message_id": body["message"]["message_id"],
        "reasoning_trace_id": str(reasoning_trace_id),
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


async def _insert_reasoning_trace(
    client: TestClient,
    *,
    conversation_id: int,
    message_id: int,
    reasoning_trace_id: str,
) -> None:
    engine = client.app.state.container.database_engine()
    async with engine.begin() as connection:
        await connection.execute(
            ConversationReasoningTraceModel.__table__.insert().values(
                f_reasoning_trace_id=reasoning_trace_id,
                f_conversation_id=conversation_id,
                f_source_message_id=message_id,
                f_trace_payload={
                    "objective": "Select restore plan",
                    "decision_summary": "Compared RPO and RTO.",
                    "comparison_dimensions": ["RPO", "RTO"],
                    "candidates": [{"candidate_option_id": "candidate-a", "title": "Fast plan"}],
                    "recommendation": "candidate-a",
                    "recommended_candidate_option_id": "candidate-a",
                    "pending_confirmations": [
                        {
                            "confirmation_id": "confirm-a",
                            "prompt": "Use candidate-a?",
                            "allowed_actions": ["confirm", "reject", "revise"],
                        }
                    ],
                    "created_by_agent": "decision-agent",
                    "internal_reasoning": "must not be returned",
                    "system_prompt": "must not be returned",
                },
                f_core_agent_run_id="run-reasoning",
                f_created_by_agent="decision-agent",
                f_trace_id="trace-reasoning",
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


async def _count(client: TestClient, column: object) -> int:
    engine = client.app.state.container.database_engine()
    async with engine.connect() as connection:
        count = await connection.scalar(select(func.count(column)))
    return int(count or 0)
