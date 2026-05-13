import logging
from dataclasses import dataclass, field
from time import time
from typing import Any

from app.application.commands.agent_events import CoreAgentKweaverStreamCommand, DecisionAgentAgUiEventCommand
from app.application.use_cases.decision_agent_ag_ui import DecisionAgentAgUiEventHandler

logger = logging.getLogger(__name__)


@dataclass
class KweaverRunState:
    conversation_id: int
    turn_id: int
    message_id: int
    run_id: str
    ag_ui_sequence: int = 0
    last_progress: list[dict[str, Any]] = field(default_factory=list)
    text_started: bool = False
    run_started: bool = False


class KweaverToAgUiConverter:
    def __init__(self, *, handler: DecisionAgentAgUiEventHandler) -> None:
        self._handler = handler
        self._runs: dict[str, KweaverRunState] = {}

    async def process_stream_event(self, command: CoreAgentKweaverStreamCommand) -> None:
        run_key = f"{command.conversation_id}:{command.run_id}"
        state = self._runs.get(run_key)
        if state is None:
            state = KweaverRunState(
                conversation_id=command.conversation_id,
                turn_id=command.turn_id,
                message_id=command.message_id,
                run_id=command.run_id,
            )
            self._runs[run_key] = state

        now_ms = int(time() * 1000)
        kweaver_event = command.kweaver_event
        event_key = kweaver_event.get("key", "")
        content = kweaver_event.get("content")
        action = kweaver_event.get("action")
        finished = kweaver_event.get("finished", False)

        if not state.run_started:
            state.run_started = True
            state.ag_ui_sequence += 1
            await self._emit_event(state, command, "RUN_STARTED", now_ms)

        if content is not None:
            await self._process_content(state, command, event_key, content, now_ms)

        if finished:
            state.ag_ui_sequence += 1
            await self._emit_event(state, command, "RUN_FINISHED", now_ms)
            self._runs.pop(run_key, None)

    async def _process_content(
        self,
        state: KweaverRunState,
        command: CoreAgentKweaverStreamCommand,
        event_key: str,
        content: Any,
        now_ms: int,
    ) -> None:
        if isinstance(content, dict):
            progress = content.get("progress")
            if isinstance(progress, list):
                await self._process_progress_changes(state, command, progress, now_ms)

            answer = content.get("answer") or content.get("final_answer")
            if isinstance(answer, dict):
                answer_text = answer.get("answer", {})
                if isinstance(answer_text, dict):
                    text = answer_text.get("text", "")
                elif isinstance(answer_text, str):
                    text = answer_text
                else:
                    text = str(answer_text) if answer_text else ""
                if text:
                    await self._emit_text_message(state, command, text, now_ms)
        elif isinstance(content, str) and content:
            await self._emit_text_message(state, command, content, now_ms)

    async def _process_progress_changes(
        self,
        state: KweaverRunState,
        command: CoreAgentKweaverStreamCommand,
        progress: list[dict[str, Any]],
        now_ms: int,
    ) -> None:
        new_items = [p for p in progress if p not in state.last_progress]
        state.last_progress = list(progress)

        for item in new_items:
            skill_info = item.get("skill_info")
            status = item.get("status")
            result = item.get("result")
            answer = item.get("answer") or item.get("description")

            if skill_info is not None:
                state.ag_ui_sequence += 1
                await self._emit_event(
                    state,
                    command,
                    "ACTIVITY_SNAPSHOT",
                    now_ms,
                    messageId=f"tool-{state.ag_ui_sequence}",
                    activityType="conversation.ui.layout-tree",
                    content={
                        "contract": "conversation.ui.layout-tree@1",
                        "blockId": f"tool-call-{skill_info.get('name', 'unknown')}",
                        "ui": {"type": "paragraph", "props": {"text": f"Calling tool: {skill_info.get('name', 'unknown')}"}},
                        "meta": {"intent": "tool_call"},
                    },
                )

            if status is not None:
                event_type = "STEP_FINISHED" if status in ("completed", "finished", "success") else "STEP_STARTED"
                state.ag_ui_sequence += 1
                await self._emit_event(
                    state,
                    command,
                    event_type,
                    now_ms,
                    stepName=item.get("step_id", str(state.ag_ui_sequence)),
                )

            if result is not None and skill_info is not None:
                state.ag_ui_sequence += 1
                await self._emit_event(
                    state,
                    command,
                    "ACTIVITY_SNAPSHOT",
                    now_ms,
                    messageId=f"tool-result-{state.ag_ui_sequence}",
                    activityType="conversation.ui.layout-tree",
                    content={
                        "contract": "conversation.ui.layout-tree@1",
                        "blockId": f"tool-result-{skill_info.get('name', 'unknown')}",
                        "ui": {"type": "paragraph", "props": {"text": f"Tool result: {str(result)[:200]}"}},
                        "meta": {"intent": "tool_call"},
                    },
                )

            if answer is not None and skill_info is None:
                state.ag_ui_sequence += 1
                await self._emit_event(
                    state,
                    command,
                    "ACTIVITY_SNAPSHOT",
                    now_ms,
                    messageId=f"thought-{state.ag_ui_sequence}",
                    activityType="conversation.ui.layout-tree",
                    content={
                        "contract": "conversation.ui.layout-tree@1",
                        "blockId": f"thought-{state.ag_ui_sequence}",
                        "ui": {"type": "paragraph", "props": {"text": str(answer)[:200]}},
                        "meta": {"intent": "thought"},
                    },
                )

    async def _emit_text_message(
        self,
        state: KweaverRunState,
        command: CoreAgentKweaverStreamCommand,
        text: str,
        now_ms: int,
    ) -> None:
        if not state.text_started:
            state.text_started = True
            state.ag_ui_sequence += 1
            await self._emit_event(
                state,
                command,
                "TEXT_MESSAGE_START",
                now_ms,
                messageId=f"msg-{command.run_id}",
                role="assistant",
            )

        state.ag_ui_sequence += 1
        await self._emit_event(
            state,
            command,
            "TEXT_MESSAGE_CONTENT",
            now_ms,
            messageId=f"msg-{command.run_id}",
            delta=text,
        )

        state.ag_ui_sequence += 1
        await self._emit_event(
            state,
            command,
            "TEXT_MESSAGE_END",
            now_ms,
            messageId=f"msg-{command.run_id}",
        )

    async def _emit_event(
        self,
        state: KweaverRunState,
        command: CoreAgentKweaverStreamCommand,
        event_type: str,
        now_ms: int,
        **extra: Any,
    ) -> None:
        ag_ui_event: dict[str, Any] = {
            "type": event_type,
            "eventId": f"kw-{command.event_id}-{state.ag_ui_sequence}",
            "threadId": str(state.conversation_id),
            "runId": state.run_id,
            "sequence": state.ag_ui_sequence,
            "timestamp": now_ms,
        }
        ag_ui_event.update(extra)

        ag_ui_cmd = DecisionAgentAgUiEventCommand(
            event_id=ag_ui_event["eventId"],
            event_type="decision_agent.session.ag_ui_event",
            source_service=command.source_service,
            conversation_id=state.conversation_id,
            turn_id=state.turn_id,
            message_id=state.message_id,
            sequence=state.ag_ui_sequence,
            ag_ui_event=ag_ui_event,
            trace_id=command.trace_id,
            correlation_id=command.correlation_id,
            occurred_time=command.occurred_time or now_ms,
        )
        await self._handler.handle(ag_ui_cmd)
