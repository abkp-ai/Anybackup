from typing import Any

from app.application.ag_ui_templates.layout_nodes import badge_row, markdown, section, stack
from app.application.ag_ui_templates.base import AgUiTemplate, AgUiTemplateResult


class TextMessageTemplate(AgUiTemplate):
    def fill(self, data: dict[str, Any]) -> AgUiTemplateResult:
        text = data["text"]
        format_hint = data.get("format_hint")
        badges = data.get("badges")

        if format_hint == "markdown":
            ui_children: list[dict[str, Any]] = []
            if badges:
                ui_children.append(section([badge_row(badges)]))
            ui_children.append(section([markdown(text)]))
            ui = stack(ui_children, gap="sm")
            return AgUiTemplateResult(
                activity_content={
                    "contract": "conversation.ui.layout-tree@1",
                    "blockId": "text-message",
                    "ui": ui,
                    "meta": {},
                },
                meta={},
            )

        return AgUiTemplateResult(
            activity_content={},
            meta={},
            text_content=text,
            is_text_only=True,
        )
