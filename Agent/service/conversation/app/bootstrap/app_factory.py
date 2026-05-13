import asyncio
import logging
import time
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager, suppress

from dependency_injector import providers
from fastapi import FastAPI

from app.bootstrap.container import Container
from app.bootstrap.settings import Settings
from app.infrastructure.observability.logging import configure_structured_logging
from app.interfaces.http.ag_ui_sse.router import router as ag_ui_sse_router
from app.interfaces.http.v1.error_handlers import register_error_handlers
from app.interfaces.http.v1.middleware import register_request_context_middleware
from app.interfaces.http.v1.router import router as http_v1_router

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    container = Container()
    if settings is not None:
        container.settings.override(providers.Object(settings))
    settings = container.settings()
    configure_structured_logging(settings.log_level)

    app = FastAPI(
        title="Conversation Service",
        version="0.1.0",
        openapi_url=f"{settings.api_prefix}/openapi.json",
        docs_url=f"{settings.api_prefix}/docs",
        redoc_url=f"{settings.api_prefix}/redoc",
        lifespan=_lifespan(container, settings),
    )
    app.state.settings = settings
    app.state.container = container
    register_request_context_middleware(app)
    register_error_handlers(app)
    app.include_router(http_v1_router, prefix=settings.api_prefix)
    app.include_router(ag_ui_sse_router, prefix=settings.api_prefix)

    @app.get("/healthz", tags=["health"])
    async def healthz() -> dict[str, str]:
        return {
            "status": "ok",
            "service": settings.service_name,
        }

    @app.get("/readyz", tags=["health"])
    async def readyz() -> dict[str, object]:
        return {
            "status": "ready",
            "service": settings.service_name,
            "checks": {
                "database": "configured",
                "rabbitmq": "configured",
                "redis": "configured",
            },
        }

    return app


def _lifespan(
    container: Container,
    settings: Settings,
) -> Callable[[FastAPI], AbstractAsyncContextManager[None]]:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if not settings.background_workers_enabled:
            yield
            return

        core_agent_status_consumer = container.core_agent_status_consumer()
        decision_agent_ag_ui_consumer = container.decision_agent_ag_ui_consumer()
        core_agent_kweaver_consumer = container.core_agent_kweaver_consumer()
        outbox_task: asyncio.Task[None] | None = None
        context_merge_task: asyncio.Task[None] | None = None
        retention_task: asyncio.Task[None] | None = None

        try:
            await core_agent_status_consumer.start()
            await decision_agent_ag_ui_consumer.start()
            await core_agent_kweaver_consumer.start()
            outbox_task = asyncio.create_task(
                _run_outbox_publisher_loop(container, settings),
                name="conversation-service-outbox-publisher",
            )
            context_merge_task = asyncio.create_task(
                _run_context_merge_loop(container, settings),
                name="conversation-service-context-merge-worker",
            )
            retention_task = asyncio.create_task(
                _run_retention_loop(container, settings),
                name="conversation-service-retention-worker",
            )
            app.state.background_worker_tasks = (
                outbox_task,
                context_merge_task,
                retention_task,
            )
            logger.info("background_workers_started")
            yield
        finally:
            for task in (retention_task, context_merge_task, outbox_task):
                if task is None:
                    continue
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task
            await decision_agent_ag_ui_consumer.close()
            await core_agent_kweaver_consumer.close()
            await core_agent_status_consumer.close()
            await container.event_publisher().close()
            logger.info("background_workers_stopped")

    return lifespan


async def _run_outbox_publisher_loop(container: Container, settings: Settings) -> None:
    worker_id = f"{settings.service_name}:outbox-publisher"
    poll_interval_seconds = settings.outbox_poll_interval_ms / 1000

    while True:
        try:
            worker = container.outbox_publisher_worker()
            await worker.run_once(worker_id=worker_id, now_ms=int(time.time() * 1000))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("outbox_publisher_loop_failed", extra={"worker_id": worker_id})

        await asyncio.sleep(poll_interval_seconds)


async def _run_context_merge_loop(container: Container, settings: Settings) -> None:
    worker_id = f"{settings.service_name}:context-merge"
    poll_interval_seconds = settings.outbox_poll_interval_ms / 1000

    while True:
        try:
            worker = container.context_merge_worker()
            await worker.run_once(worker_id=worker_id, now_ms=int(time.time() * 1000))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("context_merge_loop_failed", extra={"worker_id": worker_id})

        await asyncio.sleep(poll_interval_seconds)


async def _run_retention_loop(container: Container, settings: Settings) -> None:
    worker_id = f"{settings.service_name}:retention"
    poll_interval_seconds = settings.outbox_poll_interval_ms / 1000

    while True:
        try:
            worker = container.retention_worker()
            await worker.run_once(worker_id=worker_id, now_ms=int(time.time() * 1000))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("retention_loop_failed", extra={"worker_id": worker_id})

        await asyncio.sleep(poll_interval_seconds)
