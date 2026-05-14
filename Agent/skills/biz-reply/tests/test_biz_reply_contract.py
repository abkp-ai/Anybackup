import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from bizdata_mq_core import (  # noqa: E402
    ContractValidationError,
    generate_bizdata_message,
    generate_bizdata_message_from_markdown,
    validate_bizdata_message,
    validate_markdown_text,
    DEFAULT_BIZDATA_MESSAGE_TYPE,
    DEFAULT_EXCHANGE,
    DEFAULT_ROUTING_KEY,
    ALLOWED_SCHEMA_TYPES,
)


def test_generate_clarification_request() -> None:
    message = generate_bizdata_message(
        schema_type="clarification_request",
        data={
            "question": "请选择需要恢复的数据库实例",
            "options": [
                {"option_id": "a", "label": "MySQL 实例 A", "description": "生产环境"},
                {"option_id": "b", "label": "MySQL 实例 B", "description": "测试环境"},
            ],
        },
        conversation_id="100",
        turn_id="200",
        message_id="901",
        sequence=1,
        content="请选择需要恢复的数据库实例",
        now_ms=1_800_000_000_000,
    )
    assert message["event_type"] == DEFAULT_BIZDATA_MESSAGE_TYPE
    assert message["payload"]["business_data"]["schema_type"] == "clarification_request"
    assert message["payload"]["business_data"]["data"]["question"] == "请选择需要恢复的数据库实例"
    assert len(message["payload"]["business_data"]["data"]["options"]) == 2


def test_generate_progress_report() -> None:
    message = generate_bizdata_message(
        schema_type="progress_report",
        data={
            "heading": "恢复执行进度",
            "stage": "executing",
            "steps": [
                {"step_id": "1", "label": "连接目标", "status": "completed"},
                {"step_id": "2", "label": "数据传输", "status": "in_progress"},
                {"step_id": "3", "label": "校验数据", "status": "pending"},
            ],
        },
        conversation_id="100",
        turn_id="200",
        message_id="901",
        sequence=1,
        now_ms=1_800_000_000_000,
    )
    assert message["payload"]["business_data"]["schema_type"] == "progress_report"
    assert message["payload"]["content"] == "恢复执行进度"


def test_generate_incremental_update() -> None:
    message = generate_bizdata_message(
        schema_type="incremental_update",
        data={
            "target_block_id": "step-status",
            "patch": [{"op": "replace", "path": "/status", "value": "completed"}],
        },
        conversation_id="100",
        turn_id="200",
        message_id="901",
        sequence=2,
        content="步骤已完成",
        now_ms=1_800_000_000_000,
    )
    assert message["payload"]["business_data"]["schema_type"] == "incremental_update"


def test_generate_from_markdown_creates_business_data() -> None:
    message = generate_bizdata_message_from_markdown(
        markdown="# 恢复完成\n\n目标 MySQL 实例已成功恢复至最近可用时间点。",
        conversation_id="100",
        turn_id="200",
        sequence=1,
        now_ms=1_800_000_000_000,
    )
    assert message["event_type"] == DEFAULT_BIZDATA_MESSAGE_TYPE
    assert "business_data" in message["payload"]
    assert message["payload"]["business_data"]["schema_type"] == "text_message"
    assert message["payload"]["business_data"]["schema_version"] == "1"
    assert message["payload"]["content"] != ""


def test_generate_from_markdown_rejects_sensitive_content() -> None:
    with pytest.raises(ContractValidationError, match="sensitive"):
        generate_bizdata_message_from_markdown(
            markdown="连接串: postgresql://admin:password=@host:5432/db",
            conversation_id="100",
            turn_id="200",
            sequence=1,
        )


def test_validate_rejects_invalid_schema_version() -> None:
    message = {
        "event_id": "test-005",
        "event_type": DEFAULT_BIZDATA_MESSAGE_TYPE,
        "occurred_at": "2026-05-13T10:00:00Z",
        "source_service": "decision_agent_session",
        "payload": {
            "conversation_id": "100",
            "turn_id": "200",
            "message_id": "901",
            "content": "test",
            "sequence": 1,
            "business_data": {
                "schema_type": "text_message",
                "schema_version": "2",
                "data": {"text": "hello"},
            },
        },
    }
    with pytest.raises(ContractValidationError, match="schema_version"):
        validate_bizdata_message(message)


def test_validate_rejects_data_not_dict() -> None:
    message = {
        "event_id": "test-006",
        "event_type": DEFAULT_BIZDATA_MESSAGE_TYPE,
        "occurred_at": "2026-05-13T10:00:00Z",
        "source_service": "decision_agent_session",
        "payload": {
            "conversation_id": "100",
            "turn_id": "200",
            "message_id": "901",
            "content": "test",
            "sequence": 1,
            "business_data": {
                "schema_type": "text_message",
                "schema_version": "1",
                "data": "not a dict",
            },
        },
    }
    with pytest.raises(ContractValidationError, match="data"):
        validate_bizdata_message(message)


def test_default_exchange_and_routing_key() -> None:
    assert DEFAULT_EXCHANGE == "decision_agent.bizdata.events"
    assert DEFAULT_ROUTING_KEY == "decision_agent.session.business_data.v1"


def test_all_8_schema_types_are_valid() -> None:
    expected = {
        "plan_candidates",
        "progress_report",
        "clarification_request",
        "capacity_forecast",
        "attachment_list",
        "report_detail",
        "text_message",
        "incremental_update",
    }
    assert ALLOWED_SCHEMA_TYPES == expected
