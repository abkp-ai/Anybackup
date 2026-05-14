from __future__ import annotations

import sys
import unittest
from pathlib import Path

SRC_PATH = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC_PATH))

from conversation_agent_mq_mock.messages import (  # noqa: E402
    IncomingConversationMessage,
    build_ag_ui_message,
    build_core_status_message,
)
from conversation_agent_mq_mock.runner import AgentMqMockRunner  # noqa: E402
from conversation_agent_mq_mock.scenario import build_scenario, should_fail  # noqa: E402
from conversation_agent_mq_mock.settings import Settings  # noqa: E402
from conversation_agent_mq_mock.state import SessionTracker  # noqa: E402


class MockMessageTests(unittest.TestCase):
    def test_core_accepted_message_matches_current_consumer_contract(self) -> None:
        incoming = IncomingConversationMessage(
            event_id="conversation.message.created.200",
            conversation_id="100",
            message_id="200",
            turn_id="200",
            content="restore order database to last Friday",
            trace_id="trace-001",
            correlation_id="corr-001",
        )

        message = build_core_status_message(
            incoming,
            kind="accepted",
            core_agent_run_id="run-100-200",
            now_ms=1_800_000_000_100,
        )

        self.assertEqual(message.routing_key, "conversation.core_agent.run_status")
        self.assertEqual(message.body["event_type"], "core_agent.run.accepted")
        self.assertEqual(message.body["event_version"], "v1")
        self.assertEqual(message.body["trace_id"], "trace-001")
        self.assertEqual(message.body["correlation_id"], "corr-001")
        self.assertEqual(message.body["occurred_at"], "2027-01-15T08:00:00.100000Z")
        self.assertEqual(
            message.body["payload"],
            {
                "conversation_id": "100",
                "message_id": "200",
                "turn_id": "200",
                "content": "restore order database to last Friday",
                "accepted": {
                    "input_event_id": "conversation.message.created.200",
                    "core_agent_run_id": "run-100-200",
                    "estimated_status": "processing",
                },
            },
        )

    def test_ag_ui_message_matches_formal_mq_contract(self) -> None:
        incoming = IncomingConversationMessage(
            event_id="conversation.message.created.201",
            conversation_id="101",
            message_id="201",
            turn_id="201",
            content="show thought summary",
            trace_id="trace-002",
            correlation_id="corr-002",
        )
        step = build_scenario(incoming, core_agent_run_id="run-101-201").ag_ui_steps[0]

        message = build_ag_ui_message(incoming, step=step, now_ms=1_800_000_001_000)

        self.assertEqual(message.exchange, "decision_agent.bizdata.events")
        self.assertEqual(message.routing_key, "decision_agent.session.business_data.v1")
        self.assertEqual(message.body["event_type"], "decision_agent.session.business_data")
        self.assertEqual(message.body["source_service"], "decision_agent_session")
        self.assertEqual(message.body["payload"]["conversation_id"], "101")
        self.assertEqual(message.body["payload"]["sequence"], 1)
        self.assertEqual(message.body["trace_id"], "trace-002")
        self.assertEqual(message.body["correlation_id"], "corr-002")
        self.assertEqual(message.body["payload"]["turn_id"], "201")
        self.assertEqual(message.body["payload"]["message_id"], "10201")
        self.assertIsInstance(message.body["payload"]["ag_ui"], str)
        self.assertIn("Collected the request intent", message.body["payload"]["ag_ui"])
        self.assertIn("Visible reasoning summary", message.body["payload"]["ag_ui"])

    def test_input_body_requires_explicit_turn_id(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "conversation message requires conversation_id, message_id, turn_id, content",
        ):
            IncomingConversationMessage.from_body(
                {
                    "event_id": "conversation.message.created.200",
                    "event_type": "conversation.message.created",
                    "payload": {
                        "conversation_id": "100",
                        "message_id": "200",
                        "content": "visible error panel",
                    },
                }
            )

    def test_restore_scenario_emits_reasoning_trace_metadata_and_completed_state(self) -> None:
        scenario = build_scenario(
            IncomingConversationMessage(
                event_id="conversation.message.created.701",
                conversation_id="501",
                message_id="701",
                turn_id="701",
                content="restore order database",
                trace_id="trace-restore",
                correlation_id="corr-restore",
            ),
            core_agent_run_id="run-501-701",
        )

        self.assertEqual(scenario.scenario_id, "restore")
        result_step = scenario.ag_ui_steps[-1]
        activity = next(
            event for event in result_step.events if event["type"] == "ACTIVITY_SNAPSHOT"
        )
        state = next(event for event in result_step.events if event["type"] == "STATE_SNAPSHOT")

        self.assertEqual(activity["content"]["meta"]["intent"], "result")
        self.assertTrue(activity["content"]["meta"]["terminal"])
        self.assertTrue(activity["content"]["meta"]["reasoningTraceId"])
        self.assertEqual(
            activity["content"]["meta"]["reasoningTrace"]["recommended_candidate_option_id"],
            activity["content"]["meta"]["reasoningTrace"]["candidates"][0]["candidate_option_id"],
        )
        self.assertEqual(state["snapshot"]["interaction"]["status"], "completed")

    def test_clarifying_scenario_emits_question_payload(self) -> None:
        scenario = build_scenario(
            IncomingConversationMessage(
                event_id="conversation.message.created.801",
                conversation_id="601",
                message_id="801",
                turn_id="801",
                content="clarify restore window",
                trace_id="trace-clarify",
                correlation_id="corr-clarify",
            ),
            core_agent_run_id="run-601-801",
        )

        self.assertEqual(scenario.scenario_id, "clarifying")
        event = next(
            item
            for item in scenario.ag_ui_steps[-1].events
            if item["type"] == "ACTIVITY_SNAPSHOT"
        )
        state = next(
            item for item in scenario.ag_ui_steps[-1].events if item["type"] == "STATE_SNAPSHOT"
        )

        self.assertEqual(event["content"]["meta"]["intent"], "clarification")
        self.assertEqual(state["snapshot"]["interaction"]["status"], "clarifying")
        self.assertEqual(state["snapshot"]["selection"]["selectionLocked"], False)
        actions = {item["id"]: item for item in event["content"]["actions"]}
        latest_safe = actions["submit_latest_safe_point"]["payload"]
        specific_timestamp = actions["submit_specific_timestamp"]["payload"]
        self.assertEqual(latest_safe["type"], "clarification_response")
        self.assertEqual(latest_safe["clarificationId"], "recovery_window")
        self.assertEqual(latest_safe["selectedValue"], "latest_safe_point")
        self.assertEqual(specific_timestamp["type"], "clarification_response")
        self.assertEqual(specific_timestamp["clarificationId"], "recovery_window")
        self.assertEqual(
            specific_timestamp["freeText"],
            "2026-04-24T15:30:00+08:00",
        )

    def test_doc_candidate_compare_scenario_matches_layout_tree_example(self) -> None:
        scenario = build_scenario(
            IncomingConversationMessage(
                event_id="conversation.message.created.901",
                conversation_id="801",
                message_id="901",
                turn_id="901",
                content="doc candidate compare",
                trace_id="trace-doc-candidate",
                correlation_id="corr-doc-candidate",
            ),
            core_agent_run_id="run-801-901",
        )

        self.assertEqual(scenario.scenario_id, "doc_candidate_compare")
        activity = next(
            item for item in scenario.ag_ui_steps[-1].events if item["type"] == "ACTIVITY_SNAPSHOT"
        )
        self.assertEqual(activity["content"]["blockId"], "candidate_compare_001")
        grid = next(
            child for child in activity["content"]["ui"]["children"] if child["type"] == "grid"
        )
        self.assertEqual(len(grid["children"]), 3)

    def test_doc_report_detail_scenario_contains_chart_table_and_attachments(self) -> None:
        scenario = build_scenario(
            IncomingConversationMessage(
                event_id="conversation.message.created.902",
                conversation_id="802",
                message_id="902",
                turn_id="902",
                content="doc report detail",
                trace_id="trace-doc-report",
                correlation_id="corr-doc-report",
            ),
            core_agent_run_id="run-802-902",
        )

        self.assertEqual(scenario.scenario_id, "doc_report_detail")
        activity = next(
            item for item in scenario.ag_ui_steps[-1].events if item["type"] == "ACTIVITY_SNAPSHOT"
        )
        serialized = str(activity["content"]["ui"])
        self.assertIn("chart", serialized)
        self.assertIn("data-table", serialized)
        self.assertIn("attachment-list", serialized)

    def test_doc_report_detail_submit_action_is_report_scoped_not_fixed_candidate(self) -> None:
        scenario = build_scenario(
            IncomingConversationMessage(
                event_id="conversation.message.created.903",
                conversation_id="803",
                message_id="903",
                turn_id="903",
                content="doc report detail",
                trace_id="trace-doc-report-action",
                correlation_id="corr-doc-report-action",
            ),
            core_agent_run_id="run-803-903",
        )

        activity = next(
            item for item in scenario.ag_ui_steps[-1].events if item["type"] == "ACTIVITY_SNAPSHOT"
        )
        submit_action = next(
            action
            for action in activity["content"]["actions"]
            if action["id"] == "submit_restore_plan"
        )

        self.assertEqual(submit_action["payload"]["type"], "report_action")
        self.assertEqual(submit_action["payload"]["action"], "continue_with_plan")
        self.assertIn("report_id", submit_action["payload"])
        self.assertNotIn("candidateOptionId", submit_action["payload"])

    def test_supported_scenarios_cover_all_protocol_scenes(self) -> None:
        cases = {
            "show thought summary": "thought",
            "show tool call summary": "tool_call",
            "show progress update": "progress",
            "clarify restore window": "clarifying",
            "restore order database": "restore",
            "capacity report": "capacity",
            "attachment summary": "attachment",
            "visible error panel": "visible_error",
            "doc candidate compare": "doc_candidate_compare",
            "doc report detail": "doc_report_detail",
            "incremental update": "incremental",
            "text fallback only": "text_only",
        }

        for content, expected in cases.items():
            with self.subTest(content=content):
                scenario = build_scenario(
                    IncomingConversationMessage(
                        event_id=f"conversation.message.created.{expected}",
                        conversation_id="999",
                        message_id="777",
                        turn_id="777",
                        content=content,
                        trace_id="trace-scene",
                        correlation_id="corr-scene",
                    ),
                    core_agent_run_id="run-999-777",
                )
                self.assertEqual(scenario.scenario_id, expected)

    def test_supported_layout_tree_scenarios_emit_timestamped_detailed_visible_content(
        self,
    ) -> None:
        cases = {
            "show thought summary": {"section", "kv-list", "callout"},
            "show tool call summary": {"section", "kv-list", "data-table", "callout"},
            "show progress update": {"metric-list", "chart", "callout"},
            "clarify restore window": {"section", "kv-list", "callout", "action-row"},
            "restore order database": {"section", "grid", "metric-list", "kv-list", "callout"},
            "capacity report": {"metric-list", "chart", "data-table", "callout"},
            "attachment summary": {"section", "attachment-list", "data-table", "callout"},
            "visible error panel": {"callout", "kv-list", "action-row"},
            "doc candidate compare": {"section", "grid", "metric-list", "kv-list", "callout"},
            "doc report detail": {
                "section",
                "metric-list",
                "grid",
                "markdown",
                "chart",
                "data-table",
                "attachment-list",
                "action-row",
            },
            "incremental update": {"section", "metric-list", "callout", "action-row"},
        }

        for content, expected_node_types in cases.items():
            with self.subTest(content=content):
                scenario = build_scenario(
                    IncomingConversationMessage(
                        event_id=f"conversation.message.created.{content}",
                        conversation_id="1200",
                        message_id="2200",
                        turn_id="2200",
                        content=content,
                        trace_id="trace-detailed",
                        correlation_id="corr-detailed",
                    ),
                    core_agent_run_id="run-1200-2200",
                )

                all_node_types: set[str] = set()
                for step in scenario.ag_ui_steps:
                    self.assertTrue(step.content)
                    for event in step.events:
                        self.assertIn("timestamp", event)
                        if event["type"] == "ACTIVITY_SNAPSHOT":
                            self.assertEqual(
                                event["content"]["contract"],
                                "conversation.ui.layout-tree@1",
                            )
                            all_node_types.update(_node_types(event["content"]["ui"]))
                        elif event["type"] == "STATE_SNAPSHOT":
                            self.assertIn("interaction", event["snapshot"])

                self.assertTrue(expected_node_types.issubset(all_node_types))

    def test_chart_nodes_include_frontend_compatible_items(self) -> None:
        for content in ("show progress update", "capacity report", "doc report detail"):
            with self.subTest(content=content):
                scenario = build_scenario(
                    IncomingConversationMessage(
                        event_id=f"conversation.message.created.{content}",
                        conversation_id="1500",
                        message_id="2500",
                        turn_id="2500",
                        content=content,
                        trace_id="trace-chart",
                        correlation_id="corr-chart",
                    ),
                    core_agent_run_id="run-1500-2500",
                )

                chart_nodes = [
                    node
                    for step in scenario.ag_ui_steps
                    for event in step.events
                    if event["type"] == "ACTIVITY_SNAPSHOT"
                    for node in _walk_nodes(event["content"]["ui"])
                    if node.get("type") == "chart"
                ]
                self.assertTrue(chart_nodes)
                for node in chart_nodes:
                    props = node.get("props", {})
                    self.assertIn("items", props)
                    self.assertTrue(props["items"])

    def test_reasoning_trace_scenarios_emit_detailed_visible_candidate_payloads(self) -> None:
        for content in (
            "restore order database",
            "doc candidate compare",
            "doc report detail",
        ):
            with self.subTest(content=content):
                scenario = build_scenario(
                    IncomingConversationMessage(
                        event_id=f"conversation.message.created.{content}",
                        conversation_id="1300",
                        message_id="2300",
                        turn_id="2300",
                        content=content,
                        trace_id="trace-reasoning",
                        correlation_id="corr-reasoning",
                    ),
                    core_agent_run_id="run-1300-2300",
                )

                activity = next(
                    item
                    for step in scenario.ag_ui_steps
                    for item in step.events
                    if item["type"] == "ACTIVITY_SNAPSHOT"
                    and item["content"]["meta"].get("reasoningTraceId")
                )
                trace = activity["content"]["meta"]["reasoningTrace"]

                self.assertTrue(activity["content"]["meta"]["reasoningTraceId"])
                self.assertTrue(trace["objective"])
                self.assertTrue(trace["decision_summary"])
                self.assertTrue(trace["comparison_dimensions"])
                self.assertTrue(trace["pending_confirmations"])
                self.assertEqual(len(trace["candidates"]), 3)
                for candidate in trace["candidates"]:
                    self.assertIn("candidate_option_id", candidate)
                    self.assertIn("title", candidate)
                    self.assertIn("summary", candidate)
                    self.assertIn("risk_level", candidate)
                    self.assertIn("recommendation_level", candidate)
                    self.assertIn("restore_scope", candidate)
                    self.assertIn("rpo", candidate)
                    self.assertIn("rto", candidate)
                    self.assertIn("target", candidate)
                    self.assertIn("impact_summary", candidate)
                    self.assertIn("execution_steps", candidate)

    def test_text_only_scene_streams_chunked_text_with_timestamps(self) -> None:
        scenario = build_scenario(
            IncomingConversationMessage(
                event_id="conversation.message.created.text-only",
            conversation_id="1400",
            message_id="2400",
            turn_id="2400",
            content="text fallback only",
                trace_id="trace-text",
                correlation_id="corr-text",
            ),
            core_agent_run_id="run-1400-2400",
        )

        self.assertEqual(scenario.scenario_id, "text_only")
        content_events = [
            item
            for item in scenario.ag_ui_steps[-1].events
            if item["type"] in {"TEXT_MESSAGE_CONTENT", "TEXT_MESSAGE_CHUNK"}
        ]
        self.assertGreaterEqual(len(content_events), 2)
        self.assertTrue(all("timestamp" in item for item in scenario.ag_ui_steps[-1].events))

    def test_visible_error_scene_is_not_treated_as_core_failure(self) -> None:
        incoming = IncomingConversationMessage(
            event_id="conversation.message.created.visible_error",
            conversation_id="999",
            message_id="778",
            turn_id="778",
            content="visible error panel",
            trace_id="trace-scene",
            correlation_id="corr-scene",
        )

        self.assertFalse(should_fail(incoming))
        self.assertEqual(
            build_scenario(incoming, core_agent_run_id="run-999-778").scenario_id,
            "visible_error",
        )

    def test_tracker_rejects_duplicate_input_event(self) -> None:
        tracker = SessionTracker()

        self.assertTrue(tracker.mark_seen("conversation.message.created.500"))
        self.assertFalse(tracker.mark_seen("conversation.message.created.500"))
        self.assertTrue(tracker.mark_seen("conversation.message.created.501"))

    def test_runner_uses_monotonic_ag_ui_sequence_per_conversation(self) -> None:
        publisher = _FakePublisher()
        runner = AgentMqMockRunner(
            settings=Settings(rabbitmq_url="amqp://guest:guest@localhost:5672/", delay_ms=0),
            publisher=publisher,
            tracker=SessionTracker(),
        )

        async def run_messages() -> None:
            await runner.handle_body(
                {
                    "event_id": "conversation.message.created.601",
                    "event_type": "conversation.message.created",
                    "payload": {
                        "conversation_id": "301",
                        "message_id": "601",
                        "turn_id": "601",
                        "content": "restore order database",
                    },
                }
            )
            await runner.handle_body(
                {
                    "event_id": "conversation.message.created.602",
                    "event_type": "conversation.message.created",
                    "payload": {
                        "conversation_id": "301",
                        "message_id": "602",
                        "turn_id": "602",
                        "content": "show thought summary",
                    },
                }
            )

        import asyncio

        asyncio.run(run_messages())

        sequences = [
            message.body["payload"]["sequence"]
            for message in publisher.messages
            if message.exchange == "decision_agent.bizdata.events"
        ]
        self.assertEqual(sequences, [1, 2, 3, 4])

    def test_runner_can_replay_same_ag_ui_event_for_idempotency(self) -> None:
        publisher = _FakePublisher()
        runner = AgentMqMockRunner(
            settings=Settings(rabbitmq_url="amqp://guest:guest@localhost:5672/", delay_ms=0),
            publisher=publisher,
            tracker=SessionTracker(),
        )

        async def run_message() -> None:
            await runner.handle_body(
                {
                    "event_id": "conversation.message.created.901",
                    "event_type": "conversation.message.created",
                    "payload": {
                        "conversation_id": "701",
                        "message_id": "901",
                        "turn_id": "901",
                        "content": "replay restore candidates",
                    },
                }
            )

        import asyncio

        asyncio.run(run_message())

        event_ids = [
            message.body["event_id"]
            for message in publisher.messages
            if message.exchange == "decision_agent.bizdata.events"
        ]
        self.assertGreater(len(event_ids), len(set(event_ids)))


class _FakePublisher:
    def __init__(self) -> None:
        self.messages = []

    async def publish(self, message: object) -> None:
        self.messages.append(message)


if __name__ == "__main__":
    unittest.main()


def _node_types(node: dict[str, object]) -> set[str]:
    node_types = {str(node["type"])}
    children = node.get("children")
    if isinstance(children, list):
        for child in children:
            if isinstance(child, dict):
                node_types.update(_node_types(child))
    return node_types


def _walk_nodes(node: dict[str, object]) -> list[dict[str, object]]:
    nodes = [node]
    children = node.get("children")
    if isinstance(children, list):
        for child in children:
            if isinstance(child, dict):
                nodes.extend(_walk_nodes(child))
    return nodes
