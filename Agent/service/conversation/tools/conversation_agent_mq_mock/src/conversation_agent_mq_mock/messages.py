from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

DEFAULT_CORE_STATUS_QUEUE = "conversation.core_agent.status.v1"
DEFAULT_AG_UI_EXCHANGE = "decision_agent.ag_ui.events"
DEFAULT_AG_UI_ROUTING_KEY = "decision_agent.session.business_data.v1"


@dataclass(frozen=True, slots=True)
class IncomingConversationMessage:
    event_id: str
    conversation_id: str
    message_id: str
    turn_id: str
    content: str
    trace_id: str
    correlation_id: str

    @classmethod
    def from_body(cls, body: dict[str, Any]) -> IncomingConversationMessage:
        payload = body.get("payload") or {}
        if not isinstance(payload, dict):
            raise ValueError("conversation message payload must be an object")

        conversation_id = payload.get("conversation_id") or body.get("conversation_id")
        message_id = payload.get("message_id") or body.get("message_id")
        turn_id = payload.get("turn_id") or body.get("turn_id")
        content = payload.get("content")
        if conversation_id is None or message_id is None or turn_id is None or content is None:
            raise ValueError(
                "conversation message requires conversation_id, message_id, turn_id, content"
            )

        return cls(
            event_id=str(body["event_id"]),
            conversation_id=str(conversation_id),
            message_id=str(message_id),
            turn_id=str(turn_id),
            content=str(content),
            trace_id=str(payload.get("trace_id") or body.get("trace_id") or ""),
            correlation_id=str(payload.get("correlation_id") or body.get("correlation_id") or ""),
        )


@dataclass(frozen=True, slots=True)
class OutgoingMqMessage:
    body: dict[str, Any]
    routing_key: str
    exchange: str | None = None
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def event_id(self) -> str:
        return str(self.body["event_id"])


@dataclass(frozen=True, slots=True)
class AgUiStep:
    sequence: int
    content: str
    events: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class BusinessDataStep:
    sequence: int
    content: str
    schema_type: str
    schema_version: str = "1"
    data: dict[str, Any] = field(default_factory=dict)


def build_core_status_message(
    incoming: IncomingConversationMessage,
    *,
    kind: Literal["accepted", "rejected", "failed"],
    core_agent_run_id: str,
    now_ms: int,
    status_queue: str = DEFAULT_CORE_STATUS_QUEUE,
    error_code: str | None = None,
    error_message: str | None = None,
    retryable: bool = False,
) -> OutgoingMqMessage:
    payload: dict[str, Any] = {
        "conversation_id": incoming.conversation_id,
        "message_id": incoming.message_id,
        "turn_id": incoming.turn_id,
    }
    if kind == "accepted":
        payload["content"] = incoming.content
        payload["accepted"] = {
            "input_event_id": incoming.event_id,
            "core_agent_run_id": core_agent_run_id,
            "estimated_status": "processing",
        }
    else:
        payload[kind] = {
            "code": error_code or "CORE_AGENT_MOCK_FAILURE",
            "message": error_message or "Mock core agent returned a simulated failure.",
            "retryable": retryable,
        }

    body = {
        "event_id": f"core-agent.{kind}.{incoming.message_id}",
        "event_type": f"core_agent.run.{kind}",
        "event_version": "v1",
        "occurred_at": _ms_to_iso(now_ms),
        "payload": payload,
        "trace_id": incoming.trace_id,
        "correlation_id": incoming.correlation_id,
    }
    return OutgoingMqMessage(
        body=body,
        routing_key=status_queue,
        headers=_headers(incoming.trace_id, incoming.correlation_id),
    )


def build_ag_ui_message(
    incoming: IncomingConversationMessage,
    *,
    step: AgUiStep,
    now_ms: int,
    exchange: str = DEFAULT_AG_UI_EXCHANGE,
    routing_key: str = DEFAULT_AG_UI_ROUTING_KEY,
    source_service: str = "decision_agent_session",
) -> OutgoingMqMessage:
    event_id = f"decision-agent.ag-ui.{incoming.message_id}.{step.sequence}"
    body = {
        "event_id": event_id,
        "event_type": "decision_agent.session.ag_ui_event",
        "occurred_at": _ms_to_iso(now_ms),
        "source_service": source_service,
        "trace_id": incoming.trace_id,
        "correlation_id": incoming.correlation_id,
        "payload": {
            "conversation_id": incoming.conversation_id,
            "turn_id": incoming.turn_id,
            "message_id": _assistant_output_message_id(incoming),
            "content": step.content,
            "sequence": step.sequence,
            "ag_ui": _markdown_from_step(step),
        },
    }
    return OutgoingMqMessage(
        body=body,
        exchange=exchange,
        routing_key=routing_key,
        headers=_headers(incoming.trace_id, incoming.correlation_id),
    )


def build_business_data_message(
    incoming: IncomingConversationMessage,
    *,
    step: BusinessDataStep,
    now_ms: int,
    exchange: str = DEFAULT_AG_UI_EXCHANGE,
    routing_key: str = DEFAULT_AG_UI_ROUTING_KEY,
    source_service: str = "decision_agent_session",
) -> OutgoingMqMessage:
    event_id = f"decision-agent.bizdata.{incoming.message_id}.{step.sequence}"
    body = {
        "event_id": event_id,
        "event_type": "decision_agent.session.business_data",
        "occurred_at": _ms_to_iso(now_ms),
        "source_service": source_service,
        "trace_id": incoming.trace_id,
        "correlation_id": incoming.correlation_id,
        "payload": {
            "conversation_id": incoming.conversation_id,
            "turn_id": incoming.turn_id,
            "message_id": _assistant_output_message_id(incoming),
            "content": step.content,
            "sequence": step.sequence,
            "business_data": {
                "schema_type": step.schema_type,
                "schema_version": step.schema_version,
                "data": step.data,
            },
        },
    }
    return OutgoingMqMessage(
        body=body,
        exchange=exchange,
        routing_key=routing_key,
        headers=_headers(incoming.trace_id, incoming.correlation_id),
    )


def _headers(trace_id: str, correlation_id: str) -> dict[str, str]:
    headers = {
        "trace_id": trace_id,
        "correlation_id": correlation_id,
    }
    if trace_id:
        headers["traceparent"] = _traceparent(trace_id)
    return headers


def _traceparent(trace_id: str) -> str:
    sanitized = "".join(ch for ch in trace_id.lower() if ch in "0123456789abcdef")
    trace_hex = sanitized[:32].ljust(32, "0")
    return f"00-{trace_hex}-0000000000000000-01"


def _ms_to_iso(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, UTC).isoformat().replace("+00:00", "Z")


def _assistant_output_message_id(incoming: IncomingConversationMessage) -> str:
    try:
        return str(int(incoming.turn_id) + 10_000)
    except ValueError:
        return f"{incoming.turn_id}-assistant"


def _markdown_from_step(step: AgUiStep) -> str:
    chunks: list[str] = []
    if step.content:
        chunks.append(f"# {step.content}")

    for event in step.events:
        if event.get("type") != "ACTIVITY_SNAPSHOT":
            continue
        content = event.get("content")
        if not isinstance(content, dict):
            continue
        actions_by_id = {
            str(action.get("id")): str(action.get("label"))
            for action in content.get("actions", [])
            if isinstance(action, dict) and action.get("id") and action.get("label")
        }
        ui = content.get("ui")
        chunks.extend(_node_markdown(ui, actions_by_id=actions_by_id))

    return "\n\n".join(chunk for chunk in chunks if chunk.strip()) or step.content


def _node_markdown(node: object, *, actions_by_id: dict[str, str]) -> list[str]:
    if not isinstance(node, dict):
        return []

    node_type = node.get("type")
    props = node.get("props")
    if not isinstance(props, dict):
        props = {}

    if node_type == "heading":
        level = props.get("level", 2)
        if isinstance(level, bool) or not isinstance(level, int):
            level = 2
        hashes = "#" * max(1, min(level, 6))
        text = str(props.get("text") or "").strip()
        return [f"{hashes} {text}"] if text else []

    if node_type in {"paragraph", "markdown"}:
        text = str(props.get("text") or props.get("markdown") or "").strip()
        return [text] if text else []

    if node_type == "callout":
        title = str(props.get("title") or "提示").strip()
        text = str(props.get("text") or "").strip()
        body = f"> **{title}**"
        if text:
            body = f"{body}\n>\n> {text}"
        return [body]

    if node_type in {"kv-list", "metric-list"}:
        return _items_table(props.get("items"))

    if node_type == "data-table":
        return _data_table(props.get("columns"), props.get("rows"))

    if node_type == "chart":
        chart_type = str(props.get("chartType") or "chart")
        return [f"图表：{chart_type}"]

    if node_type == "attachment-list":
        return _attachment_list(props.get("items"))

    if node_type == "action-row":
        labels = [
            actions_by_id.get(str(action_id), str(action_id))
            for action_id in props.get("actionIds", [])
        ]
        labels = [label for label in labels if label]
        return [f"可选动作：{', '.join(labels)}"] if labels else []

    chunks: list[str] = []
    title = props.get("title")
    if node_type == "card" and isinstance(title, str) and title.strip():
        chunks.append(f"## {title.strip()}")
    for child in node.get("children", []):
        chunks.extend(_node_markdown(child, actions_by_id=actions_by_id))
    return chunks


def _items_table(items: object) -> list[str]:
    if not isinstance(items, list) or not items:
        return []
    rows = ["| 项目 | 值 |", "| --- | --- |"]
    for item in items:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or item.get("name") or "").strip()
        value = str(item.get("value") or "").strip()
        if label or value:
            rows.append(f"| {label} | {value} |")
    return ["\n".join(rows)] if len(rows) > 2 else []


def _data_table(columns: object, rows: object) -> list[str]:
    if not isinstance(columns, list) or not isinstance(rows, list) or not columns:
        return []
    column_defs = [column for column in columns if isinstance(column, dict)]
    keys = [str(column.get("key")) for column in column_defs if column.get("key")]
    labels = [str(column.get("label") or column.get("key")) for column in column_defs]
    if not keys:
        return []
    table = [
        "| " + " | ".join(labels) + " |",
        "| " + " | ".join("---" for _ in labels) + " |",
    ]
    for row in rows:
        if not isinstance(row, dict):
            continue
        table.append("| " + " | ".join(str(row.get(key, "")) for key in keys) + " |")
    return ["\n".join(table)]


def _attachment_list(items: object) -> list[str]:
    if not isinstance(items, list) or not items:
        return []
    lines = ["附件："]
    for item in items:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or item.get("name") or "未命名附件")
        ref_id = str(item.get("refId") or item.get("id") or "")
        lines.append(f"- {title}" + (f" ({ref_id})" if ref_id else ""))
    return ["\n".join(lines)]
