import logging
from time import time
from typing import Any

from app.application.ag_ui_templates.registry import AgUiTemplateRegistry
from app.application.ag_ui_templates.base import AgUiTemplateResult
from app.application.commands.agent_events import DecisionAgentAgUiEventCommand, DecisionAgentBusinessDataCommand
from app.application.use_cases.decision_agent_ag_ui import DecisionAgentAgUiEventHandler
from app.domain.business_data_schemas import validate_business_data

logger = logging.getLogger(__name__)


class BusinessDataToAgUiConverter:
    def __init__(
        self,
        *,
        template_registry: AgUiTemplateRegistry,
        handler: DecisionAgentAgUiEventHandler,
    ) -> None:
        self._template_registry = template_registry
        self._handler = handler

    async def process_business_data(self, command: DecisionAgentBusinessDataCommand) -> None:
        logger.info(
            "business_data_to_ag_ui_enter",
            extra={
                "event_id": command.event_id,
                "schema_type": command.schema_type,
                "conversation_id": command.conversation_id,
            },
        )

        validate_business_data(command.schema_type, command.schema_version, command.data)

        template = self._template_registry.get_template(command.schema_type, command.schema_version)
        result = template.fill(command.data)

        now_ms = int(time() * 1000)

        if result.is_text_only:
            await self._emit_text_message_events(command, result.text_content or "", now_ms)
        elif result.activity_content.get("patch") is not None:
            await self._emit_activity_delta(command, result, now_ms)
        else:
            await self._emit_activity_snapshot_events(command, result, now_ms)

    async def _emit_text_message_events(
        self,
        command: DecisionAgentBusinessDataCommand,
        text: str,
        now_ms: int,
    ) -> None:
        msg_id = f"msg-{command.event_id}"
        events = [
            _make_event(command, "TEXT_MESSAGE_START", now_ms, messageId=msg_id, role="assistant"),
            _make_event(command, "TEXT_MESSAGE_CONTENT", now_ms, messageId=msg_id, delta=text),
            _make_event(command, "TEXT_MESSAGE_END", now_ms, messageId=msg_id),
        ]
        for event in events:
            ag_ui_cmd = _to_ag_ui_command(command, event, command.sequence)
            await self._handler.handle(ag_ui_cmd)

    async def _emit_activity_snapshot_events(
        self,
        command: DecisionAgentBusinessDataCommand,
        result: Any,
        now_ms: int,
    ) -> None:
        activity_event = _make_event(
            command,
            "ACTIVITY_SNAPSHOT",
            now_ms,
            messageId=f"act-{command.event_id}",
            activityType="conversation.ui.layout-tree",
            content=result.activity_content,
        )
        ag_ui_cmd = _to_ag_ui_command(command, activity_event, command.sequence)
        await self._handler.handle(ag_ui_cmd)

        if result.state is not None:
            state_event = _make_event(
                command,
                "STATE_SNAPSHOT",
                now_ms,
                messageId=f"state-{command.event_id}",
                state=result.state,
            )
            state_cmd = _to_ag_ui_command(command, state_event, command.sequence + 1)
            await self._handler.handle(state_cmd)

    async def _emit_activity_delta(
        self,
        command: DecisionAgentBusinessDataCommand,
        result: Any,
        now_ms: int,
    ) -> None:
        delta_event = _make_event(
            command,
            "ACTIVITY_DELTA",
            now_ms,
            messageId=f"delta-{command.event_id}",
            delta=result.activity_content,
        )
        ag_ui_cmd = _to_ag_ui_command(command, delta_event, command.sequence)
        await self._handler.handle(ag_ui_cmd)


def _make_event(
    command: DecisionAgentBusinessDataCommand,
    event_type: str,
    timestamp: int,
    **extra: Any,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "type": event_type,
        "eventId": command.event_id,
        "threadId": str(command.conversation_id),
        "runId": str(command.turn_id),
        "sequence": command.sequence,
        "timestamp": timestamp,
    }
    event.update(extra)
    return event


def _to_ag_ui_command(
    command: DecisionAgentBusinessDataCommand,
    ag_ui_event: dict[str, Any],
    sequence: int,
) -> DecisionAgentAgUiEventCommand:
    return DecisionAgentAgUiEventCommand(
        event_id=f"{command.event_id}-{ag_ui_event['type']}",
        event_type="decision_agent.session.ag_ui_event",
        source_service=command.source_service,
        conversation_id=command.conversation_id,
        turn_id=command.turn_id,
        message_id=command.message_id,
        sequence=sequence,
        ag_ui_event=ag_ui_event,
        trace_id=command.trace_id,
        correlation_id=command.correlation_id,
        occurred_time=command.occurred_time,
    )
