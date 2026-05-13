import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ag_ui_mq_core import (  # noqa: E402
    ContractValidationError,
    generate_valid_message_from_business_data,
    validate_business_data_message,
    DEFAULT_BUSINESS_DATA_MESSAGE_TYPE,
    ALLOWED_SCHEMA_TYPES,
)


def test_generate_plan_candidates_business_data() -> None:
    message = generate_valid_message_from_business_data(
        schema_type="plan_candidates",
        data={
            "heading": "恢复候选方案",
            "candidates": [
                {
                    "candidate_option_id": "a",
                    "title": "方案A",
                    "summary": "推荐方案",
                    "recommendation_level": "recommended",
                    "risk_level": "medium",
                }
            ],
        },
        conversation_id="100",
        turn_id="200",
        message_id="901",
        sequence=1,
        content="恢复候选方案",
        now_ms=1_800_000_000_000,
    )
    assert message["event_type"] == DEFAULT_BUSINESS_DATA_MESSAGE_TYPE
    assert message["payload"]["business_data"]["schema_type"] == "plan_candidates"
    assert message["payload"]["business_data"]["schema_version"] == "1"
    assert message["payload"]["business_data"]["data"]["heading"] == "恢复候选方案"
    assert message["payload"]["content"] == "恢复候选方案"


def test_generate_text_message_business_data() -> None:
    message = generate_valid_message_from_business_data(
        schema_type="text_message",
        data={"text": "操作完成"},
        conversation_id="100",
        turn_id="200",
        message_id="901",
        sequence=1,
        now_ms=1_800_000_000_000,
    )
    assert message["payload"]["business_data"]["schema_type"] == "text_message"
    assert message["payload"]["content"] != ""


def test_generate_derives_content_from_heading() -> None:
    message = generate_valid_message_from_business_data(
        schema_type="progress_report",
        data={
            "heading": "恢复进度",
            "stage": "processing",
            "steps": [{"step_id": "1", "label": "连接", "status": "completed"}],
        },
        conversation_id="100",
        turn_id="200",
        message_id="901",
        sequence=1,
        now_ms=1_800_000_000_000,
    )
    assert message["payload"]["content"] == "恢复进度"


def test_validate_business_data_message_accepts_valid() -> None:
    message = {
        "event_id": "test-001",
        "event_type": DEFAULT_BUSINESS_DATA_MESSAGE_TYPE,
        "occurred_at": "2026-05-13T10:00:00Z",
        "source_service": "decision_agent_session",
        "payload": {
            "conversation_id": "100",
            "turn_id": "200",
            "message_id": "901",
            "content": "恢复候选方案",
            "sequence": 1,
            "business_data": {
                "schema_type": "plan_candidates",
                "schema_version": "1",
                "data": {"heading": "恢复候选方案", "candidates": [{"candidate_option_id": "a", "title": "A", "summary": "s", "risk_level": "medium"}]},
            },
        },
    }
    validated = validate_business_data_message(message)
    assert validated["payload"]["business_data"]["schema_type"] == "plan_candidates"


def test_validate_rejects_wrong_event_type() -> None:
    message = {
        "event_id": "test-002",
        "event_type": "decision_agent.session.ag_ui_event",
        "occurred_at": "2026-05-13T10:00:00Z",
        "source_service": "decision_agent_session",
        "payload": {
            "conversation_id": "100",
            "turn_id": "200",
            "message_id": "901",
            "content": "text",
            "sequence": 1,
            "business_data": {
                "schema_type": "text_message",
                "schema_version": "1",
                "data": {"text": "hello"},
            },
        },
    }
    with pytest.raises(ContractValidationError, match="event_type"):
        validate_business_data_message(message)


def test_validate_rejects_unknown_schema_type() -> None:
    message = {
        "event_id": "test-003",
        "event_type": DEFAULT_BUSINESS_DATA_MESSAGE_TYPE,
        "occurred_at": "2026-05-13T10:00:00Z",
        "source_service": "decision_agent_session",
        "payload": {
            "conversation_id": "100",
            "turn_id": "200",
            "message_id": "901",
            "content": "text",
            "sequence": 1,
            "business_data": {
                "schema_type": "tool_call_summary",
                "schema_version": "1",
                "data": {},
            },
        },
    }
    with pytest.raises(ContractValidationError, match="schema_type"):
        validate_business_data_message(message)


def test_validate_rejects_missing_content() -> None:
    message = {
        "event_id": "test-004",
        "event_type": DEFAULT_BUSINESS_DATA_MESSAGE_TYPE,
        "occurred_at": "2026-05-13T10:00:00Z",
        "source_service": "decision_agent_session",
        "payload": {
            "conversation_id": "100",
            "turn_id": "200",
            "message_id": "901",
            "sequence": 1,
            "business_data": {
                "schema_type": "text_message",
                "schema_version": "1",
                "data": {"text": "hello"},
            },
        },
    }
    with pytest.raises(ContractValidationError, match="content"):
        validate_business_data_message(message)


def test_allowed_schema_types_excludes_kweaver_types() -> None:
    assert "tool_call_summary" not in ALLOWED_SCHEMA_TYPES
    assert "thought_summary" not in ALLOWED_SCHEMA_TYPES
    assert "error_report" not in ALLOWED_SCHEMA_TYPES


def test_allowed_schema_types_has_8_entries() -> None:
    assert len(ALLOWED_SCHEMA_TYPES) == 8
