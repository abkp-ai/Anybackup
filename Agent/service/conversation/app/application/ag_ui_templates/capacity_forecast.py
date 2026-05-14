from typing import Any

from app.application.ag_ui_templates.layout_nodes import (
    action_row,
    badge_row,
    callout,
    chart,
    data_table,
    heading,
    kv_list,
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
        block_id_suffix = data.get("block_id_suffix")

        header_children: list[dict[str, Any]] = [heading("Capacity Forecast", level=2)]

        header_badges = data.get("header_badges")
        if header_badges:
            header_children.append(badge_row(header_badges))

        # CapacityMetric uses current/capacity, convert to metric_list format
        metric_items = [
            {"label": m["label"], "value": f"{m['current']}/{m['capacity']}", "unit": m.get("unit", "")}
            for m in metrics
        ]
        ui_children: list[dict[str, Any]] = [
            section(header_children),
            section([metric_list(metric_items)]),
        ]

        # 通用扩展：metadata
        report_metadata = data.get("metadata")
        if report_metadata:
            ui_children.append(section([kv_list(report_metadata)]))

        # 修复 Bug：forecast 数据实际渲染
        if forecast:
            fc_items = _get_forecast_attr(forecast, "items")
            fc_columns = _get_forecast_attr(forecast, "columns")
            fc_rows = _get_forecast_attr(forecast, "rows")
            fc_title = _get_forecast_attr(forecast, "title") or "Forecast"
            fc_chart_type = _get_forecast_attr(forecast, "chart_type")

            if fc_items:
                ui_children.append(section([chart(fc_items, title=fc_title, chart_type=fc_chart_type)]))
            if fc_columns and fc_rows:
                ui_children.append(section([data_table(fc_columns, fc_rows)]))

            # 兼容原始 dict 格式的 forecast
            if not fc_items and not (fc_columns and fc_rows) and isinstance(forecast, dict):
                remaining = {k: v for k, v in forecast.items() if k not in ("items", "columns", "rows", "title", "chart_type")}
                if remaining:
                    ui_children.append(section([heading(fc_title, level=3), kv_list(
                        [{"label": str(k), "value": str(v)} for k, v in remaining.items()]
                    )]))

        if warnings:
            for w in warnings:
                ui_children.append(callout(w["message"], tone=w.get("level", "warning")))

        # 通用扩展：callouts
        for c in data.get("callouts") or []:
            ui_children.append(callout(c["text"], tone=c.get("tone", "warning"), title=c.get("title")))

        # 通用扩展：extra_actions
        extra_actions = data.get("extra_actions")
        if extra_actions:
            action_ids = [a["id"] for a in extra_actions if "id" in a]
            if action_ids:
                ui_children.append(action_row(action_ids))

        ui = stack(ui_children, gap="md")
        meta: dict[str, Any] = {"intent": "result", "terminal": True}

        block_id = f"capacity-forecast-{block_id_suffix}" if block_id_suffix else "capacity-forecast"
        actions = extra_actions if extra_actions else None

        return AgUiTemplateResult(
            activity_content={
                "contract": "conversation.ui.layout-tree@1",
                "blockId": block_id,
                "ui": ui,
                "meta": meta,
                **({"actions": actions} if actions else {}),
            },
            meta=meta,
            actions=actions,
        )


def _get_forecast_attr(forecast: Any, attr: str) -> Any:
    if isinstance(forecast, dict):
        return forecast.get(attr)
    # Pydantic model — use model_fields to avoid builtin method conflicts (e.g. 'items')
    if hasattr(forecast, "model_fields") and attr in forecast.model_fields:
        return getattr(forecast, attr)
    if hasattr(forecast, "__dict__") and attr in forecast.__dict__:
        return forecast.__dict__[attr]
    return None
