import logging
from datetime import UTC, datetime
from typing import Any, Protocol

import aio_pika
from aio_pika import ExchangeType

from app.application.commands.agent_events import DecisionAgentBusinessDataCommand
from app.application.use_cases.business_data_to_ag_ui import BusinessDataToAgUiConverter
from app.infrastructure.messaging.rabbitmq.publisher import decode_message_body

logger = logging.getLogger(__name__)

DECISION_AGENT_BIZDATA_EXCHANGE = "decision_agent.bizdata.events"
DECISION_AGENT_BIZDATA_ROUTING_KEY = "decision_agent.session.business_data.v1"


class IncomingMessage(Protocol):
    body: bytes

    async def ack(self) -> None:
        raise NotImplementedError

    async def reject(self, *, requeue: bool) -> None:
        raise NotImplementedError


class DecisionAgentBizdataMessageConsumer:
    def __init__(self, *, converter: BusinessDataToAgUiConverter) -> None:
        self._converter = converter

    async def process_message(self, message: IncomingMessage) -> None:
        try:
            command = _command_from_body(decode_message_body(message.body))
            logger.info(
                "decision_agent_business_data_consume_enter",
                extra={
                    "event_id": command.event_id,
                    "conversation_id": command.conversation_id,
                    "schema_type": command.schema_type,
                },
            )
            await self._converter.process_business_data(command)
            await message.ack()
        except Exception:
            logger.exception("decision_agent_bizdata_consume_failed")
            await message.reject(requeue=False)


class RabbitMqDecisionAgentBizdataConsumer:
    def __init__(
        self,
        *,
        rabbitmq_url: str,
        exchange_name: str = DECISION_AGENT_BIZDATA_EXCHANGE,
        queue_name: str,
        prefetch_count: int,
        converter: BusinessDataToAgUiConverter,
        routing_key: str = DECISION_AGENT_BIZDATA_ROUTING_KEY,
    ) -> None:
        self._rabbitmq_url = rabbitmq_url
        self._exchange_name = exchange_name
        self._queue_name = queue_name
        self._prefetch_count = prefetch_count
        self._routing_key = routing_key
        self._message_consumer = DecisionAgentBizdataMessageConsumer(converter=converter)
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None

    async def start(self) -> None:
        logger.info(
            "decision_agent_bizdata_consumer_start_enter",
            extra={"queue_name": self._queue_name, "prefetch_count": self._prefetch_count},
        )
        connection = await aio_pika.connect_robust(self._rabbitmq_url)
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=self._prefetch_count)
        exchange = await channel.declare_exchange(
            self._exchange_name,
            ExchangeType.TOPIC,
            durable=True,
        )
        queue = await channel.declare_queue(self._queue_name, durable=True)
        await queue.bind(exchange, routing_key=self._routing_key)
        await queue.consume(self._message_consumer.process_message, no_ack=False)
        self._connection = connection
        self._channel = channel

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
        self._connection = None
        self._channel = None


def _command_from_body(body: dict[str, Any]) -> DecisionAgentBusinessDataCommand:
    payload = body.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("decision agent business data payload must be an object")

    business_data = payload.get("business_data")
    if not isinstance(business_data, dict):
        raise ValueError("payload must contain business_data")

    return DecisionAgentBusinessDataCommand(
        event_id=str(body["event_id"]),
        event_type=str(body["event_type"]),
        source_service=str(body["source_service"]),
        conversation_id=int(payload["conversation_id"]),
        turn_id=_required_int(payload.get("turn_id")),
        message_id=int(payload["message_id"]),
        sequence=_required_int(payload.get("sequence")),
        content=str(payload.get("content") or ""),
        schema_type=str(business_data["schema_type"]),
        schema_version=str(business_data.get("schema_version") or "1"),
        data=business_data.get("data", {}),
        trace_id=str(body.get("trace_id") or ""),
        correlation_id=str(body.get("correlation_id") or ""),
        occurred_time=_occurred_at_to_ms(body.get("occurred_at")),
    )


def _required_int(value: object) -> int:
    if isinstance(value, bool):
        raise ValueError("integer value cannot be boolean")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    raise ValueError("integer value must be int or string")


def _occurred_at_to_ms(value: object) -> int | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("occurred_at must be a string")
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return int(parsed.timestamp() * 1000)
