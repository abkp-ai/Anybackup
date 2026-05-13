import asyncio
from types import SimpleNamespace

from app.bootstrap import app_factory
from app.bootstrap.settings import Settings


class FakeConsumer:
    def __init__(self) -> None:
        self.started = False
        self.closed = False

    async def start(self) -> None:
        self.started = True

    async def close(self) -> None:
        self.closed = True


class FakePublisher:
    def __init__(self) -> None:
        self.closed = False

    async def close(self) -> None:
        self.closed = True


class FakeTask:
    def __init__(self, name: str | None) -> None:
        self.name = name
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True

    def __await__(self):
        async def _wait() -> None:
            if self.cancelled:
                raise asyncio.CancelledError

        return _wait().__await__()


class FakeContainer:
    def __init__(self) -> None:
        self._core_agent_status_consumer = FakeConsumer()
        self._decision_agent_ag_ui_consumer = FakeConsumer()
        self._core_agent_kweaver_consumer = FakeConsumer()
        self._event_publisher = FakePublisher()

    def core_agent_status_consumer(self) -> FakeConsumer:
        return self._core_agent_status_consumer

    def decision_agent_ag_ui_consumer(self) -> FakeConsumer:
        return self._decision_agent_ag_ui_consumer

    def core_agent_kweaver_consumer(self) -> FakeConsumer:
        return self._core_agent_kweaver_consumer

    def event_publisher(self) -> FakePublisher:
        return self._event_publisher


def test_lifespan_starts_all_background_worker_loops(monkeypatch) -> None:
    created_tasks: list[FakeTask] = []

    def fake_create_task(coro, *, name=None):  # type: ignore[no-untyped-def]
        coro.close()
        task = FakeTask(name)
        created_tasks.append(task)
        return task

    async def exercise() -> None:
        container = FakeContainer()
        settings = Settings(background_workers_enabled=True)
        app = SimpleNamespace(state=SimpleNamespace())
        monkeypatch.setattr(app_factory.asyncio, "create_task", fake_create_task)

        async with app_factory._lifespan(container, settings)(app):
            assert tuple(task.name for task in app.state.background_worker_tasks) == (
                "conversation-service-outbox-publisher",
                "conversation-service-context-merge-worker",
                "conversation-service-retention-worker",
            )
            assert container._core_agent_status_consumer.started is True
            assert container._decision_agent_ag_ui_consumer.started is True
            assert container._core_agent_kweaver_consumer.started is True

        assert all(task.cancelled for task in created_tasks)
        assert container._core_agent_status_consumer.closed is True
        assert container._decision_agent_ag_ui_consumer.closed is True
        assert container._core_agent_kweaver_consumer.closed is True
        assert container._event_publisher.closed is True

    asyncio.run(exercise())
