import logging
from datetime import UTC, datetime
from typing import Any, Protocol

import aio_pika
from aio_pika import ExchangeType

from app.application.commands.agent_events import DecisionAgentAgUiEventCommand
from app.application.use_cases.decision_agent_ag_ui import DecisionAgentAgUiEventHandler
from app.infrastructure.messaging.rabbitmq.publisher import decode_message_body

logger = logging.getLogger(__name__)

DECISION_AGENT_AG_UI_EXCHANGE = "decision_agent.ag_ui.events"
DECISION_AGENT_AG_UI_ROUTING_KEY = "decision_agent.session.ag_ui_event.v1"


class IncomingMessage(Protocol):
    body: bytes

    async def ack(self) -> None:
        raise NotImplementedError

    async def reject(self, *, requeue: bool) -> None:
        raise NotImplementedError


class DecisionAgentAgUiHandler(Protocol):
    async def handle(self, command: DecisionAgentAgUiEventCommand) -> object:
        raise NotImplementedError


class DecisionAgentAgUiMessageConsumer:
    def __init__(self, *, handler: DecisionAgentAgUiHandler) -> None:
        self._handler = handler

    async def process_message(self, message: IncomingMessage) -> None:
        try:
            command = _command_from_body(decode_message_body(message.body))
            logger.info(
                "decision_agent_ag_ui_consume_enter",
                extra={
                    "event_id": command.event_id,
                    "conversation_id": command.conversation_id,
                    "turn_id": command.turn_id,
                    "message_id": command.message_id,
                    "sequence": command.sequence,
                },
            )
            await self._handler.handle(command)
            await message.ack()
        except Exception:
            logger.exception("decision_agent_ag_ui_consume_failed")
            await message.reject(requeue=False)


class RabbitMqDecisionAgentAgUiConsumer:
    def __init__(
        self,
        *,
        rabbitmq_url: str,
        exchange_name: str = DECISION_AGENT_AG_UI_EXCHANGE,
        queue_name: str,
        prefetch_count: int,
        handler: DecisionAgentAgUiEventHandler,
        routing_key: str = DECISION_AGENT_AG_UI_ROUTING_KEY,
    ) -> None:
        self._rabbitmq_url = rabbitmq_url
        self._exchange_name = exchange_name
        self._queue_name = queue_name
        self._prefetch_count = prefetch_count
        self._routing_key = routing_key
        self._message_consumer = DecisionAgentAgUiMessageConsumer(handler=handler)
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None
        self._channel: aio_pika.abc.AbstractChannel | None = None

    async def start(self) -> None:
        logger.info(
            "decision_agent_ag_ui_consumer_start_enter",
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


def _command_from_body(body: dict[str, Any]) -> DecisionAgentAgUiEventCommand:
    payload = body.get("payload")
    if not isinstance(payload, dict):
        raise ValueError("decision agent AG-UI payload must be an object")
    ag_ui_event = payload.get("ag_ui_event") or payload.get("event")
    if not isinstance(ag_ui_event, dict):
        raise ValueError("decision agent AG-UI event must be an object")
    return DecisionAgentAgUiEventCommand(
        event_id=str(body["event_id"]),
        event_type=str(body["event_type"]),
        source_service=str(body["source_service"]),
        conversation_id=int(payload["conversation_id"]),
        turn_id=_required_int(payload.get("turn_id")),
        message_id=int(payload["message_id"]),
        sequence=_required_int(payload.get("sequence")),
        ag_ui_event=ag_ui_event,
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
