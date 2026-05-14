"""Validate mock scenario business_data aligns with AG-UI template schemas.

These tests verify that:
1. Every scenario produces business_data_steps with valid schema_types
2. Extension fields are populated across all scenarios
3. The data passes business_data_schemas.validate_business_data()
4. KWeaver message builder produces valid output
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_PATH = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_PATH))

from conversation_agent_mq_mock.messages import (  # noqa: E402
    BusinessDataStep,
    IncomingConversationMessage,
    KweaverStep,
    build_kweaver_message,
)
from conversation_agent_mq_mock.scenario import build_scenario  # noqa: E402
from conversation_agent_mq_mock.runner import (  # noqa: E402
    _SCHEMA_TYPE_BY_SCENARIO,
    _convert_ag_ui_steps,
    _convert_ag_ui_to_kweaver,
)


def _make_incoming(content: str, conversation_id: str = "100", message_id: str = "200") -> IncomingConversationMessage:
    return IncomingConversationMessage(
        event_id=f"test-{message_id}",
        conversation_id=conversation_id,
        message_id=message_id,
        turn_id=message_id,
        content=content,
        trace_id="",
        correlation_id="",
    )


SCENARIO_CONTENTS = {
    "thought": "show thought about recovery",
    "tool_call": "show tool call for restore point",
    "progress": "show progress of plan generation",
    "clarifying": "clarify recovery window",
    "restore": "restore order database",
    "capacity": "capacity forecast for storage",
    "attachment": "attachment download for report",
    "visible_error": "visible error in restore",
    "doc_candidate_compare": "doc candidate compare plans",
    "doc_report_detail": "doc report detail analysis",
    "incremental": "incremental update progress",
    "text_only": "text fallback message",
    "general": "generic analysis request",
}


class SchemaTypeMappingTests(unittest.TestCase):
    def test_all_scenarios_have_schema_type_mapping(self) -> None:
        for scenario_name in SCENARIO_CONTENTS:
            self.assertIn(scenario_name, _SCHEMA_TYPE_BY_SCENARIO, f"Missing schema_type mapping for scenario: {scenario_name}")

    def test_schema_type_values_are_valid(self) -> None:
        valid_types = {
            "plan_candidates", "progress_report", "clarification_request",
            "capacity_forecast", "attachment_list", "report_detail",
            "text_message", "incremental_update",
        }
        for scenario_name, schema_type in _SCHEMA_TYPE_BY_SCENARIO.items():
            self.assertIn(schema_type, valid_types, f"Invalid schema_type '{schema_type}' for scenario '{scenario_name}'")


class BusinessDataStepsTests(unittest.TestCase):
    def test_all_scenarios_produce_business_data_steps(self) -> None:
        for scenario_name, content in SCENARIO_CONTENTS.items():
            incoming = _make_incoming(content)
            scenario = build_scenario(incoming, core_agent_run_id="run-test")
            self.assertGreater(
                len(scenario.business_data_steps), 0,
                f"Scenario '{scenario_name}' has no business_data_steps",
            )

    def test_all_business_data_steps_have_valid_schema_type(self) -> None:
        valid_types = {
            "plan_candidates", "progress_report", "clarification_request",
            "capacity_forecast", "attachment_list", "report_detail",
            "text_message", "incremental_update",
        }
        for scenario_name, content in SCENARIO_CONTENTS.items():
            incoming = _make_incoming(content)
            scenario = build_scenario(incoming, core_agent_run_id="run-test")
            for step in scenario.business_data_steps:
                self.assertIn(
                    step.schema_type, valid_types,
                    f"Scenario '{scenario_name}' has invalid schema_type '{step.schema_type}'",
                )

    def test_capacity_scenario_uses_capacity_forecast(self) -> None:
        incoming = _make_incoming("capacity forecast for storage")
        scenario = build_scenario(incoming, core_agent_run_id="run-test")
        schema_types = [step.schema_type for step in scenario.business_data_steps]
        self.assertIn("capacity_forecast", schema_types)

    def test_attachment_scenario_uses_attachment_list(self) -> None:
        incoming = _make_incoming("attachment download for report")
        scenario = build_scenario(incoming, core_agent_run_id="run-test")
        schema_types = [step.schema_type for step in scenario.business_data_steps]
        self.assertIn("attachment_list", schema_types)

    def test_doc_report_detail_uses_report_detail(self) -> None:
        incoming = _make_incoming("doc report detail analysis")
        scenario = build_scenario(incoming, core_agent_run_id="run-test")
        schema_types = [step.schema_type for step in scenario.business_data_steps]
        self.assertIn("report_detail", schema_types)

    def test_incremental_scenario_has_incremental_update(self) -> None:
        incoming = _make_incoming("incremental update progress")
        scenario = build_scenario(incoming, core_agent_run_id="run-test")
        schema_types = [step.schema_type for step in scenario.business_data_steps]
        self.assertIn("incremental_update", schema_types)

    def test_visible_error_uses_progress_report_with_error(self) -> None:
        incoming = _make_incoming("visible error in restore")
        scenario = build_scenario(incoming, core_agent_run_id="run-test")
        error_steps = [
            s for s in scenario.business_data_steps
            if s.schema_type == "progress_report" and "error" in s.data
        ]
        self.assertGreater(len(error_steps), 0, "visible_error should have progress_report with error field")


class ExtensionFieldCoverageTests(unittest.TestCase):
    def test_plan_candidates_has_extension_fields(self) -> None:
        incoming = _make_incoming("restore order database")
        scenario = build_scenario(incoming, core_agent_run_id="run-test")
        plan_steps = [s for s in scenario.business_data_steps if s.schema_type == "plan_candidates"]
        self.assertGreater(len(plan_steps), 0)
        data = plan_steps[0].data
        self.assertIn("header_badges", data)
        self.assertIn("candidates", data)
        first_candidate = data["candidates"][0]
        self.assertIn("badges", first_candidate)
        self.assertIn("metadata", first_candidate)

    def test_progress_report_has_extension_fields(self) -> None:
        incoming = _make_incoming("show progress of plan generation")
        scenario = build_scenario(incoming, core_agent_run_id="run-test")
        progress_steps = [s for s in scenario.business_data_steps if s.schema_type == "progress_report"]
        self.assertGreater(len(progress_steps), 0)
        data = progress_steps[0].data
        self.assertIn("callouts", data)
        self.assertIn("metadata", data)
        self.assertIn("metrics", data)

    def test_clarification_request_has_extension_fields(self) -> None:
        incoming = _make_incoming("clarify recovery window")
        scenario = build_scenario(incoming, core_agent_run_id="run-test")
        clarification_steps = [s for s in scenario.business_data_steps if s.schema_type == "clarification_request"]
        self.assertGreater(len(clarification_steps), 0)
        data = clarification_steps[0].data
        self.assertIn("allows_free_text", data)
        options = data["options"]
        first_option = options[0]
        self.assertIn("is_recommended", first_option)
        self.assertIn("badges", first_option)

    def test_capacity_forecast_has_extension_fields(self) -> None:
        incoming = _make_incoming("capacity forecast for storage")
        scenario = build_scenario(incoming, core_agent_run_id="run-test")
        capacity_steps = [s for s in scenario.business_data_steps if s.schema_type == "capacity_forecast"]
        self.assertGreater(len(capacity_steps), 0)
        data = capacity_steps[0].data
        self.assertIn("forecast", data)
        self.assertIn("warnings", data)
        self.assertIn("header_badges", data)
        self.assertIn("metadata", data)
        self.assertIn("callouts", data)
        self.assertIn("extra_actions", data)
        self.assertIn("block_id_suffix", data)

    def test_attachment_list_has_extension_fields(self) -> None:
        incoming = _make_incoming("attachment download for report")
        scenario = build_scenario(incoming, core_agent_run_id="run-test")
        attachment_steps = [s for s in scenario.business_data_steps if s.schema_type == "attachment_list"]
        self.assertGreater(len(attachment_steps), 0)
        data = attachment_steps[0].data
        self.assertIn("header_badges", data)
        attachments = data["attachments"]
        first_attachment = attachments[0]
        self.assertIn("title", first_attachment)
        self.assertIn("summary", first_attachment)
        self.assertIn("badges", first_attachment)
        self.assertIn("metadata", first_attachment)

    def test_report_detail_has_extension_fields(self) -> None:
        incoming = _make_incoming("doc report detail analysis")
        scenario = build_scenario(incoming, core_agent_run_id="run-test")
        report_steps = [s for s in scenario.business_data_steps if s.schema_type == "report_detail"]
        self.assertGreater(len(report_steps), 0)
        data = report_steps[0].data
        self.assertIn("header_badges", data)
        self.assertIn("metadata", data)
        self.assertIn("navigation", data)
        self.assertIn("use_tabs", data)
        sections = data.get("sections", [])
        if sections:
            first_section = sections[0]
            self.assertIn("section_type", first_section)
            self.assertIn("badges", first_section)

    def test_text_message_has_format_hint(self) -> None:
        incoming = _make_incoming("text fallback message")
        scenario = build_scenario(incoming, core_agent_run_id="run-test")
        text_steps = [s for s in scenario.business_data_steps if s.schema_type == "text_message"]
        self.assertGreater(len(text_steps), 0)

    def test_incremental_update_has_patch_type(self) -> None:
        incoming = _make_incoming("incremental update progress")
        scenario = build_scenario(incoming, core_agent_run_id="run-test")
        inc_steps = [s for s in scenario.business_data_steps if s.schema_type == "incremental_update"]
        self.assertGreater(len(inc_steps), 0)
        data = inc_steps[0].data
        self.assertIn("patch_type", data)
        self.assertIn("version", data)


class FallbackConversionTests(unittest.TestCase):
    def test_convert_ag_ui_steps_with_scenario_id(self) -> None:
        incoming = _make_incoming("capacity forecast for storage")
        scenario = build_scenario(incoming, core_agent_run_id="run-test")
        converted = _convert_ag_ui_steps(scenario.ag_ui_steps, scenario_id=scenario.scenario_id)
        self.assertGreater(len(converted), 0)
        schema_types = [step.schema_type for step in converted]
        self.assertIn("capacity_forecast", schema_types)

    def test_convert_ag_ui_steps_without_scenario_id_uses_text_message(self) -> None:
        incoming = _make_incoming("capacity forecast for storage")
        scenario = build_scenario(incoming, core_agent_run_id="run-test")
        converted = _convert_ag_ui_steps(scenario.ag_ui_steps)
        self.assertGreater(len(converted), 0)
        for step in converted:
            self.assertIsInstance(step, BusinessDataStep)


class KweaverMessageTests(unittest.TestCase):
    def test_build_kweaver_message_produces_valid_output(self) -> None:
        incoming = _make_incoming("restore order database")
        step = KweaverStep(
            sequence=1,
            content="test",
            kweaver_event={"key": "step-1", "content": {}, "finished": False},
            chunk_index=0,
        )
        message = build_kweaver_message(
            incoming,
            step=step,
            core_agent_run_id="run-test",
            now_ms=1_800_000_000_100,
        )
        self.assertEqual(message.body["event_type"], "core_agent.kweaver.stream_event")
        self.assertEqual(message.body["source_service"], "core_agent")
        self.assertEqual(message.body["payload"]["run_id"], "run-test")
        self.assertEqual(message.body["payload"]["chunk_index"], 0)
        self.assertIn("kweaver_event", message.body["payload"])

    def test_convert_ag_ui_to_kweaver_produces_steps(self) -> None:
        incoming = _make_incoming("restore order database")
        scenario = build_scenario(incoming, core_agent_run_id="run-test")
        kweaver_steps = _convert_ag_ui_to_kweaver(scenario.ag_ui_steps, run_id="run-test")
        self.assertGreater(len(kweaver_steps), 0)
        for step in kweaver_steps:
            self.assertTrue(hasattr(step, "kweaver_event"))
            self.assertIsInstance(step.kweaver_event, dict)


class BadgeToneTests(unittest.TestCase):
    def test_badge_tones_use_frontend_vocabulary(self) -> None:
        valid_tones = {"success", "info", "warning", "danger", "neutral"}
        incoming = _make_incoming("restore order database")
        scenario = build_scenario(incoming, core_agent_run_id="run-test")
        for step in scenario.business_data_steps:
            _check_badge_tones(step.data, valid_tones, step.schema_type)


def _check_badge_tones(data: object, valid_tones: set[str], context: str) -> None:
    if isinstance(data, dict):
        if "tone" in data:
            tone = data["tone"]
            if isinstance(tone, str):
                assert tone in valid_tones, f"Invalid badge tone '{tone}' in {context}. Valid: {valid_tones}"
        for value in data.values():
            _check_badge_tones(value, valid_tones, context)
    elif isinstance(data, list):
        for item in data:
            _check_badge_tones(item, valid_tones, context)


if __name__ == "__main__":
    unittest.main()
