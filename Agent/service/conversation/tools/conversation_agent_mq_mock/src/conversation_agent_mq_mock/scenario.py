from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from conversation_agent_mq_mock.messages import AgUiStep, BusinessDataStep, IncomingConversationMessage


LAYOUT_TREE_ACTIVITY_TYPE = "conversation.ui.layout-tree"
LAYOUT_TREE_CONTRACT = "conversation.ui.layout-tree@1"
_TIMESTAMP_EPOCH_MS = 1_777_000_000_000


@dataclass(frozen=True, slots=True)
class ScenarioPlan:
    scenario_id: str
    core_agent_run_id: str
    result_summary: str
    ag_ui_steps: tuple[AgUiStep, ...]
    business_data_steps: tuple[BusinessDataStep, ...] = ()


def build_scenario(
    incoming: IncomingConversationMessage,
    *,
    core_agent_run_id: str,
) -> ScenarioPlan:
    scenario_id = _scenario_id(incoming.content)
    suffix = _stable_suffix(incoming.conversation_id, incoming.message_id)

    scenario_builders = {
        "thought": _thought_scenario,
        "tool_call": _tool_call_scenario,
        "progress": _progress_scenario,
        "clarifying": _clarifying_scenario,
        "restore": _restore_scenario,
        "capacity": _capacity_scenario,
        "attachment": _attachment_scenario,
        "visible_error": _visible_error_scenario,
        "doc_candidate_compare": _doc_candidate_compare_scenario,
        "doc_report_detail": _doc_report_detail_scenario,
        "incremental": _incremental_scenario,
        "text_only": _text_only_scenario,
    }
    builder = scenario_builders.get(scenario_id, _general_scenario)
    plan = builder(incoming, core_agent_run_id, suffix)
    return _stamp_scenario_events(
        plan,
        conversation_id=incoming.conversation_id,
        message_id=incoming.message_id,
    )


def should_reject(incoming: IncomingConversationMessage) -> bool:
    normalized = incoming.content.lower()
    return "unsupported" in normalized or "not supported" in normalized


def should_fail(incoming: IncomingConversationMessage) -> bool:
    normalized = incoming.content.lower()
    if "visible error" in normalized:
        return False
    return "fail" in normalized or "error" in normalized or "simulated failure" in normalized


def should_replay(incoming: IncomingConversationMessage) -> bool:
    normalized = incoming.content.lower()
    return "replay" in normalized or "duplicate" in normalized


def _thought_scenario(
    incoming: IncomingConversationMessage,
    core_agent_run_id: str,
    suffix: str,
) -> ScenarioPlan:
    del incoming
    summary = "Collected the request intent and selected the next retrieval step."
    block_id = f"thought_{suffix}"
    return ScenarioPlan(
        scenario_id="thought",
        core_agent_run_id=core_agent_run_id,
        result_summary=summary,
        ag_ui_steps=(
            AgUiStep(
                sequence=1,
                content=summary,
                events=(
                    _activity(
                        message_id=f"activity_{block_id}",
                        block_id=block_id,
                        ui=_stack(
                            [
                                _section(
                                    [
                                        _heading("Visible reasoning summary", level=2),
                                        _paragraph(
                                            "The agent exposed only user-visible analysis milestones "
                                            "instead of raw chain-of-thought."
                                        ),
                                    ],
                                    node_id="thought_header",
                                ),
                                _card(
                                    "Execution focus",
                                    [
                                        _kv_list(
                                            [
                                                {
                                                    "label": "Detected intent",
                                                    "value": "Restore planning",
                                                },
                                                {
                                                    "label": "Next step",
                                                    "value": "Query restore-point inventory",
                                                },
                                                {
                                                    "label": "Run id",
                                                    "value": core_agent_run_id,
                                                },
                                            ]
                                        ),
                                        _metric_list(
                                            [
                                                {"label": "Confidence", "value": "high"},
                                                {"label": "Exposure level", "value": "visible only"},
                                            ]
                                        ),
                                    ],
                                ),
                                _callout(
                                    "info",
                                    "Why this is safe to show",
                                    "This panel contains only a summarized reasoning milestone "
                                    "that can be returned by the API.",
                                ),
                            ],
                            gap="lg",
                        ),
                        meta={"intent": "thought", "terminal": False},
                    ),
                    _state(active_block_ids=[block_id]),
                ),
            ),
        ),
    )


def _tool_call_scenario(
    incoming: IncomingConversationMessage,
    core_agent_run_id: str,
    suffix: str,
) -> ScenarioPlan:
    summary = "Finished querying recovery-point metadata."
    block_id = f"tool_call_{suffix}"
    return ScenarioPlan(
        scenario_id="tool_call",
        core_agent_run_id=core_agent_run_id,
        result_summary=summary,
        ag_ui_steps=(
            AgUiStep(
                sequence=1,
                content=summary,
                events=(
                    _activity(
                        message_id=f"activity_{block_id}",
                        block_id=block_id,
                        ui=_stack(
                            [
                                _section(
                                    [
                                        _heading("Tool execution summary", level=2),
                                        _paragraph(
                                            "The restore-point search tool completed and returned a "
                                            "masked, user-visible result summary."
                                        ),
                                    ],
                                    node_id="tool_header",
                                ),
                                _card(
                                    "Tool call details",
                                    [
                                        _kv_list(
                                            [
                                                {"label": "Tool", "value": "restore_point.search"},
                                                {"label": "Status", "value": "completed"},
                                                {
                                                    "label": "Input summary",
                                                    "value": (
                                                        "Search around the requested Friday afternoon "
                                                        "window for order database recovery points"
                                                    ),
                                                },
                                                {"label": "Result summary", "value": "3 restore points found"},
                                                {"label": "Run id", "value": core_agent_run_id},
                                            ]
                                        )
                                    ],
                                ),
                                _data_table(
                                    [
                                        {"key": "checkpoint", "label": "Checkpoint"},
                                        {"key": "restore_point", "label": "Restore point"},
                                        {"key": "lag", "label": "Replay lag"},
                                        {"key": "status", "label": "Status"},
                                    ],
                                    [
                                        {
                                            "checkpoint": "Latest safe",
                                            "restore_point": f"rp-{suffix}",
                                            "lag": "2 minutes",
                                            "status": "recommended",
                                        },
                                        {
                                            "checkpoint": "Earlier consistent",
                                            "restore_point": f"rp-{suffix}-safe",
                                            "lag": "12 minutes",
                                            "status": "available",
                                        },
                                    ],
                                ),
                                _callout(
                                    "info",
                                    "Visibility note",
                                    "Only masked tool parameters and summarized results are returned "
                                    "through conversation history.",
                                ),
                            ],
                            gap="lg",
                        ),
                        meta={
                            "intent": "tool_call",
                            "terminal": False,
                            "sourceMessageId": incoming.message_id,
                        },
                    ),
                    _state(active_block_ids=[block_id]),
                ),
            ),
        ),
    )


def _progress_scenario(
    incoming: IncomingConversationMessage,
    core_agent_run_id: str,
    suffix: str,
) -> ScenarioPlan:
    del incoming
    summary = "Recovery-plan generation is 66% complete."
    block_id = f"progress_{suffix}"
    return ScenarioPlan(
        scenario_id="progress",
        core_agent_run_id=core_agent_run_id,
        result_summary=summary,
        ag_ui_steps=(
            AgUiStep(
                sequence=1,
                content=summary,
                events=(
                    _activity(
                        message_id=f"activity_{block_id}",
                        block_id=block_id,
                        ui=_stack(
                            [
                                _section(
                                    [
                                        _heading("Plan generation progress", level=2),
                                        _paragraph(
                                            "The plan is being assembled from restore-point data, "
                                            "risk comparison, and execution constraints."
                                        ),
                                    ],
                                    node_id="progress_header",
                                ),
                                _metric_list(
                                    [
                                        {"label": "Completed", "value": "66%"},
                                        {"label": "Current step", "value": "Risk comparison"},
                                        {"label": "Remaining", "value": "2 steps"},
                                        {"label": "ETA", "value": "about 40 seconds"},
                                    ]
                                ),
                                _chart(
                                    "line",
                                    x_axis=["Inventory", "Validation", "Comparison", "Finalize"],
                                    series=[
                                        {"name": "Completion", "data": [100, 100, 66, 0]},
                                    ],
                                ),
                                _callout(
                                    "warning",
                                    "Awaiting final comparison",
                                    "The agent is still validating the business window and "
                                    "operational risk before emitting a terminal result.",
                                ),
                            ],
                            gap="lg",
                        ),
                        meta={"intent": "progress", "terminal": False},
                    ),
                    _state(active_block_ids=[block_id]),
                ),
            ),
        ),
    )


def _clarifying_scenario(
    incoming: IncomingConversationMessage,
    core_agent_run_id: str,
    suffix: str,
) -> ScenarioPlan:
    del incoming
    prompt = "Please confirm the target recovery time window."
    block_id = f"clarification_{suffix}"
    return ScenarioPlan(
        scenario_id="clarifying",
        core_agent_run_id=core_agent_run_id,
        result_summary=prompt,
        ag_ui_steps=(
            AgUiStep(
                sequence=1,
                content=prompt,
                events=(
                    _activity(
                        message_id=f"activity_{block_id}",
                        block_id=block_id,
                        ui=_stack(
                            [
                                _section(
                                    [
                                        _heading("Clarification required", level=2),
                                        _paragraph(
                                            "The request can proceed after the recovery window is "
                                            "explicitly confirmed."
                                        ),
                                    ],
                                    node_id="clarification_header",
                                ),
                                _card(
                                    "Recovery window options",
                                    [
                                        _kv_list(
                                            [
                                                {"label": "Option A", "value": "Latest safe point"},
                                                {
                                                    "label": "Option B",
                                                    "value": "Specific timestamp around Friday 15:30",
                                                },
                                                {
                                                    "label": "Impact",
                                                    "value": "A wider window may change the candidate ranking",
                                                },
                                            ]
                                        ),
                                        _callout(
                                            "info",
                                            "Why confirmation is needed",
                                            "The API can display this question directly and wait for "
                                            "the next user action without exposing hidden reasoning.",
                                        ),
                                        _action_row(
                                            [
                                                "submit_latest_safe_point",
                                                "submit_specific_timestamp",
                                            ]
                                        ),
                                    ],
                                ),
                            ],
                            gap="lg",
                        ),
                        actions=[
                            _action(
                                "submit_latest_safe_point",
                                "submit_message",
                                "Use latest safe point",
                                payload={
                                    "type": "clarification_response",
                                    "clarificationId": "recovery_window",
                                    "selectedValue": "latest_safe_point",
                                },
                                style="primary",
                            ),
                            _action(
                                "submit_specific_timestamp",
                                "submit_message",
                                "Provide specific timestamp",
                                payload={
                                    "type": "clarification_response",
                                    "clarificationId": "recovery_window",
                                    "freeText": "2026-04-24T15:30:00+08:00",
                                },
                            ),
                        ],
                        meta={"intent": "clarification", "terminal": False},
                    ),
                    _state(
                        active_block_ids=[block_id],
                        selection={
                            "required": True,
                            "selectedCandidateOptionId": None,
                            "selectionLocked": False,
                        },
                    ),
                ),
            ),
        ),
    )


def _restore_scenario(
    incoming: IncomingConversationMessage,
    core_agent_run_id: str,
    suffix: str,
) -> ScenarioPlan:
    restore_point = f"rp-{suffix}"
    reasoning_trace_id = _stable_reasoning_trace_id(incoming.conversation_id, incoming.message_id)
    candidates = _restore_candidates(restore_point)
    recommended_candidate_option_id = candidates[0]["candidate_option_id"]
    summary = f"Generated three recovery candidates for conversation {incoming.conversation_id}."
    result_block_id = f"restore_candidates_{suffix}"
    reasoning_trace = {
        "objective": "Select a safe recovery plan for the order database.",
        "decision_summary": summary,
        "recommendation": f"Prefer restore point {restore_point} on the alternate host path.",
        "recommended_candidate_option_id": recommended_candidate_option_id,
        "comparison_dimensions": [
            "RPO",
            "RTO",
            "Operational risk",
            "Business impact",
        ],
        "pending_confirmations": [
            {
                "confirmation_id": f"confirm-{restore_point}",
                "prompt": f"Confirm using restore point {restore_point}?",
                "allowed_actions": ["confirm", "reject", "revise"],
            }
        ],
        "candidates": candidates,
        "status": "ready_for_confirmation",
    }
    actions = _candidate_actions(candidates, reasoning_trace_id)
    return ScenarioPlan(
        scenario_id="restore",
        core_agent_run_id=core_agent_run_id,
        result_summary=summary,
        ag_ui_steps=(
            AgUiStep(
                sequence=1,
                content="Understanding restore target and checking available restore points.",
                events=(
                    _activity(
                        message_id=f"activity_restore_thought_{suffix}",
                        block_id=f"restore_thought_{suffix}",
                        ui=_stack(
                            [
                                _section(
                                    [
                                        _heading("Restore analysis", level=2),
                                        _paragraph(
                                            "The target database, recovery window, and production "
                                            "guardrails have been parsed from the user request."
                                        ),
                                    ],
                                    node_id="restore_analysis_header",
                                ),
                                _card(
                                    "Current understanding",
                                    [
                                        _kv_list(
                                            [
                                                {"label": "Target asset", "value": "orders-db"},
                                                {"label": "Requested window", "value": "Last Friday afternoon"},
                                                {"label": "Risk preference", "value": "Prefer safe recovery"},
                                            ]
                                        ),
                                        _callout(
                                            "info",
                                            "Next action",
                                            "Search available restore points and compare execution paths.",
                                        ),
                                    ],
                                ),
                            ],
                            gap="lg",
                        ),
                        meta={"intent": "thought", "terminal": False},
                    ),
                    _state(active_block_ids=[f"restore_thought_{suffix}"]),
                ),
            ),
            AgUiStep(
                sequence=2,
                content=f"Found restore point {restore_point} and two alternatives.",
                events=(
                    _activity(
                        message_id=f"activity_restore_tool_{suffix}",
                        block_id=f"restore_tool_{suffix}",
                        ui=_stack(
                            [
                                _section(
                                    [
                                        _heading("Restore-point search", level=2),
                                        _paragraph(
                                            "The tool returned one recommended restore point and two "
                                            "fallback alternatives."
                                        ),
                                    ],
                                    node_id="restore_tool_header",
                                ),
                                _card(
                                    "Tool summary",
                                    [
                                        _kv_list(
                                            [
                                                {"label": "Tool", "value": "restore_point.search"},
                                                {"label": "Primary point", "value": restore_point},
                                                {"label": "Alternatives", "value": "2"},
                                                {"label": "Run id", "value": core_agent_run_id},
                                            ]
                                        )
                                    ],
                                ),
                                _data_table(
                                    [
                                        {"key": "option", "label": "Option"},
                                        {"key": "restore_point", "label": "Restore point"},
                                        {"key": "expected_rpo", "label": "Expected RPO"},
                                        {"key": "comment", "label": "Comment"},
                                    ],
                                    [
                                        {
                                            "option": "Recommended",
                                            "restore_point": restore_point,
                                            "expected_rpo": candidates[0]["rpo"],
                                            "comment": "Best balance of scope control and speed",
                                        },
                                        {
                                            "option": "Fallback",
                                            "restore_point": f"{restore_point}-safe",
                                            "expected_rpo": candidates[1]["rpo"],
                                            "comment": "Safer but older point",
                                        },
                                    ],
                                ),
                                _callout(
                                    "warning",
                                    "Pending comparison",
                                    "Resource availability and production freeze window are still "
                                    "being compared before final confirmation.",
                                ),
                            ],
                            gap="lg",
                        ),
                        meta={"intent": "tool_call", "terminal": False},
                    ),
                    _state(active_block_ids=[f"restore_tool_{suffix}"]),
                ),
            ),
            AgUiStep(
                sequence=3,
                content=summary,
                events=(
                    _activity(
                        message_id=f"activity_{result_block_id}",
                        block_id=result_block_id,
                        ui=_candidate_compare_ui(
                            candidates,
                            heading="Candidate recovery plans",
                            subtitle=(
                                "Compare dynamically generated options across speed, impact, "
                                "execution effort, and risk."
                            ),
                        ),
                        actions=actions,
                        meta={
                            "intent": "result",
                            "terminal": True,
                            "reasoningTraceId": reasoning_trace_id,
                            "reasoningTrace": reasoning_trace,
                        },
                    ),
                    _state(
                        active_block_ids=[result_block_id],
                        selection={
                            "required": True,
                            "selectedCandidateOptionId": None,
                            "selectionLocked": False,
                        },
                    ),
                ),
            ),
        ),
    )


def _capacity_scenario(
    incoming: IncomingConversationMessage,
    core_agent_run_id: str,
    suffix: str,
) -> ScenarioPlan:
    del incoming
    used_percent = 60 + int(suffix) % 25
    summary = f"Capacity usage is projected to reach {used_percent}% in 14 days."
    block_id = f"capacity_{suffix}"
    return ScenarioPlan(
        scenario_id="capacity",
        core_agent_run_id=core_agent_run_id,
        result_summary=summary,
        ag_ui_steps=(
            AgUiStep(
                sequence=1,
                content=summary,
                events=(
                    _activity(
                        message_id=f"activity_{block_id}",
                        block_id=block_id,
                        ui=_stack(
                            [
                                _section(
                                    [
                                        _heading("Capacity forecast", level=2),
                                        _paragraph(
                                            "Forecast generated from recent storage consumption and "
                                            "write-rate trends."
                                        ),
                                    ],
                                    node_id="capacity_header",
                                ),
                                _metric_list(
                                    [
                                        {"label": "Current usage", "value": f"{used_percent - 8}%"},
                                        {"label": "D+7", "value": f"{used_percent - 3}%"},
                                        {"label": "D+14", "value": f"{used_percent}%"},
                                        {"label": "Threshold", "value": "80%"},
                                    ]
                                ),
                                _chart(
                                    "line",
                                    x_axis=["D+0", "D+7", "D+14"],
                                    series=[
                                        {
                                            "name": "Projected usage",
                                            "data": [used_percent - 8, used_percent - 3, used_percent],
                                        }
                                    ],
                                ),
                                _data_table(
                                    [
                                        {"key": "pool", "label": "Pool"},
                                        {"key": "current", "label": "Current"},
                                        {"key": "d14", "label": "D+14"},
                                        {"key": "risk", "label": "Risk"},
                                    ],
                                    [
                                        {
                                            "pool": "primary-ssd",
                                            "current": f"{used_percent - 10}%",
                                            "d14": f"{used_percent - 2}%",
                                            "risk": "medium",
                                        },
                                        {
                                            "pool": "archive-hdd",
                                            "current": "54%",
                                            "d14": "57%",
                                            "risk": "low",
                                        },
                                    ],
                                ),
                                _callout(
                                    "warning",
                                    "Scale recommendation",
                                    "Provision additional space before the primary pool reaches the "
                                    "80 percent operational guardrail.",
                                ),
                                _action_row(["download_capacity_report", "open_scale_plan"]),
                            ],
                            gap="lg",
                        ),
                        actions=[
                            _action(
                                "download_capacity_report",
                                "open_ref",
                                "Open capacity report",
                                payload={"refId": f"capacity-report-{suffix}"},
                                style="primary",
                            ),
                            _action(
                                "open_scale_plan",
                                "open_ref",
                                "Open scale plan",
                                payload={"refId": f"scale-plan-{suffix}"},
                            ),
                        ],
                        meta={"intent": "result", "terminal": True},
                    ),
                    _state(active_block_ids=[block_id]),
                ),
            ),
        ),
    )


def _attachment_scenario(
    incoming: IncomingConversationMessage,
    core_agent_run_id: str,
    suffix: str,
) -> ScenarioPlan:
    del incoming
    summary = "Generated two downloadable recovery artifacts."
    block_id = f"attachments_{suffix}"
    artifacts = [
        {
            "title": "Recovery runbook",
            "refId": f"runbook-{suffix}",
            "contentType": "text/markdown",
            "size": "18 KB",
            "summary": "Execution checklist for alternate-host restore",
        },
        {
            "title": "Risk validation report",
            "refId": f"risk-{suffix}",
            "contentType": "application/pdf",
            "size": "240 KB",
            "summary": "Business impact and verification recommendations",
        },
    ]
    return ScenarioPlan(
        scenario_id="attachment",
        core_agent_run_id=core_agent_run_id,
        result_summary=summary,
        ag_ui_steps=(
            AgUiStep(
                sequence=1,
                content=summary,
                events=(
                    _activity(
                        message_id=f"activity_{block_id}",
                        block_id=block_id,
                        ui=_stack(
                            [
                                _section(
                                    [
                                        _heading("Generated artifacts", level=2),
                                        _paragraph(
                                            "The agent packaged the most useful follow-up artifacts "
                                            "for review and execution."
                                        ),
                                    ],
                                    node_id="attachments_header",
                                ),
                                _callout(
                                    "info",
                                    "How to use them",
                                    "Review the runbook first, then open the risk report before "
                                    "executing the selected restore plan.",
                                ),
                                _attachment_list(artifacts),
                                _data_table(
                                    [
                                        {"key": "artifact", "label": "Artifact"},
                                        {"key": "purpose", "label": "Purpose"},
                                        {"key": "size", "label": "Size"},
                                    ],
                                    [
                                        {
                                            "artifact": "Recovery runbook",
                                            "purpose": "Execution checklist",
                                            "size": "18 KB",
                                        },
                                        {
                                            "artifact": "Risk validation report",
                                            "purpose": "Review and approval",
                                            "size": "240 KB",
                                        },
                                    ],
                                ),
                            ],
                            gap="lg",
                        ),
                        meta={"intent": "result", "terminal": True},
                    ),
                    _state(active_block_ids=[block_id]),
                ),
            ),
        ),
    )


def _visible_error_scenario(
    incoming: IncomingConversationMessage,
    core_agent_run_id: str,
    suffix: str,
) -> ScenarioPlan:
    del incoming
    summary = "The requested operation cannot continue without a valid restore point."
    block_id = f"visible_error_{suffix}"
    return ScenarioPlan(
        scenario_id="visible_error",
        core_agent_run_id=core_agent_run_id,
        result_summary=summary,
        ag_ui_steps=(
            AgUiStep(
                sequence=1,
                content=summary,
                events=(
                    _activity(
                        message_id=f"activity_{block_id}",
                        block_id=block_id,
                        ui=_stack(
                            [
                                _section(
                                    [
                                        _heading("Restore cannot continue", level=2),
                                        _paragraph(
                                            "The agent found no valid restore point that satisfies "
                                            "the current request constraints."
                                        ),
                                    ],
                                    node_id="error_header",
                                ),
                                _callout("error", "Restore point unavailable", summary),
                                _kv_list(
                                    [
                                        {"label": "Error code", "value": "RESTORE_POINT_UNAVAILABLE"},
                                        {"label": "Retryable", "value": "true"},
                                        {"label": "Recommended action", "value": "Widen the time window"},
                                    ]
                                ),
                                _action_row(["retry_restore_search", "open_restore_runbook"]),
                            ],
                            gap="lg",
                        ),
                        actions=[
                            _action(
                                "retry_restore_search",
                                "submit_message",
                                "Retry with wider window",
                                payload={"action": "retry_restore_search"},
                                style="primary",
                            ),
                            _action(
                                "open_restore_runbook",
                                "open_ref",
                                "Open troubleshooting runbook",
                                payload={"refId": "restore-runbook-visible-error"},
                            ),
                        ],
                        meta={"intent": "error", "terminal": True},
                    ),
                    _state(active_block_ids=[block_id]),
                ),
            ),
        ),
    )


def _doc_candidate_compare_scenario(
    incoming: IncomingConversationMessage,
    core_agent_run_id: str,
    suffix: str,
) -> ScenarioPlan:
    del suffix
    reasoning_trace_id = _stable_reasoning_trace_id(incoming.conversation_id, incoming.message_id)
    candidates = _document_candidate_compare_candidates()
    summary = "Generated three candidate recovery plans."
    reasoning_trace = {
        "objective": "Choose a recovery plan.",
        "decision_summary": summary,
        "recommendation": "Plan A is recommended because it keeps the scope controlled.",
        "recommended_candidate_option_id": "candidate_option_a",
        "comparison_dimensions": ["RPO/RTO", "Impact", "Risk", "Execution complexity"],
        "pending_confirmations": [
            {
                "confirmation_id": "confirm-candidate-option-a",
                "prompt": "Confirm Plan A as the submission target?",
                "allowed_actions": ["confirm", "reject", "revise"],
            }
        ],
        "candidates": candidates,
        "status": "ready_for_confirmation",
    }
    return ScenarioPlan(
        scenario_id="doc_candidate_compare",
        core_agent_run_id=core_agent_run_id,
        result_summary=summary,
        ag_ui_steps=(
            AgUiStep(
                sequence=1,
                content=summary,
                events=(
                    _activity(
                        message_id="activity_candidate_compare_001",
                        block_id="candidate_compare_001",
                        ui=_candidate_compare_ui(
                            candidates,
                            heading="Generated three recovery candidates",
                            subtitle=(
                                "The layout is dynamically assembled from recovery speed, "
                                "business impact, execution effort, and risk level."
                            ),
                        ),
                        actions=_candidate_actions(candidates, reasoning_trace_id),
                        meta={
                            "intent": "result",
                            "terminal": True,
                            "reasoningTraceId": reasoning_trace_id,
                            "reasoningTrace": reasoning_trace,
                        },
                    ),
                    _state(
                        active_block_ids=["candidate_compare_001"],
                        selection={
                            "required": True,
                            "selectedCandidateOptionId": None,
                            "selectionLocked": False,
                        },
                    ),
                ),
            ),
        ),
    )


def _doc_report_detail_scenario(
    incoming: IncomingConversationMessage,
    core_agent_run_id: str,
    suffix: str,
) -> ScenarioPlan:
    reasoning_trace_id = _stable_reasoning_trace_id(incoming.conversation_id, incoming.message_id)
    candidates = _report_detail_candidates(suffix)
    summary = "Generated a structured recovery feasibility report."
    block_id = f"report_detail_{suffix}"
    report_id = f"restore_report_{suffix}"
    reasoning_trace = {
        "objective": "Summarize the recommended recovery report for execution.",
        "decision_summary": summary,
        "recommendation": "Continue with the alternate-host database restore report.",
        "recommended_candidate_option_id": candidates[0]["candidate_option_id"],
        "comparison_dimensions": ["Recommended point", "Duration", "Risk", "Affected objects"],
        "pending_confirmations": [
            {
                "confirmation_id": f"confirm-report-{suffix}",
                "prompt": "Continue with the recommended report-backed plan?",
                "allowed_actions": ["confirm", "reject", "revise"],
            }
        ],
        "candidates": candidates,
        "status": "report_ready",
    }
    return ScenarioPlan(
        scenario_id="doc_report_detail",
        core_agent_run_id=core_agent_run_id,
        result_summary=summary,
        ag_ui_steps=(
            AgUiStep(
                sequence=1,
                content=summary,
                events=(
                    _activity(
                        message_id=f"activity_{block_id}",
                        block_id=block_id,
                        ui=_stack(
                            [
                                _section(
                                    [
                                        _heading("Recovery feasibility report", level=2),
                                        _badge_row(
                                            [
                                                {"tone": "positive", "text": "Executable"},
                                                {"tone": "neutral", "text": "Auto-generated"},
                                            ]
                                        ),
                                        _paragraph(
                                            "This report combines the current restore window, risk "
                                            "assessment, and execution guidance into one block."
                                        ),
                                    ],
                                    node_id="report_header",
                                ),
                                _metric_list(
                                    [
                                        {"label": "Recommended restore point", "value": candidates[0]["target"]},
                                        {"label": "Estimated duration", "value": candidates[0]["rto"]},
                                        {"label": "Affected objects", "value": "2"},
                                        {"label": "Risk level", "value": candidates[0]["risk_level"]},
                                    ]
                                ),
                                _grid(
                                    [
                                        _stack(
                                            [
                                                _card(
                                                    "Recovery steps overview",
                                                    [
                                                        _markdown(
                                                            "1. Prepare alternate host\n"
                                                            "2. Restore target instance\n"
                                                            "3. Export selected table\n"
                                                            "4. Validate and import"
                                                        )
                                                    ],
                                                    node_id="left_steps_card",
                                                ),
                                                _card(
                                                    "Risk notes",
                                                    [
                                                        _callout(
                                                            "warning",
                                                            "Attention required",
                                                            "Confirm the target table is write-frozen "
                                                            "before import and run integrity checks "
                                                            "before cutover.",
                                                        )
                                                    ],
                                                    node_id="left_risk_card",
                                                ),
                                            ],
                                            gap="md",
                                        ),
                                        _stack(
                                            [
                                                _card(
                                                    "Capacity trend",
                                                    [
                                                        _chart(
                                                            "line",
                                                            x_axis=["08:00", "08:30", "09:00", "09:30"],
                                                            series=[
                                                                {
                                                                    "name": "Write volume",
                                                                    "data": [12, 18, 22, 16],
                                                                }
                                                            ],
                                                        )
                                                    ],
                                                    node_id="right_chart_card",
                                                )
                                            ],
                                            gap="md",
                                        ),
                                    ],
                                    columns=2,
                                ),
                                _section(
                                    [
                                        _heading("Object details", level=3),
                                        _data_table(
                                            [
                                                {"key": "object_name", "label": "Object"},
                                                {"key": "restore_scope", "label": "Restore scope"},
                                                {"key": "risk_level", "label": "Risk level"},
                                                {"key": "comment", "label": "Comment"},
                                            ],
                                            [
                                                {
                                                    "object_name": "order_details",
                                                    "restore_scope": "target table",
                                                    "risk_level": "medium",
                                                    "comment": "Run integrity validation before import",
                                                },
                                                {
                                                    "object_name": "order_archive",
                                                    "restore_scope": "validation only",
                                                    "risk_level": "low",
                                                    "comment": "No backfill required",
                                                },
                                            ],
                                        ),
                                    ],
                                    node_id="detail_table_section",
                                ),
                                _attachment_list(
                                    [
                                        {
                                            "title": "Execution checklist",
                                            "refId": f"report-attachment-checklist-{suffix}",
                                            "contentType": "application/pdf",
                                        },
                                        {
                                            "title": "Risk validation report",
                                            "refId": f"report-attachment-risk-{suffix}",
                                            "contentType": "application/pdf",
                                        },
                                    ]
                                ),
                                _action_row(["submit_restore_plan", "download_report"]),
                            ],
                            gap="lg",
                        ),
                        actions=[
                            _action(
                                "submit_restore_plan",
                                "submit_message",
                                "Continue with this plan",
                                payload={
                                    "type": "report_action",
                                    "action": "continue_with_plan",
                                    "report_id": report_id,
                                },
                                style="primary",
                            ),
                            _action(
                                "download_report",
                                "open_ref",
                                "Open full report",
                                payload={"refId": report_id},
                            ),
                        ],
                        meta={
                            "intent": "result",
                            "terminal": True,
                            "reasoningTraceId": reasoning_trace_id,
                            "reasoningTrace": reasoning_trace,
                        },
                    ),
                    _state(active_block_ids=[block_id]),
                ),
            ),
        ),
    )


def _incremental_scenario(
    incoming: IncomingConversationMessage,
    core_agent_run_id: str,
    suffix: str,
) -> ScenarioPlan:
    del incoming
    block_id = f"incremental_{suffix}"
    summary = "Published an initial panel and then patched the progress value."
    return ScenarioPlan(
        scenario_id="incremental",
        core_agent_run_id=core_agent_run_id,
        result_summary=summary,
        ag_ui_steps=(
            AgUiStep(
                sequence=1,
                content=summary,
                events=(
                    _activity(
                        message_id=f"activity_{block_id}",
                        block_id=block_id,
                        ui=_stack(
                            [
                                _section(
                                    [
                                        _heading("Incremental update", level=2),
                                        _paragraph(
                                            "The agent first published a draft panel and then patched "
                                            "visible fields as execution progressed."
                                        ),
                                    ],
                                    node_id="incremental_header",
                                ),
                                _card(
                                    "Current draft",
                                    [
                                        _metric_list(
                                            [
                                                {"label": "Progress", "value": "20%"},
                                                {"label": "Current step", "value": "Prepare plan skeleton"},
                                            ]
                                        ),
                                        _callout(
                                            "info",
                                            "Next update",
                                            "The next delta will replace the progress value and step summary.",
                                        ),
                                        _action_row(["open_incremental_details"]),
                                    ],
                                ),
                            ],
                            gap="lg",
                        ),
                        meta={
                            "intent": "progress",
                            "terminal": False,
                            "replaceStrategy": "patch",
                        },
                        actions=[
                            _action(
                                "open_incremental_details",
                                "open_ref",
                                "Open draft details",
                                payload={"refId": f"incremental-draft-{suffix}"},
                            )
                        ],
                    ),
                    _state(active_block_ids=[block_id]),
                    _activity_delta(
                        message_id=f"activity_{block_id}",
                        patch=[
                            {
                                "op": "replace",
                                "path": "/ui/children/1/children/0/props/items/0/value",
                                "value": "80%",
                            },
                            {
                                "op": "replace",
                                "path": "/ui/children/1/children/0/props/items/1/value",
                                "value": "Validate execution guardrails",
                            },
                            {
                                "op": "replace",
                                "path": "/ui/children/1/children/1/props/text",
                                "value": "Validation succeeded and the panel is nearly ready for completion.",
                            },
                        ],
                    ),
                    _state_delta(
                        [
                            {"op": "replace", "path": "/view/activeBlockIds/0", "value": block_id},
                        ]
                    ),
                ),
            ),
        ),
    )


def _text_only_scenario(
    incoming: IncomingConversationMessage,
    core_agent_run_id: str,
    suffix: str,
) -> ScenarioPlan:
    del incoming, suffix
    message_id = f"text_only_{core_agent_run_id}"
    summary = "This response intentionally contains only AG-UI text message events."
    return ScenarioPlan(
        scenario_id="text_only",
        core_agent_run_id=core_agent_run_id,
        result_summary=summary,
        ag_ui_steps=(
            AgUiStep(
                sequence=1,
                content=summary,
                events=(
                    {
                        "type": "TEXT_MESSAGE_START",
                        "messageId": message_id,
                        "role": "assistant",
                    },
                    {
                        "type": "TEXT_MESSAGE_CONTENT",
                        "messageId": message_id,
                        "delta": "This response intentionally contains ",
                    },
                    {
                        "type": "TEXT_MESSAGE_CONTENT",
                        "messageId": message_id,
                        "delta": "only AG-UI text message events.",
                    },
                    {"type": "TEXT_MESSAGE_END", "messageId": message_id},
                ),
            ),
        ),
    )


def _general_scenario(
    incoming: IncomingConversationMessage,
    core_agent_run_id: str,
    suffix: str,
) -> ScenarioPlan:
    summary = f"Generated mock analysis result {suffix} for conversation {incoming.conversation_id}."
    block_id = f"general_result_{suffix}"
    return ScenarioPlan(
        scenario_id="general",
        core_agent_run_id=core_agent_run_id,
        result_summary=summary,
        ag_ui_steps=(
            AgUiStep(
                sequence=1,
                content=summary,
                events=(
                    _activity(
                        message_id=f"activity_{block_id}",
                        block_id=block_id,
                        ui=_stack(
                            [
                                _section(
                                    [
                                        _heading("Mock analysis result", level=2),
                                        _paragraph(summary),
                                    ],
                                    node_id="general_header",
                                ),
                                _card(
                                    "Input excerpt",
                                    [
                                        _paragraph(incoming.content[:120]),
                                        _kv_list(
                                            [
                                                {"label": "Conversation", "value": incoming.conversation_id},
                                                {"label": "Message", "value": incoming.message_id},
                                            ]
                                        ),
                                        _callout(
                                            "info",
                                            "Fallback scene",
                                            "This generic layout is used when no specialized mock "
                                            "scenario token is present.",
                                        ),
                                    ],
                                ),
                            ],
                            gap="lg",
                        ),
                        meta={"intent": "result", "terminal": True},
                    ),
                    _state(active_block_ids=[block_id]),
                ),
            ),
        ),
    )


def _scenario_id(content: str) -> str:
    normalized = content.lower()
    ordered_matches = (
        ("clarification_response", "restore"),
        ("doc candidate compare", "doc_candidate_compare"),
        ("doc report detail", "doc_report_detail"),
        ("show thought", "thought"),
        ("show tool call", "tool_call"),
        ("show progress", "progress"),
        ("clarify", "clarifying"),
        ("replay restore", "restore"),
        ("restore", "restore"),
        ("capacity", "capacity"),
        ("attachment", "attachment"),
        ("visible error", "visible_error"),
        ("incremental", "incremental"),
        ("text fallback", "text_only"),
    )
    for token, scenario_id in ordered_matches:
        if token in normalized:
            return scenario_id
    return "general"


def _stable_suffix(conversation_id: str, message_id: str) -> str:
    seed = sum(ord(ch) for ch in f"{conversation_id}:{message_id}")
    return f"{seed % 997:03d}"


def _stable_reasoning_trace_id(conversation_id: str, message_id: str) -> str:
    seed = sum((index + 1) * ord(ch) for index, ch in enumerate(f"{conversation_id}:{message_id}"))
    return f"trace-{seed % 9_000_000 + 1_000_000}"


def _stamp_scenario_events(
    plan: ScenarioPlan,
    *,
    conversation_id: str,
    message_id: str,
) -> ScenarioPlan:
    base_ms = _timestamp_base(conversation_id, message_id)
    counter = 0
    stamped_steps: list[AgUiStep] = []
    for step in plan.ag_ui_steps:
        stamped_events: list[dict[str, Any]] = []
        for raw_event in step.events:
            event = dict(raw_event)
            if "timestamp" not in event:
                event["timestamp"] = base_ms + counter * 100
            counter += 1
            stamped_events.append(event)
        stamped_steps.append(
            AgUiStep(
                sequence=step.sequence,
                content=step.content,
                events=tuple(stamped_events),
            )
        )
    return ScenarioPlan(
        scenario_id=plan.scenario_id,
        core_agent_run_id=plan.core_agent_run_id,
        result_summary=plan.result_summary,
        ag_ui_steps=tuple(stamped_steps),
    )


def _timestamp_base(conversation_id: str, message_id: str) -> int:
    seed = sum((index + 11) * ord(ch) for index, ch in enumerate(f"{conversation_id}:{message_id}"))
    return _TIMESTAMP_EPOCH_MS + seed % 1_000_000


def _restore_candidates(restore_point: str) -> list[dict[str, Any]]:
    return [
        {
            "candidate_option_id": f"candidate-{restore_point}",
            "title": f"Use restore point {restore_point}",
            "summary": "Fast recovery path with controlled production impact.",
            "recommendation_level": "recommended",
            "risk_level": "medium",
            "restore_scope": "database restore on alternate host plus table export/import",
            "rpo": "< 2 minutes",
            "rto": "about 1.5 hours",
            "target": "Alternate MySQL recovery environment",
            "impact_summary": "Limits the blast radius to the target business table.",
            "execution_steps": [
                "Provision alternate host",
                "Restore database snapshot",
                "Export order_details",
                "Validate and import into production",
            ],
            "validation_checks": [
                "row count parity",
                "checksum sample",
                "application smoke test",
            ],
            "business_window": "short write freeze during import",
        },
        {
            "candidate_option_id": f"candidate-{restore_point}-safe",
            "title": "Use an earlier restore point",
            "summary": "Lower consistency risk with a larger data-loss window.",
            "recommendation_level": "alternative",
            "risk_level": "low",
            "restore_scope": "database restore on alternate host with earlier point",
            "rpo": "10 to 15 minutes",
            "rto": "about 1.8 hours",
            "target": "Alternate MySQL recovery environment",
            "impact_summary": "Safer replay boundary but older business data.",
            "execution_steps": [
                "Provision alternate host",
                "Restore earlier snapshot",
                "Validate historical delta",
                "Import target table",
            ],
            "validation_checks": [
                "business approval for older point",
                "data reconciliation",
            ],
            "business_window": "longer reconciliation window",
        },
        {
            "candidate_option_id": f"candidate-{restore_point}-fast",
            "title": "Restore directly on production host",
            "summary": "Shortest recovery time but requires a stronger write freeze.",
            "recommendation_level": "alternative",
            "risk_level": "high",
            "restore_scope": "direct host-level restore and point-in-time replay",
            "rpo": "< 1 minute",
            "rto": "about 45 minutes",
            "target": "Production database host",
            "impact_summary": "Fastest route but highest operational risk to live traffic.",
            "execution_steps": [
                "Freeze writes",
                "Replay target point",
                "Run integrity checks",
                "Resume traffic",
            ],
            "validation_checks": [
                "strict freeze confirmation",
                "rollback plan ready",
            ],
            "business_window": "requires longer write freeze",
        },
    ]


def _document_candidate_compare_candidates() -> list[dict[str, Any]]:
    return [
        {
            "candidate_option_id": "candidate_option_a",
            "title": "Plan A: alternate-host database restore plus table import",
            "summary": "Recommended because it limits production impact and preserves table scope.",
            "recommendation_level": "recommended",
            "risk_level": "medium",
            "restore_scope": "database-level restore with table-level final import",
            "rpo": "< 2 minutes",
            "rto": "about 1.5 hours",
            "target": "Alternate MySQL recovery environment",
            "impact_summary": "Protects unrelated production objects from accidental overwrite.",
            "execution_steps": [
                "Restore to alternate host",
                "Export target table",
                "Validate",
                "Import into production",
            ],
            "validation_checks": ["schema diff", "row count", "smoke test"],
            "business_window": "brief write freeze at import",
        },
        {
            "candidate_option_id": "candidate_option_b",
            "title": "Plan B: same-host point-in-time restore",
            "summary": "Fastest path but requires a longer production write freeze.",
            "recommendation_level": "alternative",
            "risk_level": "high",
            "restore_scope": "same-host point-in-time restore",
            "rpo": "< 1 minute",
            "rto": "about 50 minutes",
            "target": "Production MySQL host",
            "impact_summary": "Shortest duration but highest interruption risk.",
            "execution_steps": [
                "Freeze writes",
                "Restore in place",
                "Validate consistency",
                "Reopen traffic",
            ],
            "validation_checks": ["freeze approval", "rollback checkpoint"],
            "business_window": "extended write freeze",
        },
        {
            "candidate_option_id": "candidate_option_c",
            "title": "Plan C: export from standby copy",
            "summary": "Lowest operational risk, with slower data validation.",
            "recommendation_level": "alternative",
            "risk_level": "low",
            "restore_scope": "standby export and targeted backfill",
            "rpo": "5 to 8 minutes",
            "rto": "about 2 hours",
            "target": "Standby copy and staging import path",
            "impact_summary": "Minimal production touch until final import phase.",
            "execution_steps": [
                "Export from standby",
                "Stage transformed data",
                "Validate records",
                "Import selected rows",
            ],
            "validation_checks": ["data diff", "business acceptance"],
            "business_window": "lowest runtime impact",
        },
    ]


def _report_detail_candidates(suffix: str) -> list[dict[str, Any]]:
    return [
        {
            "candidate_option_id": f"report-candidate-{suffix}-a",
            "title": "Plan A: report-backed alternate-host restore",
            "summary": "Recommended execution path derived from the feasibility report.",
            "recommendation_level": "recommended",
            "risk_level": "medium",
            "restore_scope": "database restore on alternate host with controlled import",
            "rpo": "< 2 minutes",
            "rto": "1 hour 25 minutes",
            "target": "2026-04-24 09:28",
            "impact_summary": "Balances execution speed and data-safety guardrails.",
            "execution_steps": [
                "Prepare alternate host",
                "Restore target instance",
                "Export order_details",
                "Validate and import",
            ],
            "validation_checks": ["integrity validation", "business owner sign-off"],
            "business_window": "minimal production interruption",
        },
        {
            "candidate_option_id": f"report-candidate-{suffix}-b",
            "title": "Plan B: earlier restore point with extra verification",
            "summary": "Safer but older point if data consistency is prioritized over freshness.",
            "recommendation_level": "alternative",
            "risk_level": "low",
            "restore_scope": "earlier alternate-host restore",
            "rpo": "12 minutes",
            "rto": "1 hour 40 minutes",
            "target": "2026-04-24 09:16",
            "impact_summary": "Lower integrity risk but larger business data gap.",
            "execution_steps": [
                "Restore earlier point",
                "Run reconciliation",
                "Validate rows",
                "Import approved dataset",
            ],
            "validation_checks": ["reconciliation review", "approval checkpoint"],
            "business_window": "moderate interruption",
        },
        {
            "candidate_option_id": f"report-candidate-{suffix}-c",
            "title": "Plan C: direct production replay",
            "summary": "Fastest report option but requires the strongest operational controls.",
            "recommendation_level": "alternative",
            "risk_level": "high",
            "restore_scope": "direct production replay",
            "rpo": "< 1 minute",
            "rto": "55 minutes",
            "target": "production replay window",
            "impact_summary": "High speed with elevated operational sensitivity.",
            "execution_steps": [
                "Freeze writes",
                "Replay target point",
                "Validate critical queries",
                "Resume traffic",
            ],
            "validation_checks": ["rollback ready", "lead approval"],
            "business_window": "largest operational constraint",
        },
    ]


def _candidate_actions(
    candidates: list[dict[str, Any]],
    reasoning_trace_id: str,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_id = str(candidate["candidate_option_id"])
        actions.append(
            _action(
                f"choose_{candidate_id}",
                "submit_message",
                f"Choose {candidate['title']}",
                payload={
                    "reasoningTraceId": reasoning_trace_id,
                    "candidateOptionId": candidate_id,
                    "action": "confirm",
                },
                style="primary" if candidate is candidates[0] else None,
            )
        )
        actions.append(
            _action(
                f"view_{candidate_id}_detail",
                "open_ref",
                f"Open details for {candidate['title']}",
                payload={"refId": f"{candidate_id}-detail"},
            )
        )
    return actions


def _activity(
    *,
    message_id: str,
    block_id: str,
    ui: dict[str, Any],
    meta: dict[str, Any],
    actions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    content: dict[str, Any] = {
        "contract": LAYOUT_TREE_CONTRACT,
        "blockId": block_id,
        "ui": ui,
        "meta": meta,
    }
    if actions:
        content["actions"] = actions
    return {
        "type": "ACTIVITY_SNAPSHOT",
        "messageId": message_id,
        "activityType": LAYOUT_TREE_ACTIVITY_TYPE,
        "content": content,
    }


def _activity_delta(*, message_id: str, patch: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "type": "ACTIVITY_DELTA",
        "messageId": message_id,
        "activityType": LAYOUT_TREE_ACTIVITY_TYPE,
        "patch": patch,
    }


def _state(
    *,
    active_block_ids: list[str] | None = None,
    selection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state: dict[str, Any] = {}
    if active_block_ids is not None:
        state["view"] = {"activeBlockIds": active_block_ids}
    if selection is not None:
        state["selection"] = selection
    return {"type": "STATE_SNAPSHOT", "state": state}


def _state_delta(delta: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "STATE_DELTA", "delta": delta}


def _action(
    action_id: str,
    kind: str,
    label: str,
    *,
    payload: dict[str, Any] | None = None,
    style: str | None = None,
) -> dict[str, Any]:
    action: dict[str, Any] = {"id": action_id, "kind": kind, "label": label}
    if payload is not None:
        action["payload"] = payload
    if style is not None:
        action["style"] = style
    return action


def _candidate_compare_ui(
    candidates: list[dict[str, Any]],
    *,
    heading: str,
    subtitle: str,
) -> dict[str, Any]:
    cards = []
    for candidate in candidates:
        candidate_id = str(candidate["candidate_option_id"])
        cards.append(
            _card(
                "",
                [
                    _heading(str(candidate["title"]), level=3),
                    _badge_row(
                        [
                            {
                                "tone": "positive"
                                if candidate["recommendation_level"] == "recommended"
                                else "neutral",
                                "text": candidate["recommendation_level"],
                            },
                            {
                                "tone": "warning"
                                if candidate["risk_level"] in {"medium", "high"}
                                else "positive",
                                "text": candidate["risk_level"],
                            },
                        ]
                    ),
                    _paragraph(str(candidate["summary"])),
                    _metric_list(
                        [
                            {"label": "RPO", "value": str(candidate["rpo"])},
                            {"label": "RTO", "value": str(candidate["rto"])},
                            {"label": "Window", "value": str(candidate["business_window"])},
                        ]
                    ),
                    _kv_list(
                        [
                            {"label": "Scope", "value": str(candidate["restore_scope"])},
                            {"label": "Target", "value": str(candidate["target"])},
                            {
                                "label": "Validation",
                                "value": ", ".join(candidate["validation_checks"][:2]),
                            },
                        ]
                    ),
                    _callout(
                        "info",
                        "Business impact",
                        str(candidate["impact_summary"]),
                    ),
                    _action_row(
                        [f"choose_{candidate_id}", f"view_{candidate_id}_detail"]
                    ),
                ],
                node_id=candidate_id,
            )
        )

    return _stack(
        [
            _section(
                [
                    _heading(heading, level=2),
                    _paragraph(subtitle),
                ],
                node_id="page_header",
            ),
            _grid(cards, columns=3),
        ],
        gap="lg",
    )


def _stack(children: list[dict[str, Any]], *, gap: str = "md") -> dict[str, Any]:
    return {"type": "stack", "props": {"gap": gap}, "children": children}


def _section(children: list[dict[str, Any]], *, node_id: str | None = None) -> dict[str, Any]:
    node: dict[str, Any] = {"type": "section", "children": children}
    if node_id is not None:
        node["id"] = node_id
    return node


def _grid(children: list[dict[str, Any]], *, columns: int) -> dict[str, Any]:
    return {"type": "grid", "props": {"columns": columns, "gap": "md"}, "children": children}


def _card(title: str, children: list[dict[str, Any]], *, node_id: str | None = None) -> dict[str, Any]:
    node: dict[str, Any] = {
        "type": "card",
        "children": children,
    }
    if title:
        node["props"] = {"title": title}
    if node_id is not None:
        node["id"] = node_id
    return node


def _heading(text: str, *, level: int = 3) -> dict[str, Any]:
    return {"type": "heading", "props": {"level": level, "text": text}}


def _paragraph(text: str) -> dict[str, Any]:
    return {"type": "paragraph", "props": {"text": text}}


def _markdown(text: str) -> dict[str, Any]:
    return {"type": "markdown", "props": {"text": text}}


def _badge_row(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "badge-row", "props": {"items": items}}


def _kv_list(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "kv-list", "props": {"items": items}}


def _metric_list(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "metric-list", "props": {"items": items}}


def _chart(
    chart_type: str,
    data: list[dict[str, Any]] | None = None,
    *,
    x_axis: list[str] | None = None,
    series: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    props: dict[str, Any] = {"chartType": chart_type}
    if data is not None:
        props["data"] = data
    if x_axis is not None:
        props["xAxis"] = x_axis
    if series is not None:
        props["series"] = series
    props["items"] = _chart_items(data=data, x_axis=x_axis, series=series)
    return {"type": "chart", "props": props}


def _data_table(
    columns: list[dict[str, str]],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    return {"type": "data-table", "props": {"columns": columns, "rows": rows}}


def _attachment_list(items: list[dict[str, Any]]) -> dict[str, Any]:
    return {"type": "attachment-list", "props": {"items": items}}


def _action_row(action_ids: list[str]) -> dict[str, Any]:
    return {"type": "action-row", "props": {"actionIds": action_ids}}


def _callout(tone: str, title: str, text: str) -> dict[str, Any]:
    return {"type": "callout", "props": {"tone": tone, "title": title, "text": text}}


def _chart_items(
    *,
    data: list[dict[str, Any]] | None,
    x_axis: list[str] | None,
    series: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    if data:
        items: list[dict[str, Any]] = []
        for index, row in enumerate(data):
            if not isinstance(row, dict):
                continue
            label = row.get("label") or row.get("name") or row.get("x") or f"Point {index + 1}"
            value = row.get("value")
            if value is None:
                numeric_values = [
                    candidate
                    for key, candidate in row.items()
                    if key not in {"label", "name", "x"} and isinstance(candidate, (int, float))
                ]
                value = numeric_values[0] if numeric_values else 0
            items.append({"label": str(label), "value": value})
        return items

    if x_axis and series:
        first_series = next((entry for entry in series if isinstance(entry, dict)), None)
        values = list(first_series.get("data", [])) if first_series is not None else []
        return [
            {"label": str(label), "value": values[index] if index < len(values) else 0}
            for index, label in enumerate(x_axis)
        ]

    if series:
        items = []
        for index, entry in enumerate(series):
            if not isinstance(entry, dict):
                continue
            values = entry.get("data", [])
            total = sum(value for value in values if isinstance(value, (int, float)))
            items.append({"label": str(entry.get("name") or f"Series {index + 1}"), "value": total})
        return items

    return []
