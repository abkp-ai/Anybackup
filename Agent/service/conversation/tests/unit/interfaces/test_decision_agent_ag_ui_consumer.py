import pytest

from app.application.commands.agent_events import DecisionAgentBusinessDataCommand
from app.interfaces.mq import decision_agent_ag_ui_consumer
from app.interfaces.mq.decision_agent_ag_ui_consumer import (
    RabbitMqDecisionAgentAgUiConsumer,
    _command_from_body,
)


@pytest.mark.asyncio
async def test_ag_ui_consumer_binds_decision_agent_exchange(monkeypatch) -> None:
    connection = FakeConnection()

    async def fake_connect_robust(url: str) -> FakeConnection:
        connection.url = url
        return connection

    monkeypatch.setattr(
        decision_agent_ag_ui_consumer.aio_pika,
        "connect_robust",
        fake_connect_robust,
    )
    consumer = RabbitMqDecisionAgentAgUiConsumer(
        rabbitmq_url="amqp://guest:guest@localhost:5672/",
        exchange_name="decision_agent.ag_ui.events",
        queue_name="conversation.decision_agent.ag_ui",
        prefetch_count=10,
        converter=NoopConverter(),
    )

    await consumer.start()

    assert connection.url == "amqp://guest:guest@localhost:5672/"
    assert connection.channel_instance.qos_calls == [10]
    assert connection.channel_instance.declared_exchanges == [
        {"name": "decision_agent.ag_ui.events", "durable": True}
    ]
    assert connection.channel_instance.declared_queues == [
        {"name": "conversation.decision_agent.ag_ui", "durable": True}
    ]
    assert connection.channel_instance.queue.bind_calls == [
        {
            "exchange": "decision_agent.ag_ui.events",
            "routing_key": "decision_agent.session.business_data.v1",
        }
    ]
    assert connection.channel_instance.queue.consume_calls == [False]


def test_command_from_body_parses_business_data() -> None:
    command = _command_from_body(
        {
            "event_id": "evt-bizdata-001",
            "event_type": "decision_agent.session.business_data",
            "source_service": "decision_agent_session",
            "occurred_at": "2026-05-13T10:00:00Z",
            "payload": {
                "conversation_id": "100",
                "turn_id": "200",
                "message_id": "901",
                "content": "恢复候选方案",
                "sequence": 1,
                "business_data": {
                    "schema_type": "plan_candidates",
                    "schema_version": "1",
                    "data": {
                        "heading": "恢复候选方案",
                        "candidates": [
                            {
                                "candidate_option_id": "a",
                                "title": "方案A",
                                "summary": "推荐",
                                "recommendation_level": "recommended",
                                "risk_level": "medium",
                            }
                        ],
                    },
                },
            },
        }
    )
    assert isinstance(command, DecisionAgentBusinessDataCommand)
    assert command.schema_type == "plan_candidates"
    assert command.schema_version == "1"
    assert command.content == "恢复候选方案"
    assert command.data["heading"] == "恢复候选方案"
    assert len(command.data["candidates"]) == 1


def test_command_from_body_defaults_schema_version() -> None:
    command = _command_from_body(
        {
            "event_id": "evt-bizdata-002",
            "event_type": "decision_agent.session.business_data",
            "source_service": "decision_agent_session",
            "occurred_at": "2026-05-13T10:00:00Z",
            "payload": {
                "conversation_id": "100",
                "turn_id": "200",
                "message_id": "901",
                "content": "text",
                "sequence": 1,
                "business_data": {
                    "schema_type": "text_message",
                    "data": {"text": "hello"},
                },
            },
        }
    )
    assert command.schema_version == "1"


def test_command_from_body_rejects_missing_business_data() -> None:
    with pytest.raises(ValueError, match="business_data"):
        _command_from_body(
            {
                "event_id": "evt-invalid",
                "event_type": "decision_agent.session.business_data",
                "source_service": "decision_agent_session",
                "occurred_at": "2026-05-13T10:00:00Z",
                "payload": {
                    "conversation_id": "100",
                    "turn_id": "200",
                    "message_id": "901",
                    "sequence": 1,
                },
            }
        )


def test_command_from_body_rejects_non_dict_business_data() -> None:
    with pytest.raises(ValueError, match="business_data"):
        _command_from_body(
            {
                "event_id": "evt-invalid",
                "event_type": "decision_agent.session.business_data",
                "source_service": "decision_agent_session",
                "occurred_at": "2026-05-13T10:00:00Z",
                "payload": {
                    "conversation_id": "100",
                    "turn_id": "200",
                    "message_id": "901",
                    "sequence": 1,
                    "business_data": "not a dict",
                },
            }
        )


class NoopConverter:
    async def process_business_data(self, command: DecisionAgentBusinessDataCommand) -> None:
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
