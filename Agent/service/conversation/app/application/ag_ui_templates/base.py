from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class AgUiTemplateResult:
    activity_content: dict[str, Any]
    state: dict[str, Any] | None = None
    meta: dict[str, Any] = field(default_factory=dict)
    actions: list[dict[str, Any]] | None = None
    text_content: str | None = None
    is_text_only: bool = False


class AgUiTemplate(ABC):
    @abstractmethod
    def fill(self, data: dict[str, Any]) -> AgUiTemplateResult: ...
