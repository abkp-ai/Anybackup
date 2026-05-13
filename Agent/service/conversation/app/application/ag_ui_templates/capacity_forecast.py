from typing import Any

from app.application.ag_ui_templates.layout_nodes import (
    callout,
    heading,
    metric_list,
    section,
    stack,
)
from app.application.ag_ui_templates.base import AgUiTemplate, AgUiTemplateResult


class CapacityForecastTemplate(AgUiTemplate):
    def fill(self, data: dict[str, Any]) -> AgUiTemplateResult:
        metrics = data["metrics"]
        forecast = data.get("forecast")
        warnings = data.get("warnings")

        ui_children: list[dict[str, Any]] = [
            section([heading("Capacity Forecast", level=2)]),
            section([metric_list(metrics)]),
        ]

        if forecast:
            ui_children.append(section([heading("Forecast", level=3)]))

        if warnings:
            for w in warnings:
                ui_children.append(callout(w["message"], tone=w.get("level", "warning")))

        ui = stack(ui_children, gap="md")
        meta: dict[str, Any] = {"intent": "result", "terminal": True}

        return AgUiTemplateResult(
            activity_content={
                "contract": "conversation.ui.layout-tree@1",
                "blockId": "capacity-forecast",
                "ui": ui,
                "meta": meta,
            },
            meta=meta,
        )
