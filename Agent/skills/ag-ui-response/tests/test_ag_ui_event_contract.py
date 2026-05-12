import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ag_ui_mq_core import (  # noqa: E402
    ContractValidationError,
    generate_valid_message_from_event,
    validate_message,
)


def test_generate_state_snapshot_message_contains_standard_ag_ui_event() -> None:
    message = generate_valid_message_from_event(
        event_type="STATE_SNAPSHOT",
        conversation_id="100",
        turn_id="200",
        message_id="901",
        run_id="run-100",
        sequence=1,
        state={
            "humanInTheLoop": {
                "capabilities": {
                    "confirmation": True,
                    "selection": True,
                }
            }
        },
        now_ms=1_800_000_000_000,
    )

    assert message["payload"]["ag_ui_event"] == {
        "type": "STATE_SNAPSHOT",
        "eventId": "decision-agent.ag-ui.100.1.1800000000000",
        "threadId": "100",
        "runId": "run-100",
        "sequence": 1,
        "state": {
            "humanInTheLoop": {
                "capabilities": {
                    "confirmation": True,
                    "selection": True,
                }
            }
        },
    }
    validate_message(message)


def test_validate_message_rejects_snapshot_and_rich_payload_wire_fields() -> None:
    message = generate_valid_message_from_event(
        event_type="STATE_SNAPSHOT",
        conversation_id="100",
        turn_id="200",
        message_id="901",
        run_id="run-100",
        sequence=1,
        state={
            "humanInTheLoop": {
                "capabilities": {"confirmation": True, "selection": True}
            }
        },
    )
    event = message["payload"]["ag_ui_event"]
    event["snapshot"] = {}
    event["rich_payload"] = {}

    with pytest.raises(ContractValidationError) as exc_info:
        validate_message(message)

    assert any("snapshot" in error for error in exc_info.value.errors)
    assert any("rich_payload" in error for error in exc_info.value.errors)


def test_tool_call_result_requires_approval_audit_fields() -> None:
    message = generate_valid_message_from_event(
        event_type="TOOL_CALL_RESULT",
        conversation_id="100",
        turn_id="200",
        message_id="901",
        run_id="run-100",
        sequence=1,
        result={
            "decision": "approved",
            "actorRef": "user-001",
            "occurredAt": "2026-05-12T10:00:00Z",
            "summary": "User approved the tool call",
        },
    )

    validate_message(message)


def test_state_snapshot_requires_hitl_capability_modes() -> None:
    message = generate_valid_message_from_event(
        event_type="STATE_SNAPSHOT",
        conversation_id="100",
        turn_id="200",
        message_id="901",
        run_id="run-100",
        sequence=1,
        state={
            "humanInTheLoop": {
                "capabilities": {"confirmation": True, "selection": True}
            }
        },
    )
    message["payload"]["ag_ui_event"]["state"]["humanInTheLoop"]["capabilities"].pop(
        "selection"
    )

    with pytest.raises(ContractValidationError) as exc_info:
        validate_message(message)

    assert any("HumanInTheLoopCapabilities" in error for error in exc_info.value.errors)
