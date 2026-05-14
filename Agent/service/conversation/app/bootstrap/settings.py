from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    service_name: str = "conversation_service"
    service_version: str = "0.1.0"
    api_prefix: str = "/api/conversation_service/v1"

    database_url: str = "postgresql+asyncpg://conversation:conversation@localhost:5432/conversation"
    rabbitmq_url: str = "amqp://guest:guest@localhost:5672/"
    redis_url: str = "redis://localhost:6379/0"
    rabbitmq_exchange: str = "conversation.message.events"
    core_agent_status_exchange: str = "core_agent.run_status.events"
    core_agent_status_queue: str = "conversation.core_agent.run_status"
    core_agent_status_prefetch_count: int = Field(default=10, ge=1, le=1000)
    decision_agent_bizdata_exchange: str = "decision_agent.bizdata.events"
    decision_agent_bizdata_queue: str = "conversation.decision_agent.bizdata"
    decision_agent_bizdata_routing_key: str = "decision_agent.session.business_data.v1"
    decision_agent_bizdata_prefetch_count: int = Field(default=10, ge=1, le=1000)
    core_agent_kweaver_exchange: str = "core_agent.kweaver.stream"
    core_agent_kweaver_queue: str = "conversation.core_agent.kweaver"
    core_agent_kweaver_routing_key: str = "core_agent.kweaver.stream_event.v1"
    core_agent_kweaver_prefetch_count: int = Field(default=10, ge=1, le=1000)
    background_workers_enabled: bool = False
    outbox_poll_interval_ms: int = Field(default=1_000, ge=100)
    outbox_batch_size: int = Field(default=100, ge=1, le=1000)
    outbox_max_attempts: int = Field(default=5, ge=1, le=100)
    outbox_retry_delay_ms: int = Field(default=1_000, ge=1)
    outbox_lock_ttl_ms: int = Field(default=30_000, ge=1_000)
    retention_lock_ttl_ms: int = Field(default=30_000, ge=1_000)
    retention_auto_archive_after_days: int = Field(default=30, ge=1)
    retention_archive_retention_days: int = Field(default=365, ge=1)
    retention_batch_size: int = Field(default=100, ge=1, le=1000)

    snowflake_node_id: int = Field(default=1, ge=0, le=1023)
    snowflake_epoch_ms: int = 1_735_689_600_000

    auth_context_source: str = "nginx_ingress_x_user"
    auth_user_header_name: str = "X-User"
    core_agent_service_name: str = "core_agent_service"
    core_agent_service_token: str = "dev-core-agent-token"

    log_level: str = "INFO"
    log_format: str = "json"
    error_catalog_source: str = "local"
    message_catalog_source: str = "local"
