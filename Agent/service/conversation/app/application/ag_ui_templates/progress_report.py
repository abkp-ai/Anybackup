from typing import Any

from app.application.ag_ui_templates.layout_nodes import (
    action_row,
    badge_row,
    callout,
    chart,
    heading,
    kv_list,
    metric_list,
    paragraph,
    section,
    stack,
)
from app.application.ag_ui_templates.base import AgUiTemplate, AgUiTemplateResult

_STEP_STATUS_TONE = {
    "completed": "positive",
    "done": "positive",
    "in_progress": "info",
    "running": "info",
    "failed": "danger",
    "error": "danger",
    "pending": "neutral",
    "skipped": "warning",
}


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
            ui_children.append(section([chart(
                items=[{"label": "Progress", "value": progress_percent, "tone": "positive"}],
                title=f"Progress: {progress_percent}%",
            )]))

        if steps:
            step_badges: list[dict[str, str]] = []
            for step in steps:
                status = step.get("status", "pending")
                label = step.get("label", step.get("step_id", ""))
                tone = _STEP_STATUS_TONE.get(status, "neutral")
                step_badges.append({"text": f"{label}: {status}", "tone": tone})
            ui_children.append(section([badge_row(step_badges)]))

        if eta:
            ui_children.append(section([paragraph(f"Estimated time: {eta}")]))

        # 通用扩展：error
        error = data.get("error")
        if error:
            ui_children.append(callout(
                error.get("message", str(error)),
                tone=error.get("tone", "danger"),
                title=error.get("title"),
            ))

        # 通用扩展：callouts
        for c in data.get("callouts") or []:
            ui_children.append(callout(c["text"], tone=c.get("tone", "warning"), title=c.get("title")))

        # 通用扩展：metadata
        report_metadata = data.get("metadata")
        if report_metadata:
            ui_children.append(section([kv_list(report_metadata)]))

        # 通用扩展：extra_actions
        extra_actions = data.get("extra_actions")
        if extra_actions:
            action_ids = [a["id"] for a in extra_actions if "id" in a]
            if action_ids:
                ui_children.append(action_row(action_ids))

        ui = stack(ui_children, gap="md")
        meta: dict[str, Any] = {"intent": "progress", "terminal": False}

        actions = extra_actions if extra_actions else None

        return AgUiTemplateResult(
            activity_content={
                "contract": "conversation.ui.layout-tree@1",
                "blockId": f"progress-{heading_text}",
                "ui": ui,
                "meta": meta,
                **({"actions": actions} if actions else {}),
            },
            meta=meta,
            actions=actions,
        )
