from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(slots=True)
class SessionTracker:
    _seen_event_ids: set[str] = field(default_factory=set)
    _next_ag_ui_sequence_by_key: dict[str, int] = field(default_factory=dict)

    def mark_seen(self, event_id: str) -> bool:
        if event_id in self._seen_event_ids:
            return False
        self._seen_event_ids.add(event_id)
        return True

    def reserve_ag_ui_sequences(self, conversation_id: str, count: int, *, message_id: str = "") -> range:
        key = f"{conversation_id}:{message_id}"
        next_sequence = self._next_ag_ui_sequence_by_key.get(key, 1)
        self._next_ag_ui_sequence_by_key[key] = next_sequence + count
        return range(next_sequence, next_sequence + count)


def core_agent_run_id(conversation_id: str, message_id: str) -> str:
    return f"mock-run-{conversation_id}-{message_id}"
