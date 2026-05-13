from typing import Any

from app.application.ag_ui_templates.layout_nodes import (
    heading,
    paragraph,
    section,
    stack,
)
from app.application.ag_ui_templates.base import AgUiTemplate, AgUiTemplateResult


class ReportDetailTemplate(AgUiTemplate):
    def fill(self, data: dict[str, Any]) -> AgUiTemplateResult:
        heading_text = data["heading"]
        subtitle = data.get("subtitle")
        summary = data.get("summary")
        sections = data.get("sections")

        ui_children: list[dict[str, Any]] = [section([heading(heading_text, level=2)])]

        if subtitle:
            ui_children.append(section([paragraph(subtitle)]))
        if summary:
            ui_children.append(section([paragraph(summary)]))

        if sections:
            for sec in sections:
                sec_children: list[dict[str, Any]] = [heading(sec["title"], level=3)]
                content = sec.get("content")
                if isinstance(content, str):
                    sec_children.append(paragraph(content))
                elif isinstance(content, dict):
                    sec_children.append(paragraph(str(content)))
                ui_children.append(section(sec_children, node_id=f"section-{sec.get('section_id', '')}"))

        ui = stack(ui_children, gap="md")
        meta: dict[str, Any] = {"intent": "result", "terminal": True}

        return AgUiTemplateResult(
            activity_content={
                "contract": "conversation.ui.layout-tree@1",
                "blockId": f"report-{heading_text}",
                "ui": ui,
                "meta": meta,
            },
            meta=meta,
        )
