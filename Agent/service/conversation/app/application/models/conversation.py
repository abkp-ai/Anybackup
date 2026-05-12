from dataclasses import dataclass, field
from typing import Any

from app.domain.conversation import ConversationStatus
from app.domain.message import MessageStatus


@dataclass(frozen=True, slots=True)
class AuthenticatedUser:
    user_id: str
    preferred_username: str | None = None
    name: str | None = None
    email: str | None = None
    email_verified: bool | None = None
    roles: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class ConversationListQuery:
    keyword: str | None = None
    statuses: tuple[ConversationStatus, ...] = field(default_factory=tuple)
    archived: bool = False
    scenario_id: str | None = None
    task_type: str | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    created_after_time: int | None = None
    created_before_time: int | None = None
    last_active_after_time: int | None = None
    last_active_before_time: int | None = None
    cursor: str | None = None
    limit: int = 20
    sort: str = "last_active_desc"


@dataclass(frozen=True, slots=True)
class ConversationMessageListQuery:
    conversation_id: int
    cursor: str | None = None
    limit: int = 50
    role: str | None = None
    content_type: str | None = None
    status: MessageStatus | None = None
    created_after_time: int | None = None
    created_before_time: int | None = None


@dataclass(frozen=True, slots=True)
class Page:
    next_cursor: str | None
    has_more: bool
    limit: int


@dataclass(frozen=True, slots=True)
class ConversationRecord:
    conversation_id: int
    owner_user_id: str
    title: str
    status: ConversationStatus
    tags: tuple[str, ...]
    created_time: int
    updated_time: int
    last_active_time: int
    summary: str | None = None
    scenario_binding: dict[str, Any] | None = None
    latest_message_summary: str | None = None
    retention_policy: str = "conversation_default_v1"
    legal_hold: bool = False
    archived_time: int | None = None
    archived_by: str | None = None
    archive_reason: str | None = None
    expires_time: int | None = None
    expired_time: int | None = None
    active_run_id: str | None = None


@dataclass(frozen=True, slots=True)
class ConversationMessageRecord:
    message_id: int
    conversation_id: int
    role: str
    content_type: str
    status: MessageStatus
    created_time: int
    updated_time: int
    parent_message_id: int | None = None
    turn_id: int | None = None
    client_message_id: str | None = None
    content: str | None = None
    rich_payload: dict[str, Any] | None = None
    error_code: str | None = None
    trace_id: str | None = None
    correlation_id: str | None = None
    idempotency_key: str | None = None


@dataclass(frozen=True, slots=True)
class ConversationStatusEventRecord:
    status_event_id: int
    conversation_id: int
    event_type: str
    sequence: int
    created_time: int
    updated_time: int
    message_id: int | None = None
    turn_id: int | None = None
    message_status: MessageStatus | None = None
    title: str | None = None
    detail: str | None = None
    payload: dict[str, Any] | None = None
    rich_payload: dict[str, Any] | None = None
    trace_id: str | None = None
    correlation_id: str | None = None


@dataclass(frozen=True, slots=True)
class MqOutboxRecord:
    outbox_id: int
    event_id: str
    event_type: str
    routing_key: str
    conversation_id: int
    payload: dict[str, Any]
    status: str
    trace_id: str
    correlation_id: str
    created_time: int
    updated_time: int
    message_id: int | None = None
    attempt_count: int = 0
    next_retry_time: int | None = None
    last_error_code: str | None = None
    idempotency_key: str | None = None


@dataclass(frozen=True, slots=True)
class ConversationListResult:
    items: tuple[ConversationRecord, ...]
    page: Page


@dataclass(frozen=True, slots=True)
class ConversationMessageListResult:
    items: tuple[ConversationMessageRecord, ...]
    page: Page


@dataclass(frozen=True, slots=True)
class ConversationStatusEventListResult:
    items: tuple[ConversationStatusEventRecord, ...]
    page: Page
    latest_sequence: int = 0
    recommended_poll_interval_ms: int = 1000


@dataclass(frozen=True, slots=True)
class ConversationDetailResult:
    conversation: ConversationRecord
    latest_messages: tuple[ConversationMessageRecord, ...]
    latest_events: tuple[ConversationStatusEventRecord, ...]
    context: None = None


@dataclass(frozen=True, slots=True)
class MessageAcceptedResult:
    message: ConversationMessageRecord
    conversation: ConversationRecord
    status_event: ConversationStatusEventRecord
    next_poll_after_ms: int = 1000
