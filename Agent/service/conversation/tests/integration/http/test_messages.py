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
    ConversationReasoningTraceModel,
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
            snowflake_node_id=8,
            snowflake_epoch_ms=1_735_689_600_000,
        )
    )

    with TestClient(app) as test_client:
        yield test_client

    asyncio.run(app.state.container.database_engine().dispose())


def test_send_user_message_persists_message_event_outbox_and_marks_busy(
    client: TestClient,
) -> None:
    created = _create_conversation(client, "conv-for-message")
    conversation_id = created["conversation"]["conversation_id"]
    asyncio.run(_set_conversation(client, int(conversation_id), f_active_run_id=None))

    response = client.post(
        f"{API_PREFIX}/conversations/{conversation_id}/messages",
        headers={
            "X-User": _x_user("user-001"),
            "Idempotency-Key": "message-key-001",
            "X-Request-Id": "req-message-001",
        },
        json=_message_payload("Run the restore now", "client-message-001"),
    )

    assert response.status_code == 202
    body = response.json()
    assert body["conversation"]["conversation_id"] == conversation_id
    assert body["conversation"]["has_active_run"] is True
    assert body["conversation"]["active_turn_id"] == body["message"]["turn_id"]
    assert body["message"]["conversation_id"] == conversation_id
    assert body["message"]["content"] == "Run the restore now"
    assert body["message"]["client_message_id"] == "client-message-001"
    assert body["message"]["status"] == "persisted"
    assert body["message"]["turn_id"] is not None
    assert body["status_event"]["event_type"] == "message.created"
    assert body["status_event"]["sequence"] == 2
    assert body["status_event"]["turn_id"] == body["message"]["turn_id"]
    assert asyncio.run(_table_count(client, ConversationMessageModel.f_message_id)) == 2
    assert asyncio.run(_table_count(client, ConversationStatusEventModel.f_status_event_id)) == 2
    assert asyncio.run(_table_count(client, ConversationMqOutboxModel.f_outbox_id)) == 2
    outbox_row = asyncio.run(
        _latest_outbox(client, int(conversation_id), int(body["message"]["message_id"]))
    )
    assert outbox_row is not None
    assert outbox_row.f_payload == {
        "conversation_id": conversation_id,
        "message_id": body["message"]["message_id"],
        "turn_id": body["message"]["turn_id"],
        "content": "Run the restore now",
    }


def test_send_user_message_is_idempotent_before_busy_guard(client: TestClient) -> None:
    created = _create_conversation(client, "conv-for-idempotency")
    conversation_id = created["conversation"]["conversation_id"]
    asyncio.run(_set_conversation(client, int(conversation_id), f_active_run_id=None))
    headers = {
        "X-User": _x_user("user-001"),
        "Idempotency-Key": "message-idempotent-001",
    }

    first = client.post(
        f"{API_PREFIX}/conversations/{conversation_id}/messages",
        headers=headers,
        json=_message_payload("Check snapshot", "client-idem-001"),
    )
    second = client.post(
        f"{API_PREFIX}/conversations/{conversation_id}/messages",
        headers=headers,
        json=_message_payload("Check snapshot", "client-idem-001"),
    )

    assert first.status_code == 202
    assert second.status_code == 202
    assert second.json()["message"]["message_id"] == first.json()["message"]["message_id"]
    assert asyncio.run(_table_count(client, ConversationMessageModel.f_message_id)) == 2


def test_send_user_message_rejects_non_owner_and_idempotency_reuse(
    client: TestClient,
) -> None:
    created = _create_conversation(client, "conv-for-owner-boundary")
    conversation_id = created["conversation"]["conversation_id"]
    asyncio.run(_set_conversation(client, int(conversation_id), f_active_run_id=None))

    forbidden = client.post(
        f"{API_PREFIX}/conversations/{conversation_id}/messages",
        headers={"X-User": _x_user("other-user"), "Idempotency-Key": "message-forbidden"},
        json=_message_payload("Cross-user write", "client-forbidden"),
    )
    owner_response = client.post(
        f"{API_PREFIX}/conversations/{conversation_id}/messages",
        headers={"X-User": _x_user("user-001"), "Idempotency-Key": "message-owner-key"},
        json=_message_payload("Owner write", "client-owner"),
    )
    leaked_retry = client.post(
        f"{API_PREFIX}/conversations/{conversation_id}/messages",
        headers={"X-User": _x_user("other-user"), "Idempotency-Key": "message-owner-key"},
        json=_message_payload("Owner write", "client-owner"),
    )

    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"
    assert owner_response.status_code == 202
    assert leaked_retry.status_code == 403
    assert leaked_retry.json()["error"]["code"] == "FORBIDDEN"


def test_send_user_message_rejects_high_risk_credentials(client: TestClient) -> None:
    created = _create_conversation(client, "conv-for-sensitive-input")
    conversation_id = created["conversation"]["conversation_id"]
    asyncio.run(_set_conversation(client, int(conversation_id), f_active_run_id=None))

    response = client.post(
        f"{API_PREFIX}/conversations/{conversation_id}/messages",
        headers={"X-User": _x_user("user-001"), "Idempotency-Key": "message-sensitive-001"},
        json=_message_payload("please store password=SuperSecret123", "client-sensitive-001"),
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_FAILED"
    assert asyncio.run(_table_count(client, ConversationMessageModel.f_message_id)) == 1
    assert asyncio.run(_table_count(client, ConversationStatusEventModel.f_status_event_id)) == 1
    assert asyncio.run(_table_count(client, ConversationMqOutboxModel.f_outbox_id)) == 1


@pytest.mark.parametrize(
    ("values", "expected_code"),
    [
        ({"f_active_run_id": "run-001"}, "CONVERSATION_BUSY"),
        ({"f_status": "archived", "f_active_run_id": None}, "CONVERSATION_ARCHIVED"),
        ({"f_status": "expired", "f_active_run_id": None}, "CONVERSATION_EXPIRED"),
    ],
)
def test_send_user_message_rejects_blocked_conversation_states(
    client: TestClient,
    values: dict[str, object],
    expected_code: str,
) -> None:
    created = _create_conversation(client, f"conv-for-{expected_code}")
    conversation_id = created["conversation"]["conversation_id"]
    asyncio.run(_set_conversation(client, int(conversation_id), **values))

    response = client.post(
        f"{API_PREFIX}/conversations/{conversation_id}/messages",
        headers={"X-User": _x_user("user-001"), "Idempotency-Key": f"blocked-{expected_code}"},
        json=_message_payload("Should be rejected", f"client-{expected_code}"),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == expected_code


def test_candidate_selection_message_is_accepted_via_messages_endpoint(
    client: TestClient,
) -> None:
    created = _create_conversation(client, "conv-for-candidate-selection-message")
    conversation_id = int(created["conversation"]["conversation_id"])
    message_id = int(created["message"]["message_id"])
    reasoning_trace_id = f"trace-{conversation_id}"
    asyncio.run(_set_conversation(client, conversation_id, f_active_run_id=None))
    asyncio.run(
        _insert_reasoning_trace(
            client,
            conversation_id=conversation_id,
            message_id=message_id,
            reasoning_trace_id=reasoning_trace_id,
        )
    )

    response = client.post(
        f"{API_PREFIX}/conversations/{conversation_id}/messages",
        headers={"X-User": _x_user("user-001")},
        json={
            "type": "candidate_selection",
            "message_id": str(message_id),
            "reasoning_trace_id": reasoning_trace_id,
            "candidate_option_id": "candidate-a",
            "selection": "confirm",
            "additional_constraints": "Prefer the fastest safe option",
            "client_message_id": "client-candidate-message-001",
            "idempotency_key": "candidate-message-001",
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["conversation"]["conversation_id"] == str(conversation_id)
    assert body["status_event"]["event_type"] == "message.updated"
    assert body["status_event"]["detail"] == "Candidate selection accepted"
    assert body["message"]["message_id"] == str(message_id)
    assert body["message"]["reasoning_trace_id"] == reasoning_trace_id
    assert asyncio.run(_table_count(client, ConversationMessageModel.f_message_id)) == 1
    assert asyncio.run(_table_count(client, ConversationStatusEventModel.f_status_event_id)) == 1
    selection_outbox = asyncio.run(
        _latest_selection_outbox(client, conversation_id, reasoning_trace_id, "candidate-a")
    )
    assert selection_outbox is not None
    assert selection_outbox.f_event_type == "conversation.candidate_selection.created.v1"


def test_clarification_response_is_accepted_while_conversation_is_clarifying(
    client: TestClient,
) -> None:
    created = _create_conversation(client, "conv-for-clarification-response")
    conversation_id = int(created["conversation"]["conversation_id"])
    asyncio.run(_set_conversation(client, conversation_id, f_active_run_id="run-001"))

    response = client.post(
        f"{API_PREFIX}/conversations/{conversation_id}/messages",
        headers={"X-User": _x_user("user-001")},
        json={
            "type": "clarification_response",
            "message_id": created["message"]["message_id"],
            "clarification_id": "recovery_window",
            "selected_value": "latest_safe_point",
            "free_text": "Use the latest safe point and continue restore planning",
            "client_message_id": "client-clarification-001",
            "idempotency_key": "clarification-message-001",
        },
    )

    assert response.status_code == 202
    body = response.json()
    assert body["conversation"]["conversation_id"] == str(conversation_id)
    assert body["conversation"]["has_active_run"] is True
    assert body["message"]["content"] == (
        "clarification_response recovery_window latest_safe_point "
        "Use the latest safe point and continue restore planning"
    )
    outbox_row = asyncio.run(
        _latest_outbox(client, conversation_id, int(body["message"]["message_id"]))
    )
    assert outbox_row is not None
    assert outbox_row.f_payload["content"].startswith("clarification_response recovery_window")


def test_list_messages_paginates_and_filters(client: TestClient) -> None:
    created = _create_conversation(client, "conv-for-history")
    conversation_id = int(created["conversation"]["conversation_id"])
    asyncio.run(_set_conversation(client, conversation_id, f_active_run_id=None))
    _send_message(client, conversation_id, "message-history-001", "First follow-up")
    asyncio.run(_set_conversation(client, conversation_id, f_active_run_id=None))
    _send_message(client, conversation_id, "message-history-002", "Second follow-up")
    asyncio.run(_insert_assistant_message(client, conversation_id))

    first_page = client.get(
        f"{API_PREFIX}/conversations/{conversation_id}/messages",
        headers={"X-User": _x_user("user-001")},
        params={"limit": 2},
    )
    second_page = client.get(
        f"{API_PREFIX}/conversations/{conversation_id}/messages",
        headers={"X-User": _x_user("user-001")},
        params={"limit": 2, "cursor": first_page.json()["page"]["next_cursor"]},
    )
    assistant_page = client.get(
        f"{API_PREFIX}/conversations/{conversation_id}/messages",
        headers={"X-User": _x_user("user-001")},
        params={"role": "assistant", "status": "responded", "content_type": "text"},
    )
    forbidden_page = client.get(
        f"{API_PREFIX}/conversations/{conversation_id}/messages",
        headers={"X-User": _x_user("other-user")},
    )

    assert first_page.status_code == 200
    assert [item["content"] for item in first_page.json()["items"]] == [
        "conv-for-history",
        "First follow-up",
    ]
    assert first_page.json()["page"]["has_more"] is True
    assert second_page.status_code == 200
    assert [item["content"] for item in second_page.json()["items"]] == [
        "Second follow-up",
        "Assistant response",
    ]
    assert second_page.json()["page"]["has_more"] is False
    assert assistant_page.status_code == 200
    assert [item["role"] for item in assistant_page.json()["items"]] == ["assistant"]
    assert forbidden_page.status_code == 403
    assert forbidden_page.json()["error"]["code"] == "FORBIDDEN"


def test_list_events_returns_control_fields_and_turn_ids(client: TestClient) -> None:
    created = _create_conversation(client, "conv-for-events")
    conversation_id = created["conversation"]["conversation_id"]

    response = client.get(
        f"{API_PREFIX}/conversations/{conversation_id}/events",
        headers={"X-User": _x_user("user-001")},
    )
    forbidden = client.get(
        f"{API_PREFIX}/conversations/{conversation_id}/events",
        headers={"X-User": _x_user("other-user")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["latest_sequence"] == 1
    assert body["recommended_poll_interval_ms"] == 1000
    assert body["has_active_run"] is True
    assert body["items"][0]["event_type"] == "message.created"
    assert body["items"][0]["turn_id"] == created["message"]["turn_id"]
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "FORBIDDEN"


def _create_conversation(client: TestClient, content: str) -> dict[str, object]:
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
    return response.json()


def _send_message(
    client: TestClient,
    conversation_id: int,
    idempotency_key: str,
    content: str,
) -> dict[str, object]:
    response = client.post(
        f"{API_PREFIX}/conversations/{conversation_id}/messages",
        headers={"X-User": _x_user("user-001"), "Idempotency-Key": idempotency_key},
        json=_message_payload(content, f"client-{idempotency_key}"),
    )
    assert response.status_code == 202
    return response.json()


def _message_payload(content: str, client_message_id: str) -> dict[str, object]:
    return {
        "type": "user_message",
        "content": content,
        "client_message_id": client_message_id,
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


async def _set_conversation(
    client: TestClient,
    conversation_id: int,
    **values: object,
) -> None:
    engine = client.app.state.container.database_engine()
    async with engine.begin() as connection:
        await connection.execute(
            update(ConversationModel)
            .where(ConversationModel.f_conversation_id == conversation_id)
            .values(**values)
        )


async def _insert_assistant_message(client: TestClient, conversation_id: int) -> None:
    engine = client.app.state.container.database_engine()
    async with engine.begin() as connection:
        max_message_id = await connection.scalar(
            select(func.max(ConversationMessageModel.f_message_id))
        )
        max_created_time = await connection.scalar(
            select(func.max(ConversationMessageModel.f_created_time))
        )
        await connection.execute(
            ConversationMessageModel.__table__.insert().values(
                f_message_id=int(max_message_id or 0) + 1,
                f_conversation_id=conversation_id,
                f_parent_message_id=None,
                f_turn_id=None,
                f_role="assistant",
                f_content_type="text",
                f_content="Assistant response",
                f_rich_payload=None,
                f_status="responded",
                f_client_message_id=None,
                f_idempotency_key=None,
                f_trace_id="trace-assistant",
                f_correlation_id="corr-assistant",
                f_error_code=None,
                f_created_time=int(max_created_time or 0) + 1,
                f_updated_time=int(max_created_time or 0) + 1,
            )
        )


async def _latest_outbox(
    client: TestClient,
    conversation_id: int,
    message_id: int,
) -> ConversationMqOutboxModel | None:
    session_factory = client.app.state.container.async_session_factory()
    async with session_factory() as session:
        row = await session.scalar(
            select(ConversationMqOutboxModel).where(
                ConversationMqOutboxModel.f_conversation_id == conversation_id,
                ConversationMqOutboxModel.f_message_id == message_id,
            )
        )
    return row


async def _latest_selection_outbox(
    client: TestClient,
    conversation_id: int,
    reasoning_trace_id: str,
    candidate_option_id: str,
) -> ConversationMqOutboxModel | None:
    session_factory = client.app.state.container.async_session_factory()
    async with session_factory() as session:
        row = await session.scalar(
            select(ConversationMqOutboxModel).where(
                ConversationMqOutboxModel.f_conversation_id == conversation_id,
                ConversationMqOutboxModel.f_event_type
                == "conversation.candidate_selection.created.v1",
            )
        )
    if row is None:
        return None
    payload = row.f_payload or {}
    if (
        payload.get("reasoning_trace_id") != reasoning_trace_id
        or payload.get("candidate_option_id") != candidate_option_id
    ):
        return None
    return row


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
                },
                f_created_by_agent="decision-agent",
                f_core_agent_run_id="run-selection",
                f_trace_id="trace-selection",
                f_created_time=1_800_000_000_100,
                f_updated_time=1_800_000_000_100,
            )
        )


async def _table_count(client: TestClient, column: object) -> int:
    engine = client.app.state.container.database_engine()
    async with engine.connect() as connection:
        count = await connection.scalar(select(func.count(column)))
    return int(count or 0)
