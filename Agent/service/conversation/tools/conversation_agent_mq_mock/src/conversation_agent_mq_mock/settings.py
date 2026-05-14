from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Literal

from conversation_agent_mq_mock.messages import (
    DEFAULT_BIZDATA_EXCHANGE,
    DEFAULT_BIZDATA_ROUTING_KEY,
    DEFAULT_CORE_STATUS_QUEUE,
    DEFAULT_KWEAVER_EXCHANGE,
    DEFAULT_KWEAVER_ROUTING_KEY,
)

RunMode = Literal["business_data", "kweaver", "both"]


@dataclass(frozen=True, slots=True)
class Settings:
    rabbitmq_url: str
    conversation_exchange: str = "conversation.message.events"
    conversation_routing_key: str = "conversation.message.sent.v1"
    mock_input_queue: str = "core-agent-mock.message.events"
    core_status_queue: str = DEFAULT_CORE_STATUS_QUEUE
    bizdata_exchange: str = DEFAULT_BIZDATA_EXCHANGE
    bizdata_routing_key: str = DEFAULT_BIZDATA_ROUTING_KEY
    bizdata_queue: str = "conversation.decision_agent.bizdata"
    kweaver_exchange: str = DEFAULT_KWEAVER_EXCHANGE
    kweaver_routing_key: str = DEFAULT_KWEAVER_ROUTING_KEY
    kweaver_queue: str = "conversation.core_agent.kweaver"
    delay_ms: int = 800
    prefetch_count: int = 10
    worker_id: str = "conversation-agent-mq-mock"
    mode: RunMode = "business_data"

    @classmethod
    def from_env(cls) -> Settings:
        mode_value = os.getenv("MOCK_MODE", "business_data")
        if mode_value not in ("business_data", "kweaver", "both"):
            mode_value = "business_data"
        return cls(
            rabbitmq_url=_required_env("RABBITMQ_URL"),
            conversation_exchange=os.getenv(
                "CONVERSATION_EXCHANGE",
                "conversation.message.events",
            ),
            conversation_routing_key=os.getenv(
                "CONVERSATION_ROUTING_KEY",
                "conversation.message.sent.v1",
            ),
            mock_input_queue=os.getenv("MOCK_INPUT_QUEUE", "core-agent-mock.message.events"),
            core_status_queue=os.getenv("CORE_STATUS_QUEUE", DEFAULT_CORE_STATUS_QUEUE),
            bizdata_exchange=os.getenv("BIZDATA_EXCHANGE", DEFAULT_BIZDATA_EXCHANGE),
            bizdata_routing_key=os.getenv("BIZDATA_ROUTING_KEY", DEFAULT_BIZDATA_ROUTING_KEY),
            bizdata_queue=os.getenv("BIZDATA_QUEUE", "conversation.decision_agent.bizdata"),
            kweaver_exchange=os.getenv("KWEAVER_EXCHANGE", DEFAULT_KWEAVER_EXCHANGE),
            kweaver_routing_key=os.getenv("KWEAVER_ROUTING_KEY", DEFAULT_KWEAVER_ROUTING_KEY),
            kweaver_queue=os.getenv("KWEAVER_QUEUE", "conversation.core_agent.kweaver"),
            delay_ms=int(os.getenv("MOCK_DELAY_MS", "800")),
            prefetch_count=int(os.getenv("MOCK_PREFETCH_COUNT", "10")),
            worker_id=os.getenv("MOCK_WORKER_ID", "conversation-agent-mq-mock"),
            mode=mode_value,
        )


def _required_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value
