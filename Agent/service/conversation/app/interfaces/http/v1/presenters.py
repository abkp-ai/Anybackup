from datetime import UTC, datetime
from typing import Any, cast

from app.application.models.conversation import (
    ConversationDetailResult,
    ConversationListResult,
    ConversationMessageListResult,
    ConversationMessageRecord,
    ConversationRecord,
    ConversationStatusEventListResult,
    ConversationStatusEventRecord,
    MessageAcceptedResult,
    Page,
)
from app.application.models.writeback import (
    ConversationCandidateSelectionRecord,
    ConversationContextResult,
    ConversationContextSnapshotRecord,
    ConversationReasoningTraceRecord,
)
from app.application.use_cases.reasoning import (
    CandidateSelectionResult,
    ReasoningTraceListResult,
    visible_reasoning_payload,
)
from app.interfaces.http.v1.schemas import (
    CandidateSelectionAcceptedResponse,
    CandidateSelectionResponse,
    ConversationContextPanelResponse,
    ConversationContextResponse,
    ConversationContextSnapshotResponse,
    ConversationDetailResponse,
    ConversationEventsResponse,
    ConversationListResponse,
    ConversationMessageResponse,
    ConversationResponse,
    ConversationRetentionPolicy,
    ConversationStatusEventResponse,
    MessageAcceptedResponse,
    MessageListResponse,
    PageMeta,
    ReasoningTraceListResponse,
    ReasoningTraceResponse,
)


def message_accepted_to_response(result: MessageAcceptedResult) -> MessageAcceptedResponse:
    return MessageAcceptedResponse(
        message=message_to_response(result.message),
        conversation=conversation_to_response(result.conversation),
        status_event=status_event_to_response(result.status_event),
        next_poll_after_ms=result.next_poll_after_ms,
    )


def conversation_list_to_response(result: ConversationListResult) -> ConversationListResponse:
    return ConversationListResponse(
        items=[conversation_to_response(item) for item in result.items],
        page=page_to_response(result.page),
    )


def message_list_to_response(result: ConversationMessageListResult) -> MessageListResponse:
    return MessageListResponse(
        items=[message_to_response(item) for item in result.items],
        page=page_to_response(result.page),
    )


def event_list_to_response(result: ConversationStatusEventListResult) -> ConversationEventsResponse:
    return ConversationEventsResponse(
        items=[status_event_to_response(item) for item in result.items],
        page=page_to_response(result.page),
        latest_sequence=result.latest_sequence,
        recommended_poll_interval_ms=result.recommended_poll_interval_ms,
    )


def context_to_response(result: ConversationContextResult) -> ConversationContextResponse:
    return ConversationContextResponse(
        conversation_id=str(result.conversation_id),
        snapshot=(
            context_snapshot_to_response(result.snapshot)
            if result.snapshot is not None
            else None
        ),
        pending_delta_count=result.pending_delta_count,
        panel=_context_panel_to_response(result),
    )


def context_snapshot_to_response(
    record: ConversationContextSnapshotRecord,
) -> ConversationContextSnapshotResponse:
    return ConversationContextSnapshotResponse(
        context_snapshot_id=str(record.context_snapshot_id),
        conversation_id=str(record.conversation_id),
        snapshot_version=record.snapshot_version,
        short_summary=record.short_summary,
        structured_state=_visible_structured_state(record.structured_state),
        last_message_id=str(record.last_message_id) if record.last_message_id is not None else None,
        status=cast(Any, record.status),
        created_by=record.created_by,
        trace_id=record.trace_id,
        created_at=_ms_to_iso(record.created_time),
        updated_at=_ms_to_iso(record.updated_time),
    )


def _context_panel_to_response(
    result: ConversationContextResult,
) -> ConversationContextPanelResponse | None:
    if result.snapshot is None:
        return None
    state = _visible_structured_state(result.snapshot.structured_state)
    key_variables = state.get("key_variables")
    if not isinstance(key_variables, dict):
        key_variables = {
            key: value
            for key, value in state.items()
            if key
            not in {
                "confirmed_facts",
                "pending_questions",
                "current_candidates",
                "next_actions",
                "latest_reasoning_summary",
                "memory_refs",
            }
        }
    return ConversationContextPanelResponse(
        short_summary=result.snapshot.short_summary,
        scenario_binding=(
            _visible_scenario_binding(result.conversation.scenario_binding)
            if result.conversation is not None
            else None
        ),
        key_variables=cast(dict[str, object], key_variables),
        confirmed_facts=_list_value(state.get("confirmed_facts")),
        pending_questions=_list_value(state.get("pending_questions")),
        current_candidates=_dict_list_value(state.get("current_candidates")),
        next_actions=_list_value(state.get("next_actions")),
        latest_reasoning_summary=cast(str | None, state.get("latest_reasoning_summary")),
        memory_refs=_dict_list_value(state.get("memory_refs")),
        summary_status=_summary_status(result.snapshot.status),
        snapshot_version=result.snapshot.snapshot_version,
        updated_at=_ms_to_iso(result.snapshot.updated_time),
    )


def _visible_structured_state(raw_state: dict[str, Any]) -> dict[str, object]:
    blocked_keys = {
        "internal_reasoning",
        "chain_of_thought",
        "system_prompt",
        "prompt",
        "raw_tool_output",
        "stack_trace",
    }
    return {
        key: value
        for key, value in raw_state.items()
        if key not in blocked_keys and not key.startswith("_")
    }


def _visible_scenario_binding(
    raw_value: dict[str, Any] | None,
) -> dict[str, object] | None:
    if raw_value is None:
        return None
    allowed_keys = {
        "scenario_id",
        "scenario_name",
        "task_type",
        "asset_refs",
        "business_refs",
        "preferences",
        "reusable_preferences",
    }
    visible = {
        key: value
        for key, value in raw_value.items()
        if key in allowed_keys and value is not None
    }
    return visible or None


def _list_value(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _dict_list_value(value: object) -> list[dict[str, object]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _summary_status(status: str) -> str:
    if status == "current":
        return "fresh"
    return status


def reasoning_trace_list_to_response(
    result: ReasoningTraceListResult,
) -> ReasoningTraceListResponse:
    return ReasoningTraceListResponse(
        items=[reasoning_trace_to_response(item) for item in result.items],
        page=page_to_response(result.page),
    )


def reasoning_trace_to_response(record: ConversationReasoningTraceRecord) -> ReasoningTraceResponse:
    payload = visible_reasoning_payload(record)
    return ReasoningTraceResponse(
        reasoning_trace_id=str(record.reasoning_trace_id),
        conversation_id=str(record.conversation_id),
        source_message_id=str(record.source_message_id)
        if record.source_message_id is not None
        else None,
        objective=cast(str | None, payload.get("objective")),
        decision_summary=cast(str | None, payload.get("decision_summary")),
        comparison_dimensions=cast(list[str], payload.get("comparison_dimensions") or []),
        candidates=cast(list[dict[str, object]], payload.get("candidates") or []),
        recommendation=cast(str | None, payload.get("recommendation")),
        recommended_candidate_option_id=cast(
            str | None,
            payload.get("recommended_candidate_option_id"),
        ),
        pending_confirmations=cast(
            list[dict[str, object]],
            payload.get("pending_confirmations") or [],
        ),
        created_by_agent=record.created_by_agent,
        core_agent_run_id=record.core_agent_run_id,
        trace_id=record.trace_id,
        created_at=_ms_to_iso(record.created_time),
    )


def candidate_selection_to_response(
    result: CandidateSelectionResult,
) -> CandidateSelectionAcceptedResponse:
    return CandidateSelectionAcceptedResponse(
        selection=_candidate_selection_record_to_response(result.selection),
        idempotent=result.idempotent,
    )


def _candidate_selection_record_to_response(
    record: ConversationCandidateSelectionRecord,
) -> CandidateSelectionResponse:
    return CandidateSelectionResponse(
        selection_id=str(record.selection_id),
        conversation_id=str(record.conversation_id),
        reasoning_trace_id=str(record.reasoning_trace_id),
        candidate_option_id=record.candidate_option_id,
        action=cast(Any, record.action),
        comment=record.comment,
        created_by_user_id=record.created_by_user_id,
        trace_id=record.trace_id,
        correlation_id=record.correlation_id,
        created_at=_ms_to_iso(record.created_time),
    )


def conversation_detail_to_response(result: ConversationDetailResult) -> ConversationDetailResponse:
    conversation = conversation_to_response(result.conversation)
    return ConversationDetailResponse(
        **conversation.model_dump(mode="json"),
        context=result.context,
        latest_messages=[message_to_response(message) for message in result.latest_messages],
        latest_events=[status_event_to_response(event) for event in result.latest_events],
    )


def conversation_to_response(record: ConversationRecord) -> ConversationResponse:
    return ConversationResponse(
        conversation_id=str(record.conversation_id),
        owner_user_id=record.owner_user_id,
        title=record.title,
        status=record.status.value,
        summary=record.summary,
        scenario_binding=record.scenario_binding,
        tags=list(record.tags),
        latest_message_summary=record.latest_message_summary,
        active_run_id=record.active_run_id,
        has_active_run=record.active_run_id is not None,
        created_at=_ms_to_iso(record.created_time),
        updated_at=_ms_to_iso(record.updated_time),
        last_active_at=_ms_to_iso(record.last_active_time),
        archived_at=_optional_ms_to_iso(record.archived_time),
        archived_by=cast(Any, record.archived_by),
        archive_reason=record.archive_reason,
        retention_policy=ConversationRetentionPolicy(policy_id=record.retention_policy),
        legal_hold=record.legal_hold,
        expires_at=_optional_ms_to_iso(record.expires_time),
        expired_at=_optional_ms_to_iso(record.expired_time),
    )


def message_to_response(record: ConversationMessageRecord) -> ConversationMessageResponse:
    return ConversationMessageResponse(
        message_id=str(record.message_id),
        conversation_id=str(record.conversation_id),
        parent_message_id=(
            str(record.parent_message_id) if record.parent_message_id is not None else None
        ),
        turn_id=str(record.turn_id) if record.turn_id is not None else None,
        client_message_id=record.client_message_id,
        role=cast(Any, record.role),
        content_type=cast(Any, record.content_type),
        content=record.content,
        rich_payload=record.rich_payload,
        status=record.status.value,
        error_code=record.error_code,
        error_message=None,
        reasoning_trace_id=None,
        trace_id=record.trace_id,
        correlation_id=record.correlation_id,
        created_at=_ms_to_iso(record.created_time),
        updated_at=_ms_to_iso(record.updated_time),
    )


def status_event_to_response(
    record: ConversationStatusEventRecord,
) -> ConversationStatusEventResponse:
    return ConversationStatusEventResponse(
        status_event_id=str(record.status_event_id),
        conversation_id=str(record.conversation_id),
        message_id=str(record.message_id) if record.message_id is not None else None,
        turn_id=str(record.turn_id) if record.turn_id is not None else None,
        event_type=cast(Any, record.event_type),
        sequence=record.sequence,
        message_status=record.message_status.value if record.message_status is not None else None,
        title=record.title,
        detail=record.detail,
        payload=record.payload,
        rich_payload=record.rich_payload,
        trace_id=record.trace_id,
        correlation_id=record.correlation_id,
        occurred_at=_ms_to_iso(record.created_time),
        created_at=_ms_to_iso(record.created_time),
    )


def page_to_response(page: Page) -> PageMeta:
    return PageMeta(next_cursor=page.next_cursor, has_more=page.has_more, limit=page.limit)


def _optional_ms_to_iso(value: int | None) -> str | None:
    if value is None:
        return None
    return _ms_to_iso(value)


def _ms_to_iso(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, UTC).isoformat().replace("+00:00", "Z")
