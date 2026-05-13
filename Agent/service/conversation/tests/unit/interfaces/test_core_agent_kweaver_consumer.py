import pytest

from app.application.commands.agent_events import CoreAgentKweaverStreamCommand
from app.interfaces.mq import core_agent_kweaver_consumer
from app.interfaces.mq.core_agent_kweaver_consumer import (
    RabbitMqCoreAgentKweaverConsumer,
    _command_from_body,
)


@pytest.mark.asyncio
async def test_kweaver_consumer_binds_exchange(monkeypatch) -> None:
    connection = FakeConnection()

    async def fake_connect_robust(url: str) -> FakeConnection:
        connection.url = url
        return connection

    monkeypatch.setattr(
        core_agent_kweaver_consumer.aio_pika,
        "connect_robust",
        fake_connect_robust,
    )
    consumer = RabbitMqCoreAgentKweaverConsumer(
        rabbitmq_url="amqp://guest:guest@localhost:5672/",
        exchange_name="core_agent.kweaver.stream",
        queue_name="conversation.core_agent.kweaver",
        prefetch_count=10,
        converter=NoopConverter(),
    )

    await consumer.start()

    assert connection.url == "amqp://guest:guest@localhost:5672/"
    assert connection.channel_instance.declared_exchanges == [
        {"name": "core_agent.kweaver.stream", "durable": True}
    ]
    assert connection.channel_instance.queue.bind_calls == [
        {
            "exchange": "core_agent.kweaver.stream",
            "routing_key": "core_agent.kweaver.stream_event.v1",
        }
    ]


def test_command_from_body_parses_kweaver_event() -> None:
    command = _command_from_body(
        {
            "event_id": "kw-evt-001",
            "event_type": "core_agent.kweaver.stream_event",
            "source_service": "core_agent_service",
            "occurred_at": "2026-05-13T10:00:00Z",
            "payload": {
                "conversation_id": 100,
                "turn_id": 200,
                "message_id": 901,
                "run_id": "run-001",
                "chunk_index": 1,
                "kweaver_event": {
                    "key": "progress",
                    "content": {"progress": [{"skill_info": {"name": "search"}}]},
                    "finished": False,
                },
            },
        }
    )
    assert isinstance(command, CoreAgentKweaverStreamCommand)
    assert command.conversation_id == 100
    assert command.run_id == "run-001"
    assert command.chunk_index == 1
    assert command.kweaver_event["key"] == "progress"


def test_command_from_body_rejects_missing_kweaver_event() -> None:
    with pytest.raises(ValueError, match="kweaver_event"):
        _command_from_body(
            {
                "event_id": "kw-evt-invalid",
                "event_type": "core_agent.kweaver.stream_event",
                "source_service": "core_agent_service",
                "occurred_at": "2026-05-13T10:00:00Z",
                "payload": {
                    "conversation_id": 100,
                    "turn_id": 200,
                    "message_id": 901,
                    "run_id": "run-001",
                    "chunk_index": 1,
                },
            }
        )


class NoopConverter:
    async def process_stream_event(self, command: CoreAgentKweaverStreamCommand) -> None:
        pass


class FakeConnection:
    def __init__(self) -> None:
        self.url = ""
        self.channel_instance = FakeChannel()

    async def channel(self) -> "FakeChannel":
        return self.channel_instance

    async def close(self) -> None:
        pass


class FakeChannel:
    def __init__(self) -> None:
        self.qos_calls: list[int] = []
        self.declared_exchanges: list[dict[str, object]] = []
        self.declared_queues: list[dict[str, object]] = []
        self.queue = FakeQueue()

    async def set_qos(self, *, prefetch_count: int) -> None:
        self.qos_calls.append(prefetch_count)

    async def declare_exchange(self, name: str, exchange_type, *, durable: bool):
        del exchange_type
        self.declared_exchanges.append({"name": name, "durable": durable})
        return FakeExchange(name=name)

    async def declare_queue(self, name: str, *, durable: bool) -> "FakeQueue":
        self.declared_queues.append({"name": name, "durable": durable})
        return self.queue


class FakeExchange:
    def __init__(self, *, name: str) -> None:
        self.name = name


class FakeQueue:
    def __init__(self) -> None:
        self.bind_calls: list[dict[str, str]] = []
        self.consume_calls: list[bool] = []

    async def bind(self, exchange: FakeExchange, *, routing_key: str) -> None:
        self.bind_calls.append({"exchange": exchange.name, "routing_key": routing_key})

    async def consume(self, callback, *, no_ack: bool) -> None:
        del callback
        self.consume_calls.append(no_ack)
