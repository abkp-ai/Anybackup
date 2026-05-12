import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.application.models.conversation import AuthenticatedUser
from app.application.use_cases.ag_ui_runs import StartAgUiRunCommand
from app.interfaces.http.ag_ui_sse.schemas import (
    AgentCapabilities,
    AgentCapabilitiesHumanInTheLoop,
    AgentCapabilitiesIdentity,
    RunAgentInput,
)
from app.interfaces.http.v1.dependencies import require_user_context
from app.interfaces.http.v1.schemas import ERROR_RESPONSES

router = APIRouter(tags=["AG-UI"], responses=ERROR_RESPONSES)
logger = logging.getLogger(__name__)
_TERMINAL_EVENT_TYPES = frozenset({"RUN_FINISHED", "RUN_ERROR"})


@router.post(
    "/runs",
    operation_id="runAgent",
    response_class=StreamingResponse,
)
async def run_agent(
    request: Request,
    payload: RunAgentInput,
    user: Annotated[AuthenticatedUser, Depends(require_user_context)],
) -> StreamingResponse:
    handler = request.app.state.container.start_ag_ui_run_handler()
    result = await handler.handle(
        StartAgUiRunCommand(thread_id=payload.threadId, run_id=payload.runId),
        user,
    )
    return StreamingResponse(
        _db_first_sse_stream(
            request,
            conversation_id=result.conversation.conversation_id,
            run_id=payload.runId,
            after_sequence=_after_sequence(payload.forwardedProps),
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/capabilities",
    operation_id="getAgUiCapabilities",
    response_model=AgentCapabilities,
)
async def get_capabilities(
    user: Annotated[AuthenticatedUser, Depends(require_user_context)],
) -> AgentCapabilities:
    return AgentCapabilities(
        identity=AgentCapabilitiesIdentity(
            agentId="conversation-service",
            name="Conversation Service",
        ),
        humanInTheLoop=AgentCapabilitiesHumanInTheLoop(
            supported=True,
            modes=["tool_approval", "selection_snapshot"],
        ),
    )


async def _db_first_sse_stream(
    request: Request,
    *,
    conversation_id: int,
    run_id: str,
    after_sequence: int,
) -> AsyncIterator[str]:
    last_sequence = after_sequence
    idle_count = 0
    while True:
        if await request.is_disconnected():
            logger.info(
                "ag_ui_sse_client_disconnected",
                extra={"conversation_id": conversation_id, "run_id": run_id},
            )
            return
        async with request.app.state.container.unit_of_work() as unit_of_work:
            events = await unit_of_work.status_events.list_ag_ui_after_sequence(
                conversation_id,
                run_id=run_id,
                after_sequence=last_sequence,
                limit=50,
            )
        if not events:
            idle_count += 1
            await asyncio.sleep(0.05)
            if idle_count % 20 == 0:
                yield ": keep-alive\n\n"
            continue
        idle_count = 0
        for event in events:
            last_sequence = event.sequence
            payload = dict(event.payload)
            yield f"data: {json.dumps(payload, ensure_ascii=False, separators=(',', ':'))}\n\n"
            if payload.get("type") in _TERMINAL_EVENT_TYPES:
                return


def _after_sequence(forwarded_props: dict[str, object] | None) -> int:
    if forwarded_props is None:
        return 0
    raw_value = forwarded_props.get("afterSequence")
    if raw_value is None:
        return 0
    if isinstance(raw_value, bool):
        return 0
    if isinstance(raw_value, int):
        return max(raw_value, 0)
    if isinstance(raw_value, str) and raw_value.isdigit():
        return int(raw_value)
    return 0
