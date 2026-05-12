import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.conversation import Conversation, ConversationStatus
from app.infrastructure.persistence.sqlalchemy.models import Base
from app.infrastructure.persistence.sqlalchemy.repositories import SqlAlchemyConversationRepository


@pytest.mark.asyncio
async def test_conversation_repository_adds_and_loads_conversation() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        repository = SqlAlchemyConversationRepository(session)
        conversation = Conversation(
            conversation_id=1,
            owner_user_id="user-001",
            title="DB restore",
            status=ConversationStatus.ACTIVE,
            active_run_id=None,
            last_active_time=1_800_000_000_000,
            created_time=1_800_000_000_000,
            updated_time=1_800_000_000_000,
        )

        await repository.add(conversation)
        await session.commit()

    async with session_factory() as session:
        repository = SqlAlchemyConversationRepository(session)

        loaded = await repository.get_by_id(1)

    await engine.dispose()

    assert loaded == conversation
