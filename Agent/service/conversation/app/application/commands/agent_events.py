from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class CoreAgentStatusEventCommand:
    event_id: str
    event_type: str
    event_version: str
    conversation_id: int
    payload: dict[str, Any]
    message_id: int | None = None
    trace_id: str = ""
    correlation_id: str = ""
    occurred_time: int | None = None


@dataclass(frozen=True, slots=True)
class DecisionAgentAgUiEventCommand:
    event_id: str
    event_type: str
    source_service: str
    conversation_id: int
    turn_id: int
    message_id: int
    sequence: int
    ag_ui_event: dict[str, Any]
    trace_id: str = ""
    correlation_id: str = ""
    occurred_time: int | None = None


@dataclass(frozen=True, slots=True)
class CoreAgentKweaverStreamCommand:
    event_id: str
    event_type: str
    source_service: str
    conversation_id: int
    turn_id: int
    message_id: int
    run_id: str
    chunk_index: int
    kweaver_event: dict[str, Any]
    trace_id: str = ""
    correlation_id: str = ""
    occurred_time: int | None = None


@dataclass(frozen=True, slots=True)
class DecisionAgentBusinessDataCommand:
    event_id: str
    event_type: str
    source_service: str
    conversation_id: int
    turn_id: int
    message_id: int
    sequence: int
    content: str
    schema_type: str
    schema_version: str
    data: dict[str, Any]
    trace_id: str = ""
    correlation_id: str = ""
    occurred_time: int | None = None
