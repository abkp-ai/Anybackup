from sqlalchemy import ColumnElement, Select, String, cast, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.models.conversation import (
    ConversationListQuery,
    ConversationMessageListQuery,
    ConversationMessageListResult,
    ConversationMessageRecord,
    ConversationRecord,
    ConversationStatusEventRecord,
    MqOutboxRecord,
    Page,
)
from app.application.models.writeback import (
    ConversationCandidateSelectionRecord,
    ConversationContextDeltaRecord,
    ConversationContextSnapshotRecord,
    ConversationReasoningTraceRecord,
    ConversationWritebackIdempotencyRecord,
)
from app.application.ports.repositories import (
    CandidateSelectionRepository,
    ContextDeltaRepository,
    ContextSnapshotRepository,
    ConversationRepository,
    MessageRepository,
    MqOutboxRepository,
    ReasoningTraceRepository,
    StatusEventRepository,
    WritebackIdempotencyRepository,
)
from app.domain.conversation import Conversation, ConversationStatus
from app.domain.message import MessageStatus
from app.infrastructure.persistence.sqlalchemy.models import (
    ConversationCandidateSelectionModel,
    ConversationContextDeltaModel,
    ConversationContextSnapshotModel,
    ConversationMessageModel,
    ConversationModel,
    ConversationMqOutboxModel,
    ConversationReasoningTraceModel,
    ConversationStatusEventModel,
    ConversationWritebackIdempotencyModel,
)


class SqlAlchemyConversationRepository(ConversationRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, conversation: Conversation) -> None:
        self._session.add(_conversation_to_model(conversation))

    async def add_record(self, conversation: ConversationRecord) -> None:
        self._session.add(_conversation_record_to_model(conversation))

    async def update_record(self, conversation: ConversationRecord) -> None:
        await self._session.merge(_conversation_record_to_model(conversation))

    async def get_by_id(self, conversation_id: int) -> Conversation | None:
        result = await self._session.execute(
            select(ConversationModel).where(
                ConversationModel.f_conversation_id == conversation_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return _model_to_conversation(model)

    async def get_record_by_id(self, conversation_id: int) -> ConversationRecord | None:
        result = await self._session.execute(
            select(ConversationModel).where(
                ConversationModel.f_conversation_id == conversation_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return _conversation_model_to_record(model)

    async def list_records(
        self,
        query: ConversationListQuery,
        *,
        owner_user_id: str,
    ) -> tuple[tuple[ConversationRecord, ...], Page]:
        statement = select(ConversationModel).where(
            ConversationModel.f_owner_user_id == owner_user_id
        )
        statement = _apply_conversation_filters(statement, query)
        statement = statement.order_by(_conversation_sort_column(query.sort))

        offset = int(query.cursor or 0)
        statement = statement.offset(offset).limit(query.limit + 1)
        result = await self._session.execute(statement)
        models = list(result.scalars().all())
        has_more = len(models) > query.limit
        page_models = models[: query.limit]
        next_cursor = str(offset + query.limit) if has_more else None
        return (
            tuple(_conversation_model_to_record(model) for model in page_models),
            Page(next_cursor=next_cursor, has_more=has_more, limit=query.limit),
        )

    async def list_auto_archive_candidates(
        self,
        *,
        last_active_before_ms: int,
        limit: int,
    ) -> tuple[ConversationRecord, ...]:
        result = await self._session.execute(
            select(ConversationModel)
            .where(
                ConversationModel.f_status == ConversationStatus.ACTIVE.value,
                ConversationModel.f_legal_hold.is_(False),
                ConversationModel.f_last_active_time < last_active_before_ms,
                ConversationModel.f_active_run_id.is_(None),
            )
            .order_by(ConversationModel.f_last_active_time.asc())
            .limit(limit)
        )
        return tuple(_conversation_model_to_record(model) for model in result.scalars().all())

    async def list_expire_candidates(
        self,
        *,
        archived_before_ms: int,
        limit: int,
    ) -> tuple[ConversationRecord, ...]:
        result = await self._session.execute(
            select(ConversationModel)
            .where(
                ConversationModel.f_status == ConversationStatus.ARCHIVED.value,
                ConversationModel.f_legal_hold.is_(False),
                ConversationModel.f_archived_time.is_not(None),
                ConversationModel.f_archived_time < archived_before_ms,
            )
            .order_by(ConversationModel.f_archived_time.asc())
            .limit(limit)
        )
        return tuple(_conversation_model_to_record(model) for model in result.scalars().all())


def _conversation_to_model(conversation: Conversation) -> ConversationModel:
    return ConversationModel(
        f_conversation_id=conversation.conversation_id,
        f_owner_user_id=conversation.owner_user_id,
        f_tenant_id=None,
        f_title=conversation.title,
        f_display_summary=conversation.summary,
        f_status=conversation.status.value,
        f_scenario_binding=conversation.scenario_binding,
        f_tags=list(conversation.tags),
        f_retention_policy=conversation.retention_policy,
        f_legal_hold=conversation.legal_hold,
        f_last_active_time=conversation.last_active_time,
        f_active_run_id=conversation.active_run_id,
        f_archived_time=conversation.archived_time,
        f_archived_by=conversation.archived_by,
        f_archive_reason=conversation.archive_reason,
        f_expires_time=conversation.expires_time,
        f_expired_time=conversation.expired_time,
        f_purge_after_time=None,
        f_purged_time=None,
        f_version=1,
        f_created_time=conversation.created_time,
        f_updated_time=conversation.updated_time,
    )


def _model_to_conversation(model: ConversationModel) -> Conversation:
    return Conversation(
        conversation_id=model.f_conversation_id,
        owner_user_id=model.f_owner_user_id,
        title=model.f_title,
        summary=model.f_display_summary,
        scenario_binding=model.f_scenario_binding,
        tags=tuple(model.f_tags or ()),
        status=ConversationStatus(model.f_status),
        retention_policy=model.f_retention_policy,
        legal_hold=model.f_legal_hold,
        last_active_time=model.f_last_active_time,
        active_run_id=model.f_active_run_id,
        archived_time=model.f_archived_time,
        archived_by=model.f_archived_by,
        archive_reason=model.f_archive_reason,
        expires_time=model.f_expires_time,
        expired_time=model.f_expired_time,
        created_time=model.f_created_time,
        updated_time=model.f_updated_time,
    )


def _conversation_record_to_model(record: ConversationRecord) -> ConversationModel:
    return ConversationModel(
        f_conversation_id=record.conversation_id,
        f_owner_user_id=record.owner_user_id,
        f_tenant_id=None,
        f_title=record.title,
        f_display_summary=record.summary,
        f_status=record.status.value,
        f_scenario_binding=record.scenario_binding,
        f_tags=list(record.tags),
        f_retention_policy=record.retention_policy,
        f_legal_hold=record.legal_hold,
        f_last_active_time=record.last_active_time,
        f_active_run_id=record.active_run_id,
        f_archived_time=record.archived_time,
        f_archived_by=record.archived_by,
        f_archive_reason=record.archive_reason,
        f_expires_time=record.expires_time,
        f_expired_time=record.expired_time,
        f_purge_after_time=None,
        f_purged_time=None,
        f_version=1,
        f_created_time=record.created_time,
        f_updated_time=record.updated_time,
    )


def _conversation_model_to_record(model: ConversationModel) -> ConversationRecord:
    return ConversationRecord(
        conversation_id=model.f_conversation_id,
        owner_user_id=model.f_owner_user_id,
        title=model.f_title,
        summary=model.f_display_summary,
        scenario_binding=model.f_scenario_binding,
        tags=tuple(model.f_tags or ()),
        status=ConversationStatus(model.f_status),
        latest_message_summary=None,
        retention_policy=model.f_retention_policy,
        legal_hold=model.f_legal_hold,
        last_active_time=model.f_last_active_time,
        active_run_id=model.f_active_run_id,
        archived_time=model.f_archived_time,
        archived_by=model.f_archived_by,
        archive_reason=model.f_archive_reason,
        expires_time=model.f_expires_time,
        expired_time=model.f_expired_time,
        created_time=model.f_created_time,
        updated_time=model.f_updated_time,
    )


def _apply_conversation_filters(
    statement: Select[tuple[ConversationModel]],
    query: ConversationListQuery,
) -> Select[tuple[ConversationModel]]:
    if query.archived:
        statement = statement.where(ConversationModel.f_status == ConversationStatus.ARCHIVED.value)
    else:
        statement = statement.where(
            ConversationModel.f_status.notin_(
                [ConversationStatus.ARCHIVED.value, ConversationStatus.EXPIRED.value]
            )
        )

    if query.statuses:
        statement = statement.where(
            ConversationModel.f_status.in_([status.value for status in query.statuses])
        )
    if query.keyword:
        keyword = f"%{query.keyword.lower()}%"
        statement = statement.where(
            or_(
                func.lower(ConversationModel.f_title).like(keyword),
                func.lower(ConversationModel.f_display_summary).like(keyword),
                func.lower(cast(ConversationModel.f_tags, String)).like(keyword),
                func.lower(cast(ConversationModel.f_scenario_binding, String)).like(keyword),
            )
        )
    if query.scenario_id:
        statement = statement.where(
            func.lower(cast(ConversationModel.f_scenario_binding, String)).like(
                f"%{query.scenario_id.lower()}%"
            )
        )
    if query.task_type:
        statement = statement.where(
            func.lower(cast(ConversationModel.f_scenario_binding, String)).like(
                f"%{query.task_type.lower()}%"
            )
        )
    for tag in query.tags:
        statement = statement.where(
            func.lower(cast(ConversationModel.f_tags, String)).like(f"%{tag.lower()}%")
        )
    if query.created_after_time is not None:
        statement = statement.where(ConversationModel.f_created_time >= query.created_after_time)
    if query.created_before_time is not None:
        statement = statement.where(ConversationModel.f_created_time < query.created_before_time)
    if query.last_active_after_time is not None:
        statement = statement.where(
            ConversationModel.f_last_active_time >= query.last_active_after_time
        )
    if query.last_active_before_time is not None:
        statement = statement.where(
            ConversationModel.f_last_active_time < query.last_active_before_time
        )
    return statement


def _conversation_sort_column(sort: str) -> ColumnElement[int]:
    sort_map = {
        "last_active_desc": ConversationModel.f_last_active_time.desc(),
        "last_active_asc": ConversationModel.f_last_active_time.asc(),
        "created_desc": ConversationModel.f_created_time.desc(),
        "created_asc": ConversationModel.f_created_time.asc(),
        "updated_desc": ConversationModel.f_updated_time.desc(),
        "updated_asc": ConversationModel.f_updated_time.asc(),
    }
    return sort_map.get(sort, ConversationModel.f_last_active_time.desc())


class SqlAlchemyMessageRepository(MessageRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, message: ConversationMessageRecord) -> None:
        self._session.add(_message_record_to_model(message))

    async def update(self, message: ConversationMessageRecord) -> None:
        await self._session.merge(_message_record_to_model(message))

    async def get_by_id(self, message_id: int) -> ConversationMessageRecord | None:
        result = await self._session.execute(
            select(ConversationMessageModel).where(
                ConversationMessageModel.f_message_id == message_id,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return _message_model_to_record(model)

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> ConversationMessageRecord | None:
        result = await self._session.execute(
            select(ConversationMessageModel).where(
                ConversationMessageModel.f_idempotency_key == idempotency_key,
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return _message_model_to_record(model)

    async def list_by_conversation(
        self,
        conversation_id: int,
        *,
        limit: int,
    ) -> tuple[ConversationMessageRecord, ...]:
        result = await self._session.execute(
            select(ConversationMessageModel)
            .where(
                ConversationMessageModel.f_conversation_id == conversation_id,
                _visible_message_clause(),
            )
            .order_by(ConversationMessageModel.f_created_time.desc())
            .limit(limit)
        )
        return tuple(_message_model_to_record(model) for model in result.scalars().all())

    async def list_page(
        self,
        query: ConversationMessageListQuery,
    ) -> ConversationMessageListResult:
        statement = select(ConversationMessageModel).where(
            ConversationMessageModel.f_conversation_id == query.conversation_id,
            _visible_message_clause(),
        )
        if query.role is not None:
            statement = statement.where(ConversationMessageModel.f_role == query.role)
        if query.content_type is not None:
            statement = statement.where(
                ConversationMessageModel.f_content_type == query.content_type
            )
        if query.status is not None:
            statement = statement.where(ConversationMessageModel.f_status == query.status.value)
        if query.created_after_time is not None:
            statement = statement.where(
                ConversationMessageModel.f_created_time >= query.created_after_time
            )
        if query.created_before_time is not None:
            statement = statement.where(
                ConversationMessageModel.f_created_time < query.created_before_time
            )

        offset = int(query.cursor or 0)
        result = await self._session.execute(
            statement.order_by(
                ConversationMessageModel.f_created_time.asc(),
                ConversationMessageModel.f_message_id.asc(),
            )
            .offset(offset)
            .limit(query.limit + 1)
        )
        models = list(result.scalars().all())
        has_more = len(models) > query.limit
        page_models = models[: query.limit]
        next_cursor = str(offset + query.limit) if has_more else None
        return ConversationMessageListResult(
            items=tuple(_message_model_to_record(model) for model in page_models),
            page=Page(next_cursor=next_cursor, has_more=has_more, limit=query.limit),
        )


def _visible_message_clause() -> ColumnElement[bool]:
    return or_(
        ConversationMessageModel.f_role != "assistant",
        ConversationMessageModel.f_status.in_(
            [MessageStatus.RESPONDED.value, MessageStatus.FAILED.value]
        ),
        ConversationMessageModel.f_content.is_not(None),
        ConversationMessageModel.f_error_code.is_not(None),
    )


def _message_record_to_model(record: ConversationMessageRecord) -> ConversationMessageModel:
    return ConversationMessageModel(
        f_message_id=record.message_id,
        f_conversation_id=record.conversation_id,
        f_parent_message_id=record.parent_message_id,
        f_turn_id=record.turn_id,
        f_role=record.role,
        f_content_type=record.content_type,
        f_content=record.content,
        f_rich_payload=record.rich_payload,
        f_status=record.status.value,
        f_client_message_id=record.client_message_id,
        f_idempotency_key=record.idempotency_key,
        f_trace_id=record.trace_id,
        f_correlation_id=record.correlation_id,
        f_error_code=record.error_code,
        f_created_time=record.created_time,
        f_updated_time=record.updated_time,
    )


def _message_model_to_record(model: ConversationMessageModel) -> ConversationMessageRecord:
    return ConversationMessageRecord(
        message_id=model.f_message_id,
        conversation_id=model.f_conversation_id,
        parent_message_id=model.f_parent_message_id,
        turn_id=model.f_turn_id,
        role=model.f_role,
        content_type=model.f_content_type,
        content=model.f_content,
        rich_payload=model.f_rich_payload,
        status=MessageStatus(model.f_status),
        client_message_id=model.f_client_message_id,
        idempotency_key=model.f_idempotency_key,
        trace_id=model.f_trace_id,
        correlation_id=model.f_correlation_id,
        error_code=model.f_error_code,
        created_time=model.f_created_time,
        updated_time=model.f_updated_time,
    )


class SqlAlchemyStatusEventRepository(StatusEventRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event: ConversationStatusEventRecord) -> None:
        self._session.add(_status_event_record_to_model(event))

    async def exists_by_core_event_id(self, core_event_id: str) -> bool:
        result = await self._session.execute(
            select(ConversationStatusEventModel.f_status_event_id)
            .where(
                cast(ConversationStatusEventModel.f_payload, String).like(
                    f'%"{core_event_id}"%'
                )
            )
            .limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def next_sequence(self, conversation_id: int) -> int:
        result = await self._session.execute(
            select(func.max(ConversationStatusEventModel.f_sequence)).where(
                ConversationStatusEventModel.f_conversation_id == conversation_id,
            )
        )
        current_sequence = result.scalar_one_or_none()
        if current_sequence is None:
            return 1
        return int(current_sequence) + 1

    async def max_sequence(self, conversation_id: int) -> int:
        result = await self._session.execute(
            select(func.max(ConversationStatusEventModel.f_sequence)).where(
                ConversationStatusEventModel.f_conversation_id == conversation_id,
            )
        )
        current_sequence = result.scalar_one_or_none()
        return int(current_sequence or 0)

    async def get_first_by_message_id(
        self,
        message_id: int,
    ) -> ConversationStatusEventRecord | None:
        result = await self._session.execute(
            select(ConversationStatusEventModel)
            .where(ConversationStatusEventModel.f_message_id == message_id)
            .order_by(ConversationStatusEventModel.f_sequence.asc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return _status_event_model_to_record(model)

    async def list_by_conversation(
        self,
        conversation_id: int,
        *,
        limit: int,
    ) -> tuple[ConversationStatusEventRecord, ...]:
        result = await self._session.execute(
            select(ConversationStatusEventModel)
            .where(ConversationStatusEventModel.f_conversation_id == conversation_id)
            .order_by(ConversationStatusEventModel.f_sequence.desc())
            .limit(limit)
        )
        return tuple(_status_event_model_to_record(model) for model in result.scalars().all())

    async def list_after_sequence(
        self,
        conversation_id: int,
        *,
        after_sequence: int,
        limit: int,
    ) -> tuple[tuple[ConversationStatusEventRecord, ...], Page]:
        result = await self._session.execute(
            select(ConversationStatusEventModel)
            .where(
                ConversationStatusEventModel.f_conversation_id == conversation_id,
                ConversationStatusEventModel.f_sequence > after_sequence,
            )
            .order_by(ConversationStatusEventModel.f_sequence.asc())
            .limit(limit + 1)
        )
        models = list(result.scalars().all())
        has_more = len(models) > limit
        page_models = models[:limit]
        next_cursor = str(page_models[-1].f_sequence) if has_more and page_models else None
        return (
            tuple(_status_event_model_to_record(model) for model in page_models),
            Page(next_cursor=next_cursor, has_more=has_more, limit=limit),
        )

    async def list_ag_ui_after_sequence(
        self,
        conversation_id: int,
        *,
        run_id: str,
        after_sequence: int,
        limit: int,
    ) -> tuple[ConversationStatusEventRecord, ...]:
        result = await self._session.execute(
            select(ConversationStatusEventModel)
            .where(
                ConversationStatusEventModel.f_conversation_id == conversation_id,
                ConversationStatusEventModel.f_sequence > after_sequence,
                cast(ConversationStatusEventModel.f_payload, String).like(
                    f'%"{run_id}"%'
                ),
            )
            .order_by(ConversationStatusEventModel.f_sequence.asc())
            .limit(limit)
        )
        return tuple(_status_event_model_to_record(model) for model in result.scalars().all())


def _status_event_record_to_model(
    record: ConversationStatusEventRecord,
) -> ConversationStatusEventModel:
    payload = dict(record.payload or {})
    if payload.get("type") is None:
        if record.message_status is not None:
            payload["message_status"] = record.message_status.value
        if record.title is not None:
            payload["title"] = record.title
        if record.detail is not None:
            payload["detail"] = record.detail
        if record.rich_payload is not None:
            payload["rich_payload"] = record.rich_payload
    return ConversationStatusEventModel(
        f_status_event_id=record.status_event_id,
        f_conversation_id=record.conversation_id,
        f_sequence=record.sequence,
        f_event_type=record.event_type,
        f_event_version="v1",
        f_message_id=record.message_id,
        f_turn_id=record.turn_id,
        f_payload=payload,
        f_visible_to_user=True,
        f_trace_id=record.trace_id,
        f_correlation_id=record.correlation_id,
        f_created_time=record.created_time,
        f_updated_time=record.updated_time,
    )


def _status_event_model_to_record(
    model: ConversationStatusEventModel,
) -> ConversationStatusEventRecord:
    payload = dict(model.f_payload or {})
    message_status = payload.get("message_status")
    return ConversationStatusEventRecord(
        status_event_id=model.f_status_event_id,
        conversation_id=model.f_conversation_id,
        message_id=model.f_message_id,
        turn_id=model.f_turn_id,
        event_type=model.f_event_type,
        sequence=model.f_sequence,
        message_status=MessageStatus(message_status) if message_status is not None else None,
        title=payload.get("title"),
        detail=payload.get("detail"),
        payload=payload,
        rich_payload=payload.get("rich_payload"),
        trace_id=model.f_trace_id,
        correlation_id=model.f_correlation_id,
        created_time=model.f_created_time,
        updated_time=model.f_updated_time,
    )


class SqlAlchemyMqOutboxRepository(MqOutboxRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, event: MqOutboxRecord) -> None:
        self._session.add(
            ConversationMqOutboxModel(
                f_outbox_id=event.outbox_id,
                f_event_id=event.event_id,
                f_event_type=event.event_type,
                f_routing_key=event.routing_key,
                f_conversation_id=event.conversation_id,
                f_message_id=event.message_id,
                f_payload=event.payload,
                f_status=event.status,
                f_attempt_count=event.attempt_count,
                f_next_retry_time=event.next_retry_time,
                f_last_error_code=event.last_error_code,
                f_trace_id=event.trace_id,
                f_correlation_id=event.correlation_id,
                f_idempotency_key=event.idempotency_key,
                f_created_time=event.created_time,
                f_updated_time=event.updated_time,
            )
        )

    async def list_publishable(self, *, limit: int, now_ms: int) -> tuple[MqOutboxRecord, ...]:
        result = await self._session.execute(
            select(ConversationMqOutboxModel)
            .where(
                or_(
                    ConversationMqOutboxModel.f_status == "pending",
                    (
                        (ConversationMqOutboxModel.f_status == "retry")
                        & (ConversationMqOutboxModel.f_next_retry_time <= now_ms)
                    ),
                )
            )
            .order_by(ConversationMqOutboxModel.f_created_time.asc())
            .limit(limit)
        )
        return tuple(_outbox_model_to_record(model) for model in result.scalars().all())

    async def mark_published(self, *, outbox_id: int, now_ms: int) -> None:
        await self._session.execute(
            update(ConversationMqOutboxModel)
            .where(ConversationMqOutboxModel.f_outbox_id == outbox_id)
            .values(f_status="published", f_updated_time=now_ms, f_next_retry_time=None)
        )

    async def mark_retry(
        self,
        *,
        outbox_id: int,
        attempt_count: int,
        next_retry_time: int,
        error_code: str,
        now_ms: int,
    ) -> None:
        await self._session.execute(
            update(ConversationMqOutboxModel)
            .where(ConversationMqOutboxModel.f_outbox_id == outbox_id)
            .values(
                f_status="retry",
                f_attempt_count=attempt_count,
                f_next_retry_time=next_retry_time,
                f_last_error_code=error_code,
                f_updated_time=now_ms,
            )
        )

    async def mark_dlq(
        self,
        *,
        outbox_id: int,
        attempt_count: int,
        error_code: str,
        now_ms: int,
    ) -> None:
        await self._session.execute(
            update(ConversationMqOutboxModel)
            .where(ConversationMqOutboxModel.f_outbox_id == outbox_id)
            .values(
                f_status="dlq",
                f_attempt_count=attempt_count,
                f_next_retry_time=None,
                f_last_error_code=error_code,
                f_updated_time=now_ms,
            )
        )


def _outbox_model_to_record(model: ConversationMqOutboxModel) -> MqOutboxRecord:
    return MqOutboxRecord(
        outbox_id=model.f_outbox_id,
        event_id=model.f_event_id,
        event_type=model.f_event_type,
        routing_key=model.f_routing_key,
        conversation_id=model.f_conversation_id,
        message_id=model.f_message_id,
        payload=model.f_payload,
        status=model.f_status,
        attempt_count=model.f_attempt_count,
        next_retry_time=model.f_next_retry_time,
        last_error_code=model.f_last_error_code,
        trace_id=model.f_trace_id,
        correlation_id=model.f_correlation_id,
        idempotency_key=model.f_idempotency_key,
        created_time=model.f_created_time,
        updated_time=model.f_updated_time,
    )


class SqlAlchemyWritebackIdempotencyRepository(WritebackIdempotencyRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, record: ConversationWritebackIdempotencyRecord) -> None:
        self._session.add(
            ConversationWritebackIdempotencyModel(
                f_writeback_id=record.writeback_id,
                f_idempotency_key=record.idempotency_key,
                f_conversation_id=record.conversation_id,
                f_output_id=record.output_id,
                f_request_hash=record.request_hash,
                f_result_status=record.result_status,
                f_result_message_id=record.result_message_id,
                f_reject_code=record.reject_code,
                f_reject_reason=record.reject_reason,
                f_trace_id=record.trace_id,
                f_correlation_id=record.correlation_id,
                f_created_time=record.created_time,
                f_updated_time=record.updated_time,
            )
        )

    async def get_by_key(
        self,
        idempotency_key: str,
    ) -> ConversationWritebackIdempotencyRecord | None:
        result = await self._session.execute(
            select(ConversationWritebackIdempotencyModel).where(
                ConversationWritebackIdempotencyModel.f_idempotency_key == idempotency_key
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return _writeback_model_to_record(model)

    async def get_by_conversation_output_id(
        self,
        *,
        conversation_id: int,
        output_id: str,
    ) -> ConversationWritebackIdempotencyRecord | None:
        result = await self._session.execute(
            select(ConversationWritebackIdempotencyModel)
            .where(
                ConversationWritebackIdempotencyModel.f_conversation_id == conversation_id,
                ConversationWritebackIdempotencyModel.f_output_id == output_id,
            )
            .order_by(ConversationWritebackIdempotencyModel.f_created_time.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return _writeback_model_to_record(model)

    async def max_accepted_output_sequence(
        self,
        conversation_id: int,
        *,
        turn_id: int,
        message_id: int,
    ) -> int:
        del message_id
        result = await self._session.execute(
            select(ConversationWritebackIdempotencyModel.f_output_id).where(
                ConversationWritebackIdempotencyModel.f_conversation_id == conversation_id,
                ConversationWritebackIdempotencyModel.f_result_status == "accepted",
            )
        )
        prefix = _ag_ui_output_turn_prefix(conversation_id, turn_id)
        sequences = [
            _parse_ag_ui_output_sequence(output_id)
            for output_id in result.scalars().all()
            if output_id is not None and output_id.startswith(prefix)
        ]
        return max(sequences, default=0)


def _writeback_model_to_record(
    model: ConversationWritebackIdempotencyModel,
) -> ConversationWritebackIdempotencyRecord:
    return ConversationWritebackIdempotencyRecord(
        writeback_id=model.f_writeback_id,
        idempotency_key=model.f_idempotency_key,
        conversation_id=model.f_conversation_id,
        output_id=model.f_output_id,
        request_hash=model.f_request_hash,
        result_status=model.f_result_status,
        result_message_id=model.f_result_message_id,
        reject_code=model.f_reject_code,
        reject_reason=model.f_reject_reason,
        trace_id=model.f_trace_id,
        correlation_id=model.f_correlation_id,
        created_time=model.f_created_time,
        updated_time=model.f_updated_time,
    )


class SqlAlchemyContextDeltaRepository(ContextDeltaRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, record: ConversationContextDeltaRecord) -> None:
        self._session.add(
            ConversationContextDeltaModel(
                f_context_delta_id=record.context_delta_id,
                f_conversation_id=record.conversation_id,
                f_turn_id=record.turn_id,
                f_source_message_id=record.source_message_id,
                f_base_snapshot_version=record.base_snapshot_version,
                f_delta_payload=record.delta_payload,
                f_merge_status=record.merge_status,
                f_created_by_agent=record.created_by_agent,
                f_trace_id=record.trace_id,
                f_created_time=record.created_time,
                f_updated_time=record.updated_time,
            )
        )

    async def list_pending(self, *, limit: int) -> tuple[ConversationContextDeltaRecord, ...]:
        result = await self._session.execute(
            select(ConversationContextDeltaModel)
            .where(ConversationContextDeltaModel.f_merge_status == "pending")
            .order_by(ConversationContextDeltaModel.f_created_time.asc())
            .limit(limit)
        )
        return tuple(_context_delta_model_to_record(model) for model in result.scalars().all())

    async def count_pending_by_conversation(self, conversation_id: int) -> int:
        result = await self._session.execute(
            select(func.count(ConversationContextDeltaModel.f_context_delta_id)).where(
                ConversationContextDeltaModel.f_conversation_id == conversation_id,
                ConversationContextDeltaModel.f_merge_status == "pending",
            )
        )
        return int(result.scalar_one() or 0)

    async def mark_status(
        self,
        *,
        context_delta_id: int,
        merge_status: str,
        now_ms: int,
    ) -> None:
        await self._session.execute(
            update(ConversationContextDeltaModel)
            .where(ConversationContextDeltaModel.f_context_delta_id == context_delta_id)
            .values(f_merge_status=merge_status, f_updated_time=now_ms)
        )


def _context_delta_model_to_record(
    model: ConversationContextDeltaModel,
) -> ConversationContextDeltaRecord:
    return ConversationContextDeltaRecord(
        context_delta_id=model.f_context_delta_id,
        conversation_id=model.f_conversation_id,
        turn_id=model.f_turn_id,
        source_message_id=model.f_source_message_id,
        base_snapshot_version=model.f_base_snapshot_version,
        delta_payload=model.f_delta_payload,
        merge_status=model.f_merge_status,
        created_by_agent=model.f_created_by_agent,
        trace_id=model.f_trace_id,
        created_time=model.f_created_time,
        updated_time=model.f_updated_time,
    )


class SqlAlchemyContextSnapshotRepository(ContextSnapshotRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, record: ConversationContextSnapshotRecord) -> None:
        self._session.add(
            ConversationContextSnapshotModel(
                f_context_snapshot_id=record.context_snapshot_id,
                f_conversation_id=record.conversation_id,
                f_snapshot_version=record.snapshot_version,
                f_short_summary=record.short_summary,
                f_structured_state=record.structured_state,
                f_last_message_id=record.last_message_id,
                f_status=record.status,
                f_created_by=record.created_by,
                f_trace_id=record.trace_id,
                f_created_time=record.created_time,
                f_updated_time=record.updated_time,
            )
        )

    async def get_current_by_conversation(
        self,
        conversation_id: int,
    ) -> ConversationContextSnapshotRecord | None:
        result = await self._session.execute(
            select(ConversationContextSnapshotModel)
            .where(
                ConversationContextSnapshotModel.f_conversation_id == conversation_id,
                ConversationContextSnapshotModel.f_status == "current",
            )
            .order_by(ConversationContextSnapshotModel.f_snapshot_version.desc())
            .limit(1)
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return _context_snapshot_model_to_record(model)

    async def next_version(self, conversation_id: int) -> int:
        result = await self._session.execute(
            select(func.max(ConversationContextSnapshotModel.f_snapshot_version)).where(
                ConversationContextSnapshotModel.f_conversation_id == conversation_id
            )
        )
        current = result.scalar_one_or_none()
        return int(current or 0) + 1


def _context_snapshot_model_to_record(
    model: ConversationContextSnapshotModel,
) -> ConversationContextSnapshotRecord:
    return ConversationContextSnapshotRecord(
        context_snapshot_id=model.f_context_snapshot_id,
        conversation_id=model.f_conversation_id,
        snapshot_version=model.f_snapshot_version,
        short_summary=model.f_short_summary,
        structured_state=model.f_structured_state,
        last_message_id=model.f_last_message_id,
        status=model.f_status,
        created_by=model.f_created_by,
        trace_id=model.f_trace_id,
        created_time=model.f_created_time,
        updated_time=model.f_updated_time,
    )


class SqlAlchemyReasoningTraceRepository(ReasoningTraceRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, record: ConversationReasoningTraceRecord) -> None:
        self._session.add(
            ConversationReasoningTraceModel(
                f_reasoning_trace_id=record.reasoning_trace_id,
                f_conversation_id=record.conversation_id,
                f_source_message_id=record.source_message_id,
                f_trace_payload=record.trace_payload,
                f_core_agent_run_id=record.core_agent_run_id,
                f_created_by_agent=record.created_by_agent,
                f_trace_id=record.trace_id,
                f_created_time=record.created_time,
                f_updated_time=record.updated_time,
            )
        )

    async def get_by_id(
        self,
        reasoning_trace_id: str,
    ) -> ConversationReasoningTraceRecord | None:
        result = await self._session.execute(
            select(ConversationReasoningTraceModel).where(
                ConversationReasoningTraceModel.f_reasoning_trace_id == reasoning_trace_id
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return _reasoning_trace_model_to_record(model)

    async def list_by_conversation(
        self,
        conversation_id: int,
        *,
        limit: int,
    ) -> tuple[ConversationReasoningTraceRecord, ...]:
        result = await self._session.execute(
            select(ConversationReasoningTraceModel)
            .where(ConversationReasoningTraceModel.f_conversation_id == conversation_id)
            .order_by(ConversationReasoningTraceModel.f_created_time.desc())
            .limit(limit)
        )
        return tuple(_reasoning_trace_model_to_record(model) for model in result.scalars().all())


def _reasoning_trace_model_to_record(
    model: ConversationReasoningTraceModel,
) -> ConversationReasoningTraceRecord:
    return ConversationReasoningTraceRecord(
        reasoning_trace_id=model.f_reasoning_trace_id,
        conversation_id=model.f_conversation_id,
        source_message_id=model.f_source_message_id,
        trace_payload=model.f_trace_payload,
        core_agent_run_id=model.f_core_agent_run_id,
        created_by_agent=model.f_created_by_agent,
        trace_id=model.f_trace_id,
        created_time=model.f_created_time,
        updated_time=model.f_updated_time,
    )


class SqlAlchemyCandidateSelectionRepository(CandidateSelectionRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add(self, record: ConversationCandidateSelectionRecord) -> None:
        self._session.add(
            ConversationCandidateSelectionModel(
                f_selection_id=record.selection_id,
                f_conversation_id=record.conversation_id,
                f_reasoning_trace_id=record.reasoning_trace_id,
                f_candidate_option_id=record.candidate_option_id,
                f_action=record.action,
                f_comment=record.comment,
                f_idempotency_key=record.idempotency_key,
                f_created_by_user_id=record.created_by_user_id,
                f_trace_id=record.trace_id,
                f_correlation_id=record.correlation_id,
                f_created_time=record.created_time,
                f_updated_time=record.updated_time,
            )
        )

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> ConversationCandidateSelectionRecord | None:
        result = await self._session.execute(
            select(ConversationCandidateSelectionModel).where(
                ConversationCandidateSelectionModel.f_idempotency_key == idempotency_key
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None
        return _candidate_selection_model_to_record(model)


def _candidate_selection_model_to_record(
    model: ConversationCandidateSelectionModel,
) -> ConversationCandidateSelectionRecord:
    return ConversationCandidateSelectionRecord(
        selection_id=model.f_selection_id,
        conversation_id=model.f_conversation_id,
        reasoning_trace_id=model.f_reasoning_trace_id,
        candidate_option_id=model.f_candidate_option_id,
        action=model.f_action,
        comment=model.f_comment,
        idempotency_key=model.f_idempotency_key,
        created_by_user_id=model.f_created_by_user_id,
        trace_id=model.f_trace_id,
        correlation_id=model.f_correlation_id,
        created_time=model.f_created_time,
        updated_time=model.f_updated_time,
    )


def _parse_ag_ui_output_sequence(output_id: str) -> int:
    if not output_id.startswith("agui:"):
        return 0
    try:
        return int(output_id.rsplit(":", maxsplit=1)[-1])
    except ValueError:
        return 0


def _ag_ui_output_prefix(conversation_id: int, turn_id: int, message_id: int) -> str:
    return f"agui:{conversation_id}:{turn_id}:{message_id}:"


def _ag_ui_output_turn_prefix(conversation_id: int, turn_id: int) -> str:
    return f"agui:{conversation_id}:{turn_id}:"
