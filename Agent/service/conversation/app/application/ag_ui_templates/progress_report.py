from typing import Any

from app.application.ag_ui_templates.layout_nodes import (
    callout,
    heading,
    metric_list,
    paragraph,
    section,
    stack,
)
from app.application.ag_ui_templates.base import AgUiTemplate, AgUiTemplateResult


class ProgressReportTemplate(AgUiTemplate):
    def fill(self, data: dict[str, Any]) -> AgUiTemplateResult:
        heading_text = data["heading"]
        subtitle = data.get("subtitle")
        stage = data["stage"]
        steps = data.get("steps", [])
        progress_percent = data.get("progress_percent")
        eta = data.get("eta")
        metrics = data.get("metrics")

        header_children: list[dict[str, Any]] = [heading(heading_text, level=2)]
        if subtitle:
            header_children.append(paragraph(subtitle))
        header_children.append(paragraph(f"Stage: {stage}"))

        ui_children: list[dict[str, Any]] = [section(header_children)]

        if metrics:
            ui_children.append(section([metric_list(metrics)]))

        if progress_percent is not None:
            ui_children.append(section([paragraph(f"Progress: {progress_percent}%")]))

        if steps:
            step_items = []
            for step in steps:
                status = step.get("status", "pending")
                label = step.get("label", step.get("step_id", ""))
                step_items.append(f"[{status}] {label}")
            ui_children.append(section([paragraph("\n".join(step_items))]))

        if eta:
            ui_children.append(section([paragraph(f"Estimated time: {eta}")]))

        ui = stack(ui_children, gap="md")
        meta: dict[str, Any] = {"intent": "progress", "terminal": False}

        return AgUiTemplateResult(
            activity_content={
                "contract": "conversation.ui.layout-tree@1",
                "blockId": f"progress-{heading_text}",
                "ui": ui,
                "meta": meta,
            },
            meta=meta,
        )
