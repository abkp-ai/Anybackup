from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Awaitable, Callable

import aio_pika
from aio_pika import DeliveryMode, ExchangeType, Message

from conversation_agent_mq_mock.messages import OutgoingMqMessage
from conversation_agent_mq_mock.runner import AgentMqMockRunner, decode_json_body
from conversation_agent_mq_mock.settings import Settings

logger = logging.getLogger(__name__)


class RabbitMqPublisher:
    def __init__(self, channel: aio_pika.abc.AbstractChannel) -> None:
        self._channel = channel
        self._exchanges: dict[str, aio_pika.abc.AbstractExchange] = {}

    async def publish(self, message: OutgoingMqMessage) -> None:
        payload = Message(
            body=json.dumps(message.body, ensure_ascii=False).encode("utf-8"),
            content_type="application/json",
            delivery_mode=DeliveryMode.PERSISTENT,
            message_id=message.event_id,
            correlation_id=str(message.body.get("correlation_id") or ""),
            headers=dict(message.headers),
        )
        if message.exchange is None:
            await self._channel.default_exchange.publish(payload, routing_key=message.routing_key)
            return
        exchange = await self._exchange(message.exchange)
        await exchange.publish(payload, routing_key=message.routing_key, mandatory=True)

    async def _exchange(self, exchange_name: str) -> aio_pika.abc.AbstractExchange:
        exchange = self._exchanges.get(exchange_name)
        if exchange is not None:
            return exchange
        exchange = await self._channel.declare_exchange(
            exchange_name,
            ExchangeType.TOPIC,
            durable=True,
        )
        self._exchanges[exchange_name] = exchange
        return exchange


class RabbitMqMockService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._connection: aio_pika.abc.AbstractRobustConnection | None = None

    async def run_forever(self) -> None:
        connection = await aio_pika.connect_robust(self._settings.rabbitmq_url)
        self._connection = connection
        channel = await connection.channel(publisher_confirms=True)
        await channel.set_qos(prefetch_count=self._settings.prefetch_count)

        conversation_exchange = await channel.declare_exchange(
            self._settings.conversation_exchange,
            ExchangeType.TOPIC,
            durable=True,
        )
        await channel.declare_queue(self._settings.core_status_queue, durable=True)
        bizdata_exchange = await channel.declare_exchange(
            self._settings.bizdata_exchange,
            ExchangeType.TOPIC,
            durable=True,
        )
        bizdata_queue = await channel.declare_queue(self._settings.bizdata_queue, durable=True)
        await bizdata_queue.bind(
            bizdata_exchange,
            routing_key=self._settings.bizdata_routing_key,
        )
        if self._settings.mode in ("kweaver", "both"):
            kweaver_exchange = await channel.declare_exchange(
                self._settings.kweaver_exchange,
                ExchangeType.TOPIC,
                durable=True,
            )
            kweaver_queue = await channel.declare_queue(self._settings.kweaver_queue, durable=True)
            await kweaver_queue.bind(
                kweaver_exchange,
                routing_key=self._settings.kweaver_routing_key,
            )
        queue = await channel.declare_queue(self._settings.mock_input_queue, durable=True)
        await queue.bind(
            conversation_exchange,
            routing_key=self._settings.conversation_routing_key,
        )

        runner = AgentMqMockRunner(
            settings=self._settings,
            publisher=RabbitMqPublisher(channel),
            mode=self._settings.mode,
        )

        await queue.consume(_consumer(runner), no_ack=False)
        logger.info(
            "mock_service_started",
            extra={
                "queue": self._settings.mock_input_queue,
                "exchange": self._settings.conversation_exchange,
                "routing_key": self._settings.conversation_routing_key,
                "bizdata_queue": self._settings.bizdata_queue,
                "mode": self._settings.mode,
            },
        )
        await asyncio.Future()

    async def close(self) -> None:
        if self._connection is not None:
            await self._connection.close()
        self._connection = None


def _consumer(
    runner: AgentMqMockRunner,
) -> Callable[[aio_pika.abc.AbstractIncomingMessage], Awaitable[None]]:
    async def process(message: aio_pika.abc.AbstractIncomingMessage) -> None:
        try:
            await runner.handle_body(decode_json_body(message.body))
            await message.ack()
        except Exception:
            logger.exception("mock_message_failed")
            await message.reject(requeue=False)

    return process
