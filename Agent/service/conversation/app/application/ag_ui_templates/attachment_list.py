from typing import Any

from app.application.ag_ui_templates.layout_nodes import (
    attachment_list as attachment_list_node,
    badge_row,
    heading,
    kv_list,
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

        header_badges = data.get("header_badges")
        if header_badges:
            header_children.append(badge_row(header_badges))

        ui_children: list[dict[str, Any]] = [
            section(header_children),
            section([attachment_list_node(attachments)]),
        ]

        # 通用扩展：每个附件的 badges/metadata
        attachment_details: list[dict[str, Any]] = []
        for a in attachments:
            badges = a.get("badges")
            metadata = a.get("metadata")
            if badges or metadata:
                detail_children: list[dict[str, Any]] = []
                if badges:
                    detail_children.append(badge_row(badges))
                if metadata:
                    detail_children.append(kv_list(metadata))
                attachment_details.append(section(detail_children))

        if attachment_details:
            ui_children.extend(attachment_details)

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
