from typing import Any

from app.application.ag_ui_templates.base import AgUiTemplate, AgUiTemplateResult


class TextMessageTemplate(AgUiTemplate):
    def fill(self, data: dict[str, Any]) -> AgUiTemplateResult:
        text = data["text"]
        return AgUiTemplateResult(
            activity_content={},
            meta={},
            text_content=text,
            is_text_only=True,
        )
