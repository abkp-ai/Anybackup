import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine

from app.bootstrap.app_factory import create_app
from app.bootstrap.settings import Settings
from app.infrastructure.persistence.sqlalchemy.models import Base, ConversationStatusEventModel

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
        test_client.database_url = database_url  # type: ignore[attr-defined]
        yield test_client

    asyncio.run(app.state.container.database_engine().dispose())


def test_runs_endpoint_returns_sse_stream_for_existing_conversation(client: TestClient) -> None:
    conversation = _create_conversation(client)

    with client.stream(
        "POST",
        f"{API_PREFIX}/runs",
        headers={"X-User": _x_user("user-001")},
        json={
            "threadId": conversation["conversation_id"],
            "runId": conversation["active_run_id"],
            "messages": [{"role": "user", "content": "继续分析备份状态"}],
            "state": {"selection": {"required": False}},
        },
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")


def test_runs_endpoint_streams_persisted_ag_ui_events_and_closes_on_terminal(
    client: TestClient,
) -> None:
    conversation = _create_conversation(client)
    asyncio.run(
        _insert_ag_ui_event(
            client.database_url,  # type: ignore[attr-defined]
            conversation_id=int(conversation["conversation_id"]),
            run_id=str(conversation["active_run_id"]),
        )
    )

    with client.stream(
        "POST",
        f"{API_PREFIX}/runs",
        headers={"X-User": _x_user("user-001")},
        json={
            "threadId": conversation["conversation_id"],
            "runId": conversation["active_run_id"],
            "messages": [{"role": "user", "content": "继续分析备份状态"}],
        },
    ) as response:
        body = "".join(response.iter_text())

    assert "data: " in body
    assert '"type":"RUN_FINISHED"' in body
    assert '"runId":"' + conversation["active_run_id"] + '"' in body


def test_runs_endpoint_resumes_after_forwarded_sequence_cursor(client: TestClient) -> None:
    conversation = _create_conversation(client)
    asyncio.run(
        _insert_ag_ui_event(
            client.database_url,  # type: ignore[attr-defined]
            conversation_id=int(conversation["conversation_id"]),
            run_id=str(conversation["active_run_id"]),
            sequence=2,
            event_type="STATE_SNAPSHOT",
            event_id="state-snapshot-resume",
        )
    )
    asyncio.run(
        _insert_ag_ui_event(
            client.database_url,  # type: ignore[attr-defined]
            conversation_id=int(conversation["conversation_id"]),
            run_id=str(conversation["active_run_id"]),
            sequence=3,
            event_type="RUN_FINISHED",
            event_id="run-finished-resume",
        )
    )

    with client.stream(
        "POST",
        f"{API_PREFIX}/runs",
        headers={"X-User": _x_user("user-001")},
        json={
            "threadId": conversation["conversation_id"],
            "runId": conversation["active_run_id"],
            "messages": [{"role": "user", "content": "继续分析备份状态"}],
            "forwardedProps": {"afterSequence": 2},
        },
    ) as response:
        body = "".join(response.iter_text())

    assert "state-snapshot-resume" not in body
    assert "run-finished-resume" in body


def test_runs_endpoint_requires_run_id(client: TestClient) -> None:
    conversation = _create_conversation(client)

    response = client.post(
        f"{API_PREFIX}/runs",
        headers={"X-User": _x_user("user-001")},
        json={
            "threadId": conversation["conversation_id"],
            "messages": [{"role": "user", "content": "继续分析备份状态"}],
        },
    )

    assert response.status_code == 422


def _create_conversation(client: TestClient) -> dict[str, str]:
    response = client.post(
        f"{API_PREFIX}/conversations",
        headers={"X-User": _x_user("user-001"), "Idempotency-Key": "ag-ui-run-create"},
        json={
            "initial_message": {
                "type": "user_message",
                "content": "检查备份状态",
                "client_message_id": "msg-001",
            },
            "title": "备份状态",
        },
    )
    assert response.status_code == 201
    return response.json()["conversation"]


def _x_user(user_id: str) -> str:
    return (
        '{"sub":"'
        + user_id
        + '","preferred_username":"tester","roles":["user"],"email_verified":true}'
    )


async def _insert_ag_ui_event(
    database_url: str,
    *,
    conversation_id: int,
    run_id: str,
    sequence: int = 2,
    event_type: str = "RUN_FINISHED",
    event_id: str = "run-finished-stream",
) -> None:
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(
            ConversationStatusEventModel.__table__.insert().values(
                f_status_event_id=90_000 + sequence,
                f_conversation_id=conversation_id,
                f_sequence=sequence,
                f_event_type=event_type,
                f_event_version="v1",
                f_message_id=None,
                f_turn_id=None,
                f_payload={
                    "type": event_type,
                    "eventId": event_id,
                    "threadId": str(conversation_id),
                    "runId": run_id,
                    "sequence": sequence - 1,
                    "state": {"selection": {"required": False}}
                    if event_type == "STATE_SNAPSHOT"
                    else None,
                },
                f_visible_to_user=True,
                f_trace_id="trace-stream",
                f_correlation_id="corr-stream",
                f_created_time=1_800_000_001_000,
                f_updated_time=1_800_000_001_000,
            )
        )
    await engine.dispose()
