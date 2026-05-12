from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.domain.shared.errors import DomainError, ErrorReason


class ConversationStatus(StrEnum):
    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"
    EXPIRED = "expired"


ALLOWED_STATUS_TRANSITIONS: frozenset[tuple[ConversationStatus, ConversationStatus]] = frozenset(
    {
        (ConversationStatus.CREATED, ConversationStatus.ACTIVE),
        (ConversationStatus.ACTIVE, ConversationStatus.PAUSED),
        (ConversationStatus.PAUSED, ConversationStatus.ACTIVE),
        (ConversationStatus.ACTIVE, ConversationStatus.ARCHIVED),
        (ConversationStatus.ARCHIVED, ConversationStatus.ACTIVE),
        (ConversationStatus.ARCHIVED, ConversationStatus.EXPIRED),
    }
)


@dataclass(slots=True)
class Conversation:
    conversation_id: int
    status: ConversationStatus
    owner_user_id: str = ""
    title: str = ""
    summary: str | None = None
    scenario_binding: dict[str, Any] | None = None
    tags: tuple[str, ...] = field(default_factory=tuple)
    latest_message_summary: str | None = None
    retention_policy: str = "conversation_default_v1"
    legal_hold: bool = False
    last_active_time: int = 0
    active_run_id: str | None = None
    archived_time: int | None = None
    archived_by: str | None = None
    archive_reason: str | None = None
    expires_time: int | None = None
    expired_time: int | None = None
    created_time: int = 0
    updated_time: int = 0

    def transition_to(self, target: ConversationStatus) -> None:
        if (self.status, target) not in ALLOWED_STATUS_TRANSITIONS:
            raise DomainError(ErrorReason.INVALID_STATUS_TRANSITION)
        self.status = target

    def ensure_user_message_allowed(self) -> None:
        if self.status is ConversationStatus.ARCHIVED:
            raise DomainError(ErrorReason.CONVERSATION_ARCHIVED)
        if self.status is ConversationStatus.EXPIRED:
            raise DomainError(ErrorReason.CONVERSATION_EXPIRED)
        if self.active_run_id is not None:
            raise DomainError(ErrorReason.CONVERSATION_BUSY)

    def ensure_agent_visible_content_allowed(self) -> None:
        if self.status is ConversationStatus.ARCHIVED:
            raise DomainError(ErrorReason.CONVERSATION_ARCHIVED)
        if self.status is ConversationStatus.EXPIRED:
            raise DomainError(ErrorReason.CONVERSATION_EXPIRED)

    def ensure_metadata_update_allowed(self) -> None:
        if self.status is ConversationStatus.ARCHIVED:
            raise DomainError(ErrorReason.CONVERSATION_ARCHIVED)
        if self.status is ConversationStatus.EXPIRED:
            raise DomainError(ErrorReason.CONVERSATION_EXPIRED)

    def ensure_child_belongs(self, child_conversation_id: int) -> None:
        if child_conversation_id != self.conversation_id:
            raise DomainError(ErrorReason.CHILD_CONVERSATION_MISMATCH)
