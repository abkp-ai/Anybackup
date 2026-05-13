from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_PATH = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_PATH))

from conversation_agent_mq_mock.messages import (  # noqa: E402
    BusinessDataStep,
    IncomingConversationMessage,
    build_business_data_message,
)
from conversation_agent_mq_mock.runner import _convert_ag_ui_steps  # noqa: E402
from conversation_agent_mq_mock.scenario import build_scenario  # noqa: E402


class BusinessDataMessageTests(unittest.TestCase):
    def test_build_business_data_message_uses_correct_event_type(self) -> None:
        incoming = IncomingConversationMessage(
            event_id="conversation.message.created.200",
            conversation_id="100",
            message_id="200",
            turn_id="200",
            content="restore order database",
            trace_id="trace-001",
            correlation_id="corr-001",
        )
        step = BusinessDataStep(
            sequence=1,
            content="恢复候选方案",
            schema_type="plan_candidates",
            data={
                "heading": "恢复候选方案",
                "candidates": [
                    {
                        "candidate_option_id": "a",
                        "title": "方案A",
                        "summary": "推荐",
                        "recommendation_level": "recommended",
                        "risk_level": "medium",
                    }
                ],
            },
        )
        message = build_business_data_message(incoming, step=step, now_ms=1_800_000_000_100)

        self.assertEqual(message.body["event_type"], "decision_agent.session.business_data")
        self.assertEqual(message.body["source_service"], "decision_agent_session")
        self.assertEqual(message.routing_key, "decision_agent.session.business_data.v1")
        self.assertEqual(message.body["payload"]["business_data"]["schema_type"], "plan_candidates")
        self.assertEqual(message.body["payload"]["business_data"]["schema_version"], "1")
        self.assertEqual(message.body["payload"]["content"], "恢复候选方案")

    def test_build_business_data_message_contains_all_required_fields(self) -> None:
        incoming = IncomingConversationMessage(
            event_id="conversation.message.created.200",
            conversation_id="100",
            message_id="200",
            turn_id="200",
            content="show progress",
            trace_id="",
            correlation_id="",
        )
        step = BusinessDataStep(
            sequence=1,
            content="恢复进度",
            schema_type="progress_report",
            data={
                "heading": "恢复进度",
                "stage": "processing",
                "steps": [{"step_id": "1", "label": "连接", "status": "running"}],
            },
        )
        message = build_business_data_message(incoming, step=step, now_ms=1_800_000_000_100)

        payload = message.body["payload"]
        self.assertIn("conversation_id", payload)
        self.assertIn("turn_id", payload)
        self.assertIn("message_id", payload)
        self.assertIn("sequence", payload)
        self.assertIn("content", payload)
        self.assertIn("business_data", payload)

    def test_scenario_plan_has_business_data_steps_field(self) -> None:
        incoming = IncomingConversationMessage(
            event_id="test-001",
            conversation_id="100",
            message_id="200",
            turn_id="200",
            content="restore order database",
            trace_id="",
            correlation_id="",
        )
        scenario = build_scenario(incoming, core_agent_run_id="run-001")
        self.assertTrue(hasattr(scenario, "business_data_steps"))

    def test_convert_ag_ui_steps_produces_business_data_steps(self) -> None:
        incoming = IncomingConversationMessage(
            event_id="test-001",
            conversation_id="100",
            message_id="200",
            turn_id="200",
            content="restore order database",
            trace_id="",
            correlation_id="",
        )
        scenario = build_scenario(incoming, core_agent_run_id="run-001")
        if scenario.business_data_steps:
            converted = scenario.business_data_steps
        else:
            converted = _convert_ag_ui_steps(scenario.ag_ui_steps)

        self.assertGreater(len(converted), 0)
        for step in converted:
            self.assertIsInstance(step, BusinessDataStep)
            self.assertIsInstance(step.schema_type, str)
            self.assertIsInstance(step.data, dict)
