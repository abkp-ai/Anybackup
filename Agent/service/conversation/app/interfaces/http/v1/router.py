from datetime import UTC, datetime
from typing import Annotated, Any, cast

from fastapi import (
    APIRouter,
    Body,
    Depends,
    Header,
    HTTPException,
    Query,
    Request,
    status,
)

from app.application.commands.config import (
    CopyConversationConfigCommand,
    UpdateConversationCommand,
)
from app.application.commands.reasoning import CandidateSelectionCommand
from app.application.models.conversation import (
    AuthenticatedUser,
    ConversationListQuery,
    ConversationMessageListQuery,
    ConversationRecord,
)
from app.application.use_cases.reasoning import CandidateSelectionResult
from app.domain.conversation import ConversationStatus
from app.domain.message import MessageStatus
from app.interfaces.http.v1.command_mapping import (
    build_create_conversation_command,
    build_send_clarification_response_command,
    build_send_user_message_command,
)
from app.interfaces.http.v1.dependencies import (
    require_user_context,
)
from app.interfaces.http.v1.presenters import (
    candidate_selection_to_response,
    context_to_response,
    conversation_detail_to_response,
    conversation_list_to_response,
    conversation_to_response,
    event_list_to_response,
    message_accepted_to_response,
    message_list_to_response,
    reasoning_trace_list_to_response,
)
from app.interfaces.http.v1.schemas import (
    ERROR_RESPONSES,
    CandidateSelectionAcceptedResponse,
    CandidateSelectionMessageRequest,
    CandidateSelectionRequest,
    ClarificationResponseRequest,
    ConversationArchiveRequest,
    ConversationContextResponse,
    ConversationDetailResponse,
    ConversationEventsResponse,
    ConversationLegalHoldRequest,
    ConversationListResponse,
    ConversationMessageCreateRequest,
    ConversationMessageResponse,
    ConversationResponse,
    ConversationRestoreRequest,
    ConversationStatusEventResponse,
    CopyConversationConfigRequest,
    CreateConversationRequest,
    MessageAcceptedResponse,
    MessageListResponse,
    ReasoningTraceListResponse,
    UpdateConversationRequest,
    UserMessageRequest,
)

router = APIRouter(tags=["Conversations"], responses=ERROR_RESPONSES)


@router.get(
    "/skill-manifest",
    operation_id="getSkillManifest",
    tags=["Skill"],
)
async def get_skill_manifest(request: Request) -> dict[str, Any]:
    handler = request.app.state.container.get_skill_manifest_handler()
    return cast(dict[str, Any], await handler.handle())


@router.post(
    "/conversations",
    operation_id="createConversation",
    status_code=status.HTTP_201_CREATED,
    response_model=MessageAcceptedResponse,
)
async def create_conversation(
    request: Request,
    payload: CreateConversationRequest,
    user: Annotated[AuthenticatedUser, Depends(require_user_context)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    request_id: Annotated[str | None, Header(alias="X-Request-Id")] = None,
) -> MessageAcceptedResponse:
    command = build_create_conversation_command(
        request=payload,
        idempotency_key_header=idempotency_key,
        request_id=request_id,
    )
    handler = request.app.state.container.create_conversation_handler()
    result = await handler.handle(command, user)
    return message_accepted_to_response(result)


@router.get(
    "/conversations",
    operation_id="listConversations",
    response_model=ConversationListResponse,
)
async def list_conversations(
    request: Request,
    user: Annotated[AuthenticatedUser, Depends(require_user_context)],
    keyword: Annotated[str | None, Query(max_length=120)] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    archived: bool = False,
    scenario_id: Annotated[str | None, Query(max_length=80)] = None,
    task_type: Annotated[str | None, Query(max_length=80)] = None,
    tag: Annotated[str | None, Query(max_length=200)] = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
    last_active_after: datetime | None = None,
    last_active_before: datetime | None = None,
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: Annotated[
        str,
        Query(
            pattern=(
                "^(last_active_desc|last_active_asc|created_desc|created_asc|"
                "updated_desc|updated_asc)$"
            )
        ),
    ] = "last_active_desc",
) -> ConversationListResponse:
    query = ConversationListQuery(
        keyword=keyword,
        statuses=_parse_statuses(status_filter),
        archived=archived,
        scenario_id=scenario_id,
        task_type=task_type,
        tags=_parse_csv_values(tag),
        created_after_time=_datetime_to_ms(created_after),
        created_before_time=_datetime_to_ms(created_before),
        last_active_after_time=_datetime_to_ms(last_active_after),
        last_active_before_time=_datetime_to_ms(last_active_before),
        cursor=cursor,
        limit=limit,
        sort=sort,
    )
    handler = request.app.state.container.list_conversations_handler()
    result = await handler.handle(query, user)
    return conversation_list_to_response(result)


@router.get(
    "/conversations/{conversation_id}",
    operation_id="getConversation",
    response_model=ConversationDetailResponse,
)
async def get_conversation(
    request: Request,
    conversation_id: str,
    user: Annotated[AuthenticatedUser, Depends(require_user_context)],
    include_latest_messages: bool = True,
    latest_message_limit: Annotated[int, Query(ge=1, le=50)] = 20,
    include_context: bool = True,
    include_latest_events: bool = True,
) -> ConversationDetailResponse:
    del include_context
    handler = request.app.state.container.get_conversation_handler()
    result = await handler.handle(
        _parse_int_id(conversation_id),
        user,
        include_latest_messages=include_latest_messages,
        latest_message_limit=latest_message_limit,
        include_latest_events=include_latest_events,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation_detail_to_response(result)


@router.patch(
    "/conversations/{conversation_id}",
    operation_id="updateConversation",
    response_model=ConversationResponse,
)
async def update_conversation(
    request: Request,
    conversation_id: str,
    payload: UpdateConversationRequest,
    user: Annotated[AuthenticatedUser, Depends(require_user_context)],
    request_id: Annotated[str | None, Header(alias="X-Request-Id")] = None,
) -> ConversationResponse:
    command = UpdateConversationCommand(
        conversation_id=_parse_int_id(conversation_id),
        title=payload.title,
        request_id=request_id,
    )
    handler = request.app.state.container.update_conversation_handler()
    result = await handler.handle(command, user)
    if result is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation_to_response(result)


@router.post(
    "/conversations/{conversation_id}/archive",
    operation_id="archiveConversation",
    response_model=ConversationResponse,
)
async def archive_conversation(
    request: Request,
    conversation_id: str,
    user: Annotated[AuthenticatedUser, Depends(require_user_context)],
    payload: Annotated[ConversationArchiveRequest | None, Body()] = None,
) -> ConversationResponse:
    handler = request.app.state.container.archive_conversation_handler()
    result = await handler.handle(
        _parse_int_id(conversation_id),
        user,
        reason=payload.reason if payload is not None else None,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation_to_response(result)


@router.post(
    "/conversations/{conversation_id}/restore",
    operation_id="restoreConversation",
    response_model=ConversationResponse,
)
async def restore_conversation(
    request: Request,
    conversation_id: str,
    user: Annotated[AuthenticatedUser, Depends(require_user_context)],
    payload: Annotated[ConversationRestoreRequest | None, Body()] = None,
) -> ConversationResponse:
    handler = request.app.state.container.restore_conversation_handler()
    result = await handler.handle(
        _parse_int_id(conversation_id),
        user,
        reason=payload.reason if payload is not None else None,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation_to_response(result)


@router.post(
    "/conversations/{conversation_id}/legal-hold",
    operation_id="setConversationLegalHold",
    response_model=ConversationResponse,
)
async def set_conversation_legal_hold(
    request: Request,
    conversation_id: str,
    payload: ConversationLegalHoldRequest,
    user: Annotated[AuthenticatedUser, Depends(require_user_context)],
) -> ConversationResponse:
    handler = request.app.state.container.set_legal_hold_handler()
    result = await handler.handle(
        _parse_int_id(conversation_id),
        user,
        enabled=payload.enabled,
        reason=payload.reason,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation_to_response(result)


@router.post(
    "/conversations/{conversation_id}/copy-config",
    operation_id="copyConversationConfig",
    status_code=status.HTTP_201_CREATED,
    response_model=ConversationDetailResponse,
)
async def copy_conversation_config(
    request: Request,
    conversation_id: str,
    user: Annotated[AuthenticatedUser, Depends(require_user_context)],
    payload: Annotated[CopyConversationConfigRequest | None, Body()] = None,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    request_id: Annotated[str | None, Header(alias="X-Request-Id")] = None,
) -> ConversationDetailResponse:
    command = CopyConversationConfigCommand(
        source_conversation_id=_parse_int_id(conversation_id),
        title=payload.title if payload is not None else None,
        copy_tags=payload.copy_tags if payload is not None else True,
        copy_scenario_binding=payload.copy_scenario_binding if payload is not None else True,
        additional_tags=tuple(payload.additional_tags if payload is not None else ()),
        idempotency_key=idempotency_key,
        request_id=request_id,
    )
    handler = request.app.state.container.copy_conversation_config_handler()
    result = await handler.handle(command, user)
    if result is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation_detail_to_response(result)


@router.post(
    "/conversations/{conversation_id}/messages",
    operation_id="createConversationMessage",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=MessageAcceptedResponse,
)
async def create_conversation_message(
    request: Request,
    conversation_id: str,
    payload: ConversationMessageCreateRequest,
    user: Annotated[AuthenticatedUser, Depends(require_user_context)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    request_id: Annotated[str | None, Header(alias="X-Request-Id")] = None,
) -> MessageAcceptedResponse:
    parsed_conversation_id = _parse_int_id(conversation_id)
    if isinstance(payload, UserMessageRequest):
        command = build_send_user_message_command(
            conversation_id=parsed_conversation_id,
            request=payload,
            idempotency_key_header=idempotency_key,
            request_id=request_id,
        )
        handler = request.app.state.container.send_user_message_handler()
        result = await handler.handle(command, user)
        if result is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return message_accepted_to_response(result)

    if isinstance(payload, ClarificationResponseRequest):
        command = build_send_clarification_response_command(
            conversation_id=parsed_conversation_id,
            request=payload,
            idempotency_key_header=idempotency_key,
            request_id=request_id,
        )
        handler = request.app.state.container.send_user_message_handler()
        result = await handler.handle(command, user)
        if result is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        return message_accepted_to_response(result)

    return await _accept_candidate_selection_message(
        request=request,
        conversation_id=parsed_conversation_id,
        payload=payload,
        user=user,
        idempotency_key=idempotency_key,
        request_id=request_id,
    )


@router.get(
    "/conversations/{conversation_id}/messages",
    operation_id="listConversationMessages",
    response_model=MessageListResponse,
)
async def list_conversation_messages(
    request: Request,
    conversation_id: str,
    user: Annotated[AuthenticatedUser, Depends(require_user_context)],
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    role: Annotated[
        str | None,
        Query(pattern="^(user|assistant|system|status)$"),
    ] = None,
    content_type: Annotated[
        str | None,
        Query(pattern="^(text|clarification|rich_content|status)$"),
    ] = None,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    created_after: datetime | None = None,
    created_before: datetime | None = None,
) -> MessageListResponse:
    query = ConversationMessageListQuery(
        conversation_id=_parse_int_id(conversation_id),
        cursor=cursor,
        limit=limit,
        role=role,
        content_type=content_type,
        status=_parse_message_status(status_filter),
        created_after_time=_datetime_to_ms(created_after),
        created_before_time=_datetime_to_ms(created_before),
    )
    handler = request.app.state.container.list_conversation_messages_handler()
    result = await handler.handle(query, user)
    if result is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return message_list_to_response(result)


@router.get(
    "/conversations/{conversation_id}/context",
    operation_id="getConversationContext",
    response_model=ConversationContextResponse,
)
async def get_conversation_context(
    request: Request,
    conversation_id: str,
    user: Annotated[AuthenticatedUser, Depends(require_user_context)],
) -> ConversationContextResponse:
    handler = request.app.state.container.get_conversation_context_handler()
    result = await handler.handle(_parse_int_id(conversation_id), user)
    if result is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return context_to_response(result)


@router.get(
    "/conversations/{conversation_id}/reasoning-traces",
    operation_id="listConversationReasoningTraces",
    response_model=ReasoningTraceListResponse,
)
async def list_conversation_reasoning_traces(
    request: Request,
    conversation_id: str,
    user: Annotated[AuthenticatedUser, Depends(require_user_context)],
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ReasoningTraceListResponse:
    handler = request.app.state.container.list_reasoning_traces_handler()
    result = await handler.handle(_parse_int_id(conversation_id), user, limit=limit)
    if result is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return reasoning_trace_list_to_response(result)


@router.post(
    "/conversations/{conversation_id}/candidate-selections",
    operation_id="createCandidateSelection",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=CandidateSelectionAcceptedResponse,
)
async def create_candidate_selection(
    request: Request,
    conversation_id: str,
    payload: CandidateSelectionRequest,
    user: Annotated[AuthenticatedUser, Depends(require_user_context)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    request_id: Annotated[str | None, Header(alias="X-Request-Id")] = None,
) -> CandidateSelectionAcceptedResponse:
    if idempotency_key is None:
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")
    command = CandidateSelectionCommand(
        conversation_id=_parse_int_id(conversation_id),
        reasoning_trace_id=payload.reasoning_trace_id,
        candidate_option_id=payload.candidate_option_id,
        action=payload.action,
        comment=payload.comment,
        idempotency_key=idempotency_key,
        user_id=user.user_id,
        request_id=request_id,
    )
    handler = request.app.state.container.confirm_candidate_selection_handler()
    result = await handler.handle(command)
    return candidate_selection_to_response(result)


@router.get(
    "/conversations/{conversation_id}/events",
    operation_id="listConversationEvents",
    response_model=ConversationEventsResponse,
)
async def list_conversation_events(
    request: Request,
    conversation_id: str,
    user: Annotated[AuthenticatedUser, Depends(require_user_context)],
    cursor: Annotated[str | None, Query(max_length=512)] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> ConversationEventsResponse:
    handler = request.app.state.container.list_conversation_events_handler()
    result = await handler.handle(
        _parse_int_id(conversation_id),
        user,
        cursor=cursor,
        limit=limit,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return event_list_to_response(result)


def _parse_int_id(raw_value: str) -> int:
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found") from exc
    if value <= 0:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return value


async def _accept_candidate_selection_message(
    *,
    request: Request,
    conversation_id: int,
    payload: CandidateSelectionMessageRequest,
    user: AuthenticatedUser,
    idempotency_key: str | None,
    request_id: str | None,
) -> MessageAcceptedResponse:
    effective_idempotency_key = idempotency_key or payload.idempotency_key
    if effective_idempotency_key is None:
        raise HTTPException(status_code=400, detail="Idempotency-Key is required")

    command = CandidateSelectionCommand(
        conversation_id=conversation_id,
        reasoning_trace_id=payload.reasoning_trace_id,
        candidate_option_id=payload.candidate_option_id,
        action=payload.selection,
        comment=payload.additional_constraints,
        idempotency_key=effective_idempotency_key,
        user_id=user.user_id,
        request_id=request_id,
    )
    handler = request.app.state.container.confirm_candidate_selection_handler()
    result = await handler.handle(command)

    detail_handler = request.app.state.container.get_conversation_handler()
    detail = await detail_handler.handle(
        conversation_id,
        user,
        include_latest_messages=False,
        latest_message_limit=0,
        include_latest_events=False,
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    return MessageAcceptedResponse(
        message=_candidate_selection_message_response(payload, result),
        conversation=conversation_to_response(detail.conversation),
        status_event=_candidate_selection_status_event_response(
            conversation=detail.conversation,
            payload=payload,
            result=result,
        ),
        next_poll_after_ms=1000,
    )


def _candidate_selection_message_response(
    payload: CandidateSelectionMessageRequest,
    result: CandidateSelectionResult,
) -> ConversationMessageResponse:
    created_at = _ms_to_iso(result.selection.created_time)
    message_id = payload.message_id or str(result.selection.selection_id)
    return ConversationMessageResponse(
        message_id=message_id,
        conversation_id=str(result.selection.conversation_id),
        parent_message_id=payload.message_id,
        turn_id=None,
        client_message_id=payload.client_message_id,
        role="user",
        content_type="status",
        content=f"candidate_selection {payload.selection} {payload.candidate_option_id}",
        rich_payload=None,
        status="responded",
        error_code=None,
        error_message=None,
        reasoning_trace_id=payload.reasoning_trace_id,
        trace_id=result.selection.trace_id,
        correlation_id=result.selection.correlation_id,
        created_at=created_at,
        updated_at=None,
    )


def _candidate_selection_status_event_response(
    *,
    conversation: ConversationRecord,
    payload: CandidateSelectionMessageRequest,
    result: CandidateSelectionResult,
) -> ConversationStatusEventResponse:
    created_at = _ms_to_iso(result.selection.created_time)
    return ConversationStatusEventResponse(
        status_event_id=str(result.selection.selection_id),
        conversation_id=str(conversation.conversation_id),
        message_id=payload.message_id,
        turn_id=None,
        event_type="message.updated",
        sequence=0,
        message_status="responded",
        title="Candidate selection accepted",
        detail="Candidate selection accepted",
        payload={
            "selection_id": str(result.selection.selection_id),
            "reasoning_trace_id": payload.reasoning_trace_id,
            "candidate_option_id": payload.candidate_option_id,
            "selection": payload.selection,
        },
        rich_payload=None,
        trace_id=result.selection.trace_id,
        correlation_id=result.selection.correlation_id,
        occurred_at=created_at,
        created_at=created_at,
    )


def _ms_to_iso(value: int) -> str:
    return datetime.fromtimestamp(value / 1000, UTC).isoformat().replace("+00:00", "Z")


def _parse_statuses(raw_value: str | None) -> tuple[ConversationStatus, ...]:
    values = _parse_csv_values(raw_value)
    statuses: list[ConversationStatus] = []
    for value in values:
        try:
            statuses.append(ConversationStatus(value))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid conversation status") from exc
    return tuple(statuses)


def _parse_message_status(raw_value: str | None) -> MessageStatus | None:
    if raw_value is None:
        return None
    try:
        return MessageStatus(raw_value)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid message status") from exc


def _parse_csv_values(raw_value: str | None) -> tuple[str, ...]:
    if raw_value is None:
        return ()
    return tuple(value.strip() for value in raw_value.split(",") if value.strip())


def _datetime_to_ms(value: datetime | None) -> int | None:
    if value is None:
        return None
    return int(value.timestamp() * 1000)
