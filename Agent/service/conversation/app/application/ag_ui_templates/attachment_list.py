from typing import Any

from app.application.ag_ui_templates.layout_nodes import (
    attachment_list as attachment_list_node,
    heading,
    paragraph,
    section,
    stack,
)
from app.application.ag_ui_templates.base import AgUiTemplate, AgUiTemplateResult


class AttachmentListTemplate(AgUiTemplate):
    def fill(self, data: dict[str, Any]) -> AgUiTemplateResult:
        heading_text = data["heading"]
        subtitle = data.get("subtitle")
        attachments = data["attachments"]

        header_children: list[dict[str, Any]] = [heading(heading_text, level=2)]
        if subtitle:
            header_children.append(paragraph(subtitle))

        ui_children: list[dict[str, Any]] = [
            section(header_children),
            section([attachment_list_node(attachments)]),
        ]

        ui = stack(ui_children, gap="md")
        meta: dict[str, Any] = {"intent": "result", "terminal": True}

        return AgUiTemplateResult(
            activity_content={
                "contract": "conversation.ui.layout-tree@1",
                "blockId": f"attachments-{heading_text}",
                "ui": ui,
                "meta": meta,
            },
            meta=meta,
        )
