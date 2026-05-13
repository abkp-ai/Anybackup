from dependency_injector import containers, providers

from app.application.use_cases.ag_ui_runs import StartAgUiRunHandler
from app.application.use_cases.agent_status import CoreAgentStatusEventHandler
from app.application.use_cases.config import (
    CopyConversationConfigHandler,
    UpdateConversationHandler,
)
from app.application.use_cases.context import ContextMergeWorker, GetConversationContextHandler
from app.application.use_cases.conversation import (
    CreateConversationHandler,
    GetConversationHandler,
    ListConversationEventsHandler,
    ListConversationMessagesHandler,
    ListConversationsHandler,
    SendUserMessageHandler,
)
from app.application.use_cases.decision_agent_ag_ui import DecisionAgentAgUiEventHandler
from app.application.use_cases.business_data_to_ag_ui import BusinessDataToAgUiConverter
from app.application.use_cases.kweaver_to_ag_ui import KweaverToAgUiConverter
from app.application.ag_ui_templates.registry import AgUiTemplateRegistry
from app.application.use_cases.outbox import OutboxPublisherWorker
from app.application.use_cases.reasoning import (
    ConfirmCandidateSelectionHandler,
    ListReasoningTracesHandler,
)
from app.application.use_cases.retention import (
    ArchiveConversationHandler,
    RestoreConversationHandler,
    RetentionWorker,
    SetLegalHoldHandler,
)
from app.application.use_cases.skill_manifest import GetSkillManifestHandler
from app.bootstrap.settings import Settings
from app.infrastructure.i18n.local_catalog import LocalErrorCatalog, LocalMessageCatalog
from app.infrastructure.id_generator.snowflake import SnowflakeIdGenerator
from app.infrastructure.locking.redis.client import create_redis_client
from app.infrastructure.locking.redis.lock import RedisGlobalLock
from app.infrastructure.messaging.rabbitmq.publisher import RabbitMqEventPublisher
from app.infrastructure.persistence.sqlalchemy.session import (
    create_async_session_factory,
    create_database_engine,
)
from app.infrastructure.persistence.sqlalchemy.unit_of_work import SqlAlchemyUnitOfWork
from app.interfaces.mq.agent_status_consumer import RabbitMqCoreAgentStatusConsumer
from app.interfaces.mq.decision_agent_ag_ui_consumer import RabbitMqDecisionAgentAgUiConsumer
from app.interfaces.mq.core_agent_kweaver_consumer import RabbitMqCoreAgentKweaverConsumer


class Container(containers.DeclarativeContainer):
    settings = providers.Singleton(Settings)
    database_engine = providers.Singleton(
        create_database_engine,
        database_url=settings.provided.database_url,
    )
    async_session_factory = providers.Singleton(
        create_async_session_factory,
        engine=database_engine,
    )
    unit_of_work = providers.Factory(
        SqlAlchemyUnitOfWork,
        session_factory=async_session_factory,
    )
    id_generator = providers.Singleton(
        SnowflakeIdGenerator,
        node_id=settings.provided.snowflake_node_id,
        epoch_ms=settings.provided.snowflake_epoch_ms,
    )
    redis_client = providers.Singleton(
        create_redis_client,
        redis_url=settings.provided.redis_url,
    )
    global_lock = providers.Factory(
        RedisGlobalLock,
        redis_client=redis_client,
    )
    error_catalog = providers.Singleton(LocalErrorCatalog)
    message_catalog = providers.Singleton(LocalMessageCatalog)
    get_skill_manifest_handler = providers.Factory(
        GetSkillManifestHandler,
        api_prefix=settings.provided.api_prefix,
        service_version=settings.provided.service_version,
    )
    event_publisher = providers.Singleton(
        RabbitMqEventPublisher,
        rabbitmq_url=settings.provided.rabbitmq_url,
        exchange_name=settings.provided.rabbitmq_exchange,
    )
    create_conversation_handler = providers.Factory(
        CreateConversationHandler,
        unit_of_work_factory=unit_of_work.provider,
        id_generator=id_generator,
    )
    list_conversations_handler = providers.Factory(
        ListConversationsHandler,
        unit_of_work_factory=unit_of_work.provider,
    )
    get_conversation_handler = providers.Factory(
        GetConversationHandler,
        unit_of_work_factory=unit_of_work.provider,
    )
    send_user_message_handler = providers.Factory(
        SendUserMessageHandler,
        unit_of_work_factory=unit_of_work.provider,
        id_generator=id_generator,
    )
    list_conversation_messages_handler = providers.Factory(
        ListConversationMessagesHandler,
        unit_of_work_factory=unit_of_work.provider,
    )
    list_conversation_events_handler = providers.Factory(
        ListConversationEventsHandler,
        unit_of_work_factory=unit_of_work.provider,
    )
    start_ag_ui_run_handler = providers.Factory(
        StartAgUiRunHandler,
        unit_of_work_factory=unit_of_work.provider,
    )
    get_conversation_context_handler = providers.Factory(
        GetConversationContextHandler,
        unit_of_work_factory=unit_of_work.provider,
    )
    list_reasoning_traces_handler = providers.Factory(
        ListReasoningTracesHandler,
        unit_of_work_factory=unit_of_work.provider,
    )
    confirm_candidate_selection_handler = providers.Factory(
        ConfirmCandidateSelectionHandler,
        unit_of_work_factory=unit_of_work.provider,
        id_generator=id_generator,
    )
    context_merge_worker = providers.Factory(
        ContextMergeWorker,
        unit_of_work_factory=unit_of_work.provider,
        id_generator=id_generator,
        lock=global_lock,
        lock_ttl_ms=settings.provided.outbox_lock_ttl_ms,
    )
    archive_conversation_handler = providers.Factory(
        ArchiveConversationHandler,
        unit_of_work_factory=unit_of_work.provider,
        id_generator=id_generator,
    )
    restore_conversation_handler = providers.Factory(
        RestoreConversationHandler,
        unit_of_work_factory=unit_of_work.provider,
        id_generator=id_generator,
    )
    set_legal_hold_handler = providers.Factory(
        SetLegalHoldHandler,
        unit_of_work_factory=unit_of_work.provider,
        id_generator=id_generator,
    )
    copy_conversation_config_handler = providers.Factory(
        CopyConversationConfigHandler,
        unit_of_work_factory=unit_of_work.provider,
        id_generator=id_generator,
    )
    update_conversation_handler = providers.Factory(
        UpdateConversationHandler,
        unit_of_work_factory=unit_of_work.provider,
    )
    retention_worker = providers.Factory(
        RetentionWorker,
        unit_of_work_factory=unit_of_work.provider,
        id_generator=id_generator,
        lock=global_lock,
        lock_ttl_ms=settings.provided.retention_lock_ttl_ms,
        auto_archive_after_days=settings.provided.retention_auto_archive_after_days,
        archive_retention_days=settings.provided.retention_archive_retention_days,
        batch_size=settings.provided.retention_batch_size,
    )
    core_agent_status_handler = providers.Factory(
        CoreAgentStatusEventHandler,
        unit_of_work_factory=unit_of_work.provider,
        id_generator=id_generator,
    )
    decision_agent_ag_ui_handler = providers.Factory(
        DecisionAgentAgUiEventHandler,
        unit_of_work_factory=unit_of_work.provider,
        id_generator=id_generator,
    )
    ag_ui_template_registry = providers.Singleton(AgUiTemplateRegistry)
    business_data_converter = providers.Singleton(
        BusinessDataToAgUiConverter,
        template_registry=ag_ui_template_registry,
        handler=decision_agent_ag_ui_handler,
    )
    kweaver_converter = providers.Singleton(
        KweaverToAgUiConverter,
        handler=decision_agent_ag_ui_handler,
    )
    core_agent_status_consumer = providers.Singleton(
        RabbitMqCoreAgentStatusConsumer,
        rabbitmq_url=settings.provided.rabbitmq_url,
        exchange_name=settings.provided.core_agent_status_exchange,
        queue_name=settings.provided.core_agent_status_queue,
        prefetch_count=settings.provided.core_agent_status_prefetch_count,
        handler=core_agent_status_handler,
    )
    decision_agent_ag_ui_consumer = providers.Singleton(
        RabbitMqDecisionAgentAgUiConsumer,
        rabbitmq_url=settings.provided.rabbitmq_url,
        exchange_name=settings.provided.decision_agent_ag_ui_exchange,
        queue_name=settings.provided.decision_agent_ag_ui_queue,
        routing_key=settings.provided.decision_agent_ag_ui_routing_key,
        prefetch_count=settings.provided.decision_agent_ag_ui_prefetch_count,
        converter=business_data_converter,
    )
    core_agent_kweaver_consumer = providers.Singleton(
        RabbitMqCoreAgentKweaverConsumer,
        rabbitmq_url=settings.provided.rabbitmq_url,
        exchange_name=settings.provided.core_agent_kweaver_exchange,
        queue_name=settings.provided.core_agent_kweaver_queue,
        routing_key=settings.provided.core_agent_kweaver_routing_key,
        prefetch_count=settings.provided.core_agent_kweaver_prefetch_count,
        converter=kweaver_converter,
    )
    outbox_publisher_worker = providers.Factory(
        OutboxPublisherWorker,
        unit_of_work_factory=unit_of_work.provider,
        publisher=event_publisher,
        lock=global_lock,
        exchange_name=settings.provided.rabbitmq_exchange,
        batch_size=settings.provided.outbox_batch_size,
        max_attempts=settings.provided.outbox_max_attempts,
        retry_delay_ms=settings.provided.outbox_retry_delay_ms,
        lock_ttl_ms=settings.provided.outbox_lock_ttl_ms,
    )
