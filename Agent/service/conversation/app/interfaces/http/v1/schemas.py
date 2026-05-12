from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")


class MessageAttachmentRef(StrictSchema):
    attachment_id: str = Field(min_length=1, max_length=120)
    name: str | None = Field(default=None, max_length=255)
    content_type: str | None = Field(default=None, max_length=120)


class UserMessageRequest(StrictSchema):
    type: Literal["user_message"]
    content: str = Field(min_length=1, max_length=20_000)
    client_message_id: str | None = Field(default=None, max_length=80)
    parent_message_id: str | None = Field(default=None, max_length=80)
    attachments: list[MessageAttachmentRef] = Field(default_factory=list, max_length=20)
    input_context: dict[str, str] | None = None
    idempotency_key: str | None = Field(default=None, max_length=128)


class CandidateSelectionMessageRequest(StrictSchema):
    type: Literal["candidate_selection"]
    message_id: str | None = Field(default=None, max_length=80)
    reasoning_trace_id: str = Field(min_length=1, max_length=80)
    candidate_option_id: str = Field(min_length=1, max_length=80)
    selection: Literal["confirm", "reject", "revise"]
    additional_constraints: str | None = Field(default=None, max_length=4_000)
    client_message_id: str | None = Field(default=None, max_length=80)
    idempotency_key: str | None = Field(default=None, max_length=128)


class ClarificationResponseRequest(StrictSchema):
    type: Literal["clarification_response"]
    message_id: str | None = Field(default=None, max_length=80)
    clarification_id: str | None = Field(default=None, max_length=120)
    selected_value: str | None = Field(default=None, max_length=500)
    free_text: str | None = Field(default=None, max_length=4_000)
    client_message_id: str | None = Field(default=None, max_length=80)
    idempotency_key: str | None = Field(default=None, max_length=128)

    @model_validator(mode="after")
    def validate_response_content(self) -> ClarificationResponseRequest:
        if not self.selected_value and not self.free_text:
            raise ValueError("clarification response requires selected_value or free_text")
        return self


ConversationMessageCreateRequest = Annotated[
    UserMessageRequest | CandidateSelectionMessageRequest | ClarificationResponseRequest,
    Field(discriminator="type"),
]


class InitialConversationContext(StrictSchema):
    summary: str | None = Field(default=None, max_length=4_000)
    metadata: dict[str, str] | None = None


class ScenarioBinding(StrictSchema):
    scenario_id: str | None = Field(default=None, max_length=120)
    task_type: str | None = Field(default=None, max_length=120)
    asset_refs: list[str] = Field(default_factory=list, max_length=50)


class CreateConversationRequest(StrictSchema):
    initial_message: UserMessageRequest
    title: str | None = Field(default=None, min_length=1, max_length=120)
    scenario_binding: ScenarioBinding | None = None
    initial_context: InitialConversationContext | None = None
    tags: list[str] = Field(default_factory=list, max_length=20)
    source: Literal["web", "api", "system"] = "web"
    idempotency_key: str | None = Field(default=None, max_length=128)
    metadata: dict[str, str] | None = None


class UpdateConversationRequest(StrictSchema):
    title: str = Field(min_length=1, max_length=120)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = " ".join(value.strip().split())
        if not normalized:
            raise ValueError("title must not be blank")
        return normalized


class ConversationRetentionPolicy(StrictSchema):
    policy_id: str = "conversation_default_v1"
    auto_archive_after_days: int = 30
    archive_retention_days: int = 365
    hard_delete_enabled: bool = False
    large_object_retention_days: int | None = 90
    evaluated_at: str | None = None


class ConversationResponse(StrictSchema):
    conversation_id: str
    owner_user_id: str
    title: str
    status: Literal["created", "active", "paused", "archived", "expired"]
    summary: str | None = None
    scenario_binding: dict[str, object] | None = None
    tags: list[str]
    latest_message_summary: str | None = None
    active_run_id: str | None = None
    has_active_run: bool
    created_at: str
    updated_at: str
    last_active_at: str
    archived_at: str | None = None
    archived_by: Literal["user", "system"] | None = None
    archive_reason: str | None = None
    retention_policy: ConversationRetentionPolicy
    legal_hold: bool
    expires_at: str | None = None
    expired_at: str | None = None


class ConversationArchiveRequest(StrictSchema):
    reason: str | None = Field(default=None, max_length=500)


class ConversationRestoreRequest(StrictSchema):
    reason: str | None = Field(default=None, max_length=500)


class ConversationLegalHoldRequest(StrictSchema):
    enabled: bool
    reason: str | None = Field(default=None, max_length=500)


class CopyConversationConfigRequest(StrictSchema):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    copy_tags: bool = True
    copy_scenario_binding: bool = True
    additional_tags: list[str] = Field(default_factory=list, max_length=20)


class ConversationMessageResponse(StrictSchema):
    message_id: str
    conversation_id: str
    parent_message_id: str | None = None
    turn_id: str | None = None
    client_message_id: str | None = None
    role: Literal["user", "assistant", "system", "status"]
    content_type: Literal["text", "clarification", "rich_content", "status"]
    content: str | None = None
    rich_payload: dict[str, object] | None = None
    status: Literal[
        "received",
        "persisted",
        "published",
        "processing",
        "responded",
        "failed",
    ]
    error_code: str | None = None
    error_message: str | None = None
    reasoning_trace_id: str | None = None
    trace_id: str | None = None
    correlation_id: str | None = None
    created_at: str
    updated_at: str | None = None


class ConversationStatusEventResponse(StrictSchema):
    status_event_id: str
    conversation_id: str
    message_id: str | None = None
    turn_id: str | None = None
    event_type: Literal[
        "message.created",
        "message.updated",
        "RUN_STARTED",
        "RUN_FINISHED",
        "RUN_ERROR",
        "TEXT_MESSAGE_START",
        "TEXT_MESSAGE_CONTENT",
        "TEXT_MESSAGE_END",
        "TEXT_MESSAGE_CHUNK",
        "THINKING_START",
        "THINKING_TEXT_MESSAGE_START",
        "THINKING_TEXT_MESSAGE_CONTENT",
        "THINKING_TEXT_MESSAGE_END",
        "THINKING_END",
        "STATE_SNAPSHOT",
        "STATE_DELTA",
        "ACTIVITY_SNAPSHOT",
        "ACTIVITY_DELTA",
        "TOOL_CALL_START",
        "TOOL_CALL_ARGS",
        "TOOL_CALL_END",
        "TOOL_CALL_CHUNK",
        "TOOL_CALL_RESULT",
        "MESSAGES_SNAPSHOT",
        "STEP_STARTED",
        "STEP_FINISHED",
        "REASONING_START",
        "REASONING_MESSAGE_START",
        "REASONING_MESSAGE_CONTENT",
        "REASONING_MESSAGE_END",
        "REASONING_END",
        "RAW",
        "CUSTOM",
        "ERROR",
        "context.updated",
        "reasoning_trace.created",
        "rich_content.created",
        "rich_content.updated",
        "conversation.archived",
        "conversation.restored",
        "conversation.expired",
        "error",
    ]
    sequence: int
    message_status: str | None = None
    title: str | None = None
    detail: str | None = None
    payload: dict[str, object] | None = None
    rich_payload: dict[str, object] | None = None
    trace_id: str | None = None
    correlation_id: str | None = None
    occurred_at: str
    created_at: str


class PageMeta(StrictSchema):
    next_cursor: str | None = None
    has_more: bool
    limit: int


class ConversationListResponse(StrictSchema):
    items: list[ConversationResponse]
    page: PageMeta


class MessageListResponse(StrictSchema):
    items: list[ConversationMessageResponse]
    page: PageMeta


class ConversationDetailResponse(ConversationResponse):
    context: None = None
    latest_messages: list[ConversationMessageResponse]
    latest_events: list[ConversationStatusEventResponse]


class MessageAcceptedResponse(StrictSchema):
    message: ConversationMessageResponse
    conversation: ConversationResponse
    status_event: ConversationStatusEventResponse
    next_poll_after_ms: int = Field(ge=0, le=60_000)


class ConversationEventsResponse(StrictSchema):
    items: list[ConversationStatusEventResponse]
    page: PageMeta
    latest_sequence: int = Field(ge=0)
    recommended_poll_interval_ms: int = Field(ge=0, le=60_000)


class ConversationContextSnapshotResponse(StrictSchema):
    context_snapshot_id: str
    conversation_id: str
    snapshot_version: int
    short_summary: str
    structured_state: dict[str, object]
    last_message_id: str | None = None
    status: Literal["current", "stale", "failed"]
    created_by: str
    trace_id: str | None = None
    created_at: str
    updated_at: str


class ConversationContextPanelResponse(StrictSchema):
    short_summary: str | None = None
    scenario_binding: dict[str, object] | None = None
    key_variables: dict[str, object] = Field(default_factory=dict)
    confirmed_facts: list[object] = Field(default_factory=list)
    pending_questions: list[object] = Field(default_factory=list)
    current_candidates: list[dict[str, object]] = Field(default_factory=list)
    next_actions: list[object] = Field(default_factory=list)
    latest_reasoning_summary: str | None = None
    memory_refs: list[dict[str, object]] = Field(default_factory=list)
    summary_status: str | None = None
    snapshot_version: int | None = None
    updated_at: str | None = None


class ConversationContextResponse(StrictSchema):
    conversation_id: str
    snapshot: ConversationContextSnapshotResponse | None
    pending_delta_count: int
    panel: ConversationContextPanelResponse | None = None


class ReasoningTraceResponse(StrictSchema):
    reasoning_trace_id: str
    conversation_id: str
    source_message_id: str | None = None
    objective: str | None = None
    decision_summary: str | None = None
    comparison_dimensions: list[str] = Field(default_factory=list)
    candidates: list[dict[str, object]] = Field(default_factory=list)
    recommendation: str | None = None
    recommended_candidate_option_id: str | None = None
    pending_confirmations: list[dict[str, object]] = Field(default_factory=list)
    created_by_agent: str | None = None
    core_agent_run_id: str | None = None
    trace_id: str | None = None
    created_at: str


class ReasoningTraceListResponse(StrictSchema):
    items: list[ReasoningTraceResponse]
    page: PageMeta


class CandidateSelectionRequest(StrictSchema):
    reasoning_trace_id: str = Field(min_length=1, max_length=64)
    candidate_option_id: str = Field(min_length=1, max_length=128)
    action: Literal["confirm", "reject", "revise"]
    comment: str | None = Field(default=None, max_length=500)


class CandidateSelectionResponse(StrictSchema):
    selection_id: str
    conversation_id: str
    reasoning_trace_id: str
    candidate_option_id: str
    action: Literal["confirm", "reject", "revise"]
    comment: str | None = None
    created_by_user_id: str
    trace_id: str | None = None
    correlation_id: str | None = None
    created_at: str


class CandidateSelectionAcceptedResponse(StrictSchema):
    selection: CandidateSelectionResponse
    idempotent: bool


class ErrorCode(StrEnum):
    BAD_REQUEST = "BAD_REQUEST"
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    IDEMPOTENCY_CONFLICT = "IDEMPOTENCY_CONFLICT"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    CONVERSATION_ARCHIVED = "CONVERSATION_ARCHIVED"
    CONVERSATION_EXPIRED = "CONVERSATION_EXPIRED"
    CONVERSATION_BUSY = "CONVERSATION_BUSY"
    CONVERSATION_STATE_CONFLICT = "CONVERSATION_STATE_CONFLICT"
    CONVERSATION_WRITEBACK_STALE = "CONVERSATION_WRITEBACK_STALE"
    LEGAL_HOLD_PERMISSION_DENIED = "LEGAL_HOLD_PERMISSION_DENIED"


class VisibleError(StrictSchema):
    code: ErrorCode
    message: str
    retryable: bool = False
    details: dict[str, object] | None = None


class ErrorResponse(StrictSchema):
    error: VisibleError
    request_id: str
    trace_id: str | None = None


ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    400: {"model": ErrorResponse},
    401: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    404: {"model": ErrorResponse},
    409: {"model": ErrorResponse},
    422: {"model": ErrorResponse},
    500: {"model": ErrorResponse},
}
