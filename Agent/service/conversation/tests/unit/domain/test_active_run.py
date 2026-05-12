import pytest

from app.domain.conversation import Conversation, ConversationStatus
from app.domain.shared.errors import DomainError, ErrorReason


def test_active_run_blocks_new_user_messages() -> None:
    conversation = Conversation(
        conversation_id=1,
        status=ConversationStatus.ACTIVE,
        active_run_id="run-1",
    )

    with pytest.raises(DomainError) as exc_info:
        conversation.ensure_user_message_allowed()

    assert exc_info.value.reason is ErrorReason.CONVERSATION_BUSY


def test_no_active_run_allows_user_messages() -> None:
    conversation = Conversation(
        conversation_id=1,
        status=ConversationStatus.ACTIVE,
        active_run_id=None,
    )

    conversation.ensure_user_message_allowed()
