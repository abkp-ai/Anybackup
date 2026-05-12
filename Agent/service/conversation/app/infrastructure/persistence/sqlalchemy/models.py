from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

JSON_DOCUMENT = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class TimestampColumnsMixin:
    f_created_time: Mapped[int] = mapped_column(BigInteger, nullable=False)
    f_updated_time: Mapped[int] = mapped_column(BigInteger, nullable=False)


class ConversationModel(TimestampColumnsMixin, Base):
    __tablename__ = "t_conversation"
    __table_args__ = (
        Index(
            "idx_t_conversation_owner_status_active",
            "f_owner_user_id",
            "f_status",
            "f_last_active_time",
        ),
        Index(
            "idx_t_conversation_retention_scan",
            "f_status",
            "f_legal_hold",
            "f_last_active_time",
        ),
    )

    f_conversation_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    f_owner_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    f_tenant_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    f_title: Mapped[str] = mapped_column(String(120), nullable=False)
    f_display_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    f_status: Mapped[str] = mapped_column(String(32), nullable=False)
    f_scenario_binding: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    f_tags: Mapped[list[str] | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    f_retention_policy: Mapped[str] = mapped_column(
        String(80),
        nullable=False,
        default="conversation_default_v1",
    )
    f_legal_hold: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    f_last_active_time: Mapped[int] = mapped_column(BigInteger, nullable=False)
    f_active_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    f_archived_time: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    f_archived_by: Mapped[str | None] = mapped_column(String(16), nullable=True)
    f_archive_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    f_expires_time: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    f_expired_time: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    f_purge_after_time: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    f_purged_time: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    f_version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)


class ConversationMessageModel(TimestampColumnsMixin, Base):
    __tablename__ = "t_conversation_message"
    __table_args__ = (
        UniqueConstraint("f_conversation_id", "f_client_message_id"),
        UniqueConstraint("f_conversation_id", "f_idempotency_key"),
        Index("idx_t_conversation_message_page", "f_conversation_id", "f_created_time"),
    )

    f_message_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    f_conversation_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    f_parent_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    f_turn_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    f_role: Mapped[str] = mapped_column(String(24), nullable=False)
    f_content_type: Mapped[str] = mapped_column(String(32), nullable=False)
    f_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    f_rich_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON_DOCUMENT, nullable=True)
    f_status: Mapped[str] = mapped_column(String(32), nullable=False)
    f_client_message_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    f_idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    f_trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    f_correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    f_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)


class ConversationStatusEventModel(TimestampColumnsMixin, Base):
    __tablename__ = "t_conversation_status_event"
    __table_args__ = (
        UniqueConstraint("f_conversation_id", "f_sequence"),
        Index("idx_t_conversation_status_event_cursor", "f_conversation_id", "f_sequence"),
    )

    f_status_event_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    f_conversation_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    f_sequence: Mapped[int] = mapped_column(BigInteger, nullable=False)
    f_event_type: Mapped[str] = mapped_column(String(80), nullable=False)
    f_event_version: Mapped[str] = mapped_column(String(16), nullable=False, default="v1")
    f_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    f_turn_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    f_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    f_visible_to_user: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    f_trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    f_correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


class ConversationMqOutboxModel(TimestampColumnsMixin, Base):
    __tablename__ = "t_conversation_mq_outbox"
    __table_args__ = (
        UniqueConstraint("f_event_id"),
        UniqueConstraint("f_idempotency_key"),
        Index("idx_t_conversation_mq_outbox_retry", "f_status", "f_next_retry_time"),
    )

    f_outbox_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    f_event_id: Mapped[str] = mapped_column(String(128), nullable=False)
    f_event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    f_routing_key: Mapped[str] = mapped_column(String(160), nullable=False)
    f_conversation_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    f_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    f_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    f_status: Mapped[str] = mapped_column(String(32), nullable=False)
    f_attempt_count: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    f_next_retry_time: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    f_last_error_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    f_trace_id: Mapped[str] = mapped_column(String(128), nullable=False)
    f_correlation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    f_idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)


class ConversationWritebackIdempotencyModel(TimestampColumnsMixin, Base):
    __tablename__ = "t_conversation_writeback_idempotency"
    __table_args__ = (
        UniqueConstraint("f_idempotency_key"),
        Index(
            "idx_t_conversation_writeback_conversation",
            "f_conversation_id",
            "f_created_time",
        ),
    )

    f_writeback_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    f_idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    f_conversation_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    f_output_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    f_request_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    f_result_status: Mapped[str] = mapped_column(String(32), nullable=False)
    f_result_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    f_reject_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    f_reject_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    f_trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    f_correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


class ConversationContextDeltaModel(TimestampColumnsMixin, Base):
    __tablename__ = "t_conversation_context_delta"
    __table_args__ = (
        Index("idx_t_conversation_context_delta_merge", "f_merge_status", "f_created_time"),
        Index(
            "idx_t_conversation_context_delta_conversation",
            "f_conversation_id",
            "f_created_time",
        ),
    )

    f_context_delta_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    f_conversation_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    f_turn_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    f_source_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    f_base_snapshot_version: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    f_delta_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    f_merge_status: Mapped[str] = mapped_column(String(32), nullable=False)
    f_created_by_agent: Mapped[str | None] = mapped_column(String(120), nullable=True)
    f_trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


class ConversationContextSnapshotModel(TimestampColumnsMixin, Base):
    __tablename__ = "t_conversation_context_snapshot"
    __table_args__ = (
        UniqueConstraint("f_conversation_id", "f_snapshot_version"),
        Index(
            "idx_t_conversation_context_snapshot_current",
            "f_conversation_id",
            "f_status",
            "f_snapshot_version",
        ),
    )

    f_context_snapshot_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    f_conversation_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    f_snapshot_version: Mapped[int] = mapped_column(BigInteger, nullable=False)
    f_short_summary: Mapped[str] = mapped_column(Text, nullable=False)
    f_structured_state: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    f_last_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    f_status: Mapped[str] = mapped_column(String(32), nullable=False)
    f_created_by: Mapped[str] = mapped_column(String(80), nullable=False)
    f_trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


class ConversationReasoningTraceModel(TimestampColumnsMixin, Base):
    __tablename__ = "t_conversation_reasoning_trace"
    __table_args__ = (
        Index(
            "idx_t_conversation_reasoning_trace_conversation",
            "f_conversation_id",
            "f_created_time",
        ),
    )

    f_reasoning_trace_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    f_conversation_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    f_source_message_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    f_trace_payload: Mapped[dict[str, Any]] = mapped_column(JSON_DOCUMENT, nullable=False)
    f_core_agent_run_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    f_created_by_agent: Mapped[str | None] = mapped_column(String(120), nullable=True)
    f_trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


class ConversationCandidateSelectionModel(TimestampColumnsMixin, Base):
    __tablename__ = "t_conversation_candidate_selection"
    __table_args__ = (
        UniqueConstraint("f_idempotency_key"),
        UniqueConstraint("f_conversation_id", "f_reasoning_trace_id", "f_candidate_option_id"),
        Index(
            "idx_t_conversation_candidate_selection_conversation",
            "f_conversation_id",
            "f_created_time",
        ),
    )

    f_selection_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    f_conversation_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    f_reasoning_trace_id: Mapped[str] = mapped_column(String(64), nullable=False)
    f_candidate_option_id: Mapped[str] = mapped_column(String(128), nullable=False)
    f_action: Mapped[str] = mapped_column(String(16), nullable=False)
    f_comment: Mapped[str | None] = mapped_column(String(500), nullable=True)
    f_idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    f_created_by_user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    f_trace_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    f_correlation_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
