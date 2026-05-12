import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from time import time

from app.application.models.conversation import AuthenticatedUser, ConversationRecord
from app.application.ports.unit_of_work import UnitOfWork
from app.application.use_cases.access import ensure_conversation_owner
from app.domain.conversation import ConversationStatus
from app.domain.shared.errors import DomainError, ErrorReason

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class StartAgUiRunCommand:
    thread_id: str
    run_id: str


@dataclass(frozen=True, slots=True)
class StartAgUiRunResult:
    conversation: ConversationRecord


class StartAgUiRunHandler:
    def __init__(
        self,
        *,
        unit_of_work_factory: Callable[[], UnitOfWork],
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    async def handle(
        self,
        command: StartAgUiRunCommand,
        user: AuthenticatedUser,
    ) -> StartAgUiRunResult:
        conversation_id = _parse_conversation_id(command.thread_id)
        async with self._unit_of_work_factory() as unit_of_work:
            conversation = await unit_of_work.conversations.get_record_by_id(conversation_id)
            if conversation is None:
                raise DomainError(ErrorReason.CONVERSATION_NOT_FOUND)
            ensure_conversation_owner(conversation, user)
            if conversation.status is ConversationStatus.ARCHIVED:
                raise DomainError(ErrorReason.CONVERSATION_ARCHIVED)
            if conversation.status is ConversationStatus.EXPIRED:
                raise DomainError(ErrorReason.CONVERSATION_EXPIRED)
            if (
                conversation.active_run_id is not None
                and conversation.active_run_id != command.run_id
            ):
                raise DomainError(ErrorReason.CONVERSATION_BUSY)

            now_ms = _current_time_ms()
            updated = replace(
                conversation,
                active_run_id=command.run_id,
                updated_time=now_ms,
                last_active_time=now_ms,
            )
            if updated != conversation:
                await unit_of_work.conversations.update_record(updated)
            await unit_of_work.commit()
            logger.info(
                "ag_ui_run_started",
                extra={"conversation_id": conversation_id, "run_id": command.run_id},
            )
            return StartAgUiRunResult(conversation=updated)


def _parse_conversation_id(raw_value: str) -> int:
    try:
        return int(raw_value)
    except ValueError as exc:
        raise DomainError(ErrorReason.CONVERSATION_NOT_FOUND) from exc


def _current_time_ms() -> int:
    return int(time() * 1000)
