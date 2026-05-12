import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import create_async_engine

from app.application.commands.conversation import (
    CreateConversationCommand,
    SendUserMessageCommand,
)
from app.application.models.conversation import AuthenticatedUser
from app.application.use_cases.conversation import (
    CreateConversationHandler,
    SendUserMessageHandler,
)
from app.infrastructure.persistence.sqlalchemy.models import (
    Base,
    ConversationMessageModel,
    ConversationModel,
    ConversationMqOutboxModel,
)
from app.infrastructure.persistence.sqlalchemy.session import create_async_session_factory
from app.infrastructure.persistence.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWork


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
async def test_create_conversation_outbox_payload_matches_core_agent_contract(
    database_url: str,
) -> None:
    handler = CreateConversationHandler(
        unit_of_work_factory=_unit_of_work_factory(database_url),
        id_generator=FakeIdGenerator(start=100),
    )

    result = await handler.handle(
        CreateConversationCommand(
            initial_message_content="restore database",
            initial_message_client_id="client-001",
            title=None,
            scenario_binding=None,
            tags=(),
            source="web",
            idempotency_key=None,
            request_id="req-001",
        ),
        AuthenticatedUser(user_id="user-001"),
    )

    outbox = await _latest_outbox(database_url)
    assert outbox.f_payload == {
        "conversation_id": str(result.conversation.conversation_id),
        "message_id": str(result.message.message_id),
        "turn_id": str(result.message.turn_id),
        "content": "restore database",
    }
    assert await _assistant_message_count(database_url) == 0


@pytest.mark.asyncio
async def test_send_user_message_outbox_payload_excludes_ui_only_fields(
    database_url: str,
) -> None:
    await _insert_idle_conversation(database_url, conversation_id=700)
    handler = SendUserMessageHandler(
        unit_of_work_factory=_unit_of_work_factory(database_url),
        id_generator=FakeIdGenerator(start=900),
    )

    result = await handler.handle(
        SendUserMessageCommand(
            conversation_id=700,
            content="confirm candidate",
            client_message_id="client-002",
            parent_message_id=None,
            idempotency_key=None,
            request_id="req-002",
            submission_type="clarification_response",
        ),
        AuthenticatedUser(user_id="user-001"),
    )

    assert result is not None
    outbox = await _latest_outbox(database_url)
    assert outbox.f_payload == {
        "conversation_id": "700",
        "message_id": str(result.message.message_id),
        "turn_id": str(result.message.turn_id),
        "content": "confirm candidate",
    }
    assert await _assistant_message_count(database_url) == 0


def _unit_of_work_factory(database_url: str):
    engine = create_async_engine(database_url)
    session_factory = create_async_session_factory(engine)
    return lambda: SqlAlchemyUnitOfWork(session_factory)


async def _insert_idle_conversation(database_url: str, *, conversation_id: int) -> None:
    engine = create_async_engine(database_url)
    async with engine.begin() as connection:
        await connection.execute(
            ConversationModel.__table__.insert().values(
                f_conversation_id=conversation_id,
                f_owner_user_id="user-001",
                f_tenant_id=None,
                f_title="restore backup",
                f_display_summary=None,
                f_status="active",
                f_active_run_id=None,
                f_active_turn_id=None,
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
    await engine.dispose()


async def _latest_outbox(database_url: str) -> ConversationMqOutboxModel:
    engine = create_async_engine(database_url)
    session_factory = create_async_session_factory(engine)
    async with session_factory() as session:
        row = await session.scalar(
            select(ConversationMqOutboxModel)
            .order_by(ConversationMqOutboxModel.f_created_time.desc())
            .limit(1)
        )
    await engine.dispose()
    assert row is not None
    return row


async def _assistant_message_count(database_url: str) -> int:
    engine = create_async_engine(database_url)
    session_factory = create_async_session_factory(engine)
    async with session_factory() as session:
        count = await session.scalar(
            select(func.count(ConversationMessageModel.f_message_id)).where(
                ConversationMessageModel.f_role == "assistant"
            )
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
