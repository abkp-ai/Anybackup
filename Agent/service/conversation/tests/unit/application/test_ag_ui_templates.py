from typing import Any

import pytest

from app.application.ag_ui_templates.registry import AgUiTemplateRegistry
from app.application.ag_ui_templates.base import AgUiTemplate, AgUiTemplateResult
from app.application.ag_ui_templates.plan_candidates import PlanCandidatesTemplate
from app.application.ag_ui_templates.progress_report import ProgressReportTemplate
from app.application.ag_ui_templates.clarification_request import ClarificationRequestTemplate
from app.application.ag_ui_templates.capacity_forecast import CapacityForecastTemplate
from app.application.ag_ui_templates.attachment_list import AttachmentListTemplate
from app.application.ag_ui_templates.report_detail import ReportDetailTemplate
from app.application.ag_ui_templates.text_message import TextMessageTemplate
from app.application.ag_ui_templates.incremental_update import IncrementalUpdateTemplate
from app.application.ag_ui_templates import layout_nodes


# --- Registry tests ---


def test_registry_returns_default_templates() -> None:
    registry = AgUiTemplateRegistry()
    for schema_type in (
        "plan_candidates", "progress_report", "clarification_request",
        "capacity_forecast", "attachment_list", "report_detail",
        "text_message", "incremental_update",
    ):
        template = registry.get_template(schema_type, "1")
        assert template is not None


def test_registry_raises_for_unknown_template() -> None:
    registry = AgUiTemplateRegistry()
    with pytest.raises(KeyError):
        registry.get_template("unknown", "1")


def test_registry_supports_custom_registration() -> None:
    registry = AgUiTemplateRegistry()

    class CustomTemplate(AgUiTemplate):
        def fill(self, data):
            return AgUiTemplateResult(activity_content={"custom": True})

    registry.register("custom_type", "1", CustomTemplate())
    result = registry.get_template("custom_type", "1").fill({})
    assert result.activity_content["custom"] is True


# --- PlanCandidates tests ---


def test_plan_candidates_template_with_2_candidates() -> None:
    template = PlanCandidatesTemplate()
    result = template.fill({
        "heading": "恢复候选方案",
        "candidates": [
            {
                "candidate_option_id": "a",
                "title": "方案A",
                "summary": "推荐方案",
                "recommendation_level": "recommended",
                "risk_level": "medium",
            },
            {
                "candidate_option_id": "b",
                "title": "方案B",
                "summary": "备选方案",
                "recommendation_level": "alternative",
                "risk_level": "low",
            },
        ],
    })
    assert result.activity_content["contract"] == "conversation.ui.layout-tree@1"
    assert result.activity_content["ui"] is not None
    assert result.meta["intent"] == "result"
    assert len(result.actions) == 2


def test_plan_candidates_template_with_selection() -> None:
    template = PlanCandidatesTemplate()
    result = template.fill({
        "heading": "选择方案",
        "candidates": [
            {"candidate_option_id": "a", "title": "A", "summary": "sa", "risk_level": "medium"},
        ],
        "selection": {"required": True, "selected_option_id": None},
    })
    assert result.state is not None
    assert "selection" in result.state


def test_plan_candidates_with_badges_and_metadata() -> None:
    template = PlanCandidatesTemplate()
    result = template.fill({
        "heading": "选择方案",
        "candidates": [
            {
                "candidate_option_id": "a",
                "title": "方案A",
                "summary": "推荐方案",
                "badges": [{"text": "Gold", "tone": "positive"}],
                "metadata": [{"label": "Cost", "value": "¥500/月"}],
                "callouts": [{"text": "需要先完成前置配置", "tone": "info", "title": "注意"}],
                "card_tone": "highlight",
            },
        ],
    })
    ui = result.activity_content["ui"]
    card_node = _find_node_by_type(ui, "card")
    assert card_node is not None
    assert card_node["props"]["tone"] == "highlight"
    badge = _find_node_by_type(ui, "badge-row")
    assert badge is not None
    assert any(b["text"] == "Gold" for b in badge["props"]["items"])
    kv = _find_node_by_type(ui, "kv-list")
    assert kv is not None
    assert any(r["label"] == "Cost" for r in kv["props"]["rows"])
    c = _find_node_by_type(ui, "callout")
    assert c is not None
    assert c["props"]["title"] == "注意"


def test_plan_candidates_legacy_fields_backward_compat() -> None:
    template = PlanCandidatesTemplate()
    result = template.fill({
        "heading": "选择方案",
        "candidates": [
            {
                "candidate_option_id": "a",
                "title": "方案A",
                "summary": "推荐方案",
                "rpo": "1h",
                "rto": "4h",
                "target": "存储A",
                "impact_summary": "影响较小",
            },
        ],
    })
    ui = result.activity_content["ui"]
    kv = _find_node_by_type(ui, "kv-list")
    assert kv is not None
    labels = [r["label"] for r in kv["props"]["rows"]]
    assert "RPO" in labels
    assert "RTO" in labels
    assert "Target" in labels
    c = _find_node_by_type(ui, "callout")
    assert c is not None


def test_plan_candidates_header_badges_and_metadata() -> None:
    template = PlanCandidatesTemplate()
    result = template.fill({
        "heading": "选择方案",
        "candidates": [
            {"candidate_option_id": "a", "title": "A", "summary": "sa"},
        ],
        "header_badges": [{"text": "3 options available", "tone": "info"}],
        "header_metadata": [{"label": "Policy", "value": "Daily"}],
    })
    ui = result.activity_content["ui"]
    badge = _find_node_by_type(ui, "badge-row")
    assert badge is not None
    kv = _find_node_by_type(ui, "kv-list")
    assert kv is not None


# --- ProgressReport tests ---


def test_progress_report_basic() -> None:
    template = ProgressReportTemplate()
    result = template.fill({
        "heading": "恢复进度",
        "stage": "executing",
        "steps": [
            {"step_id": "s1", "label": "扫描", "status": "completed"},
            {"step_id": "s2", "label": "恢复", "status": "in_progress"},
        ],
    })
    assert result.activity_content["contract"] == "conversation.ui.layout-tree@1"
    assert result.meta["intent"] == "progress"
    assert result.meta["terminal"] is False


def test_progress_report_structured_steps() -> None:
    template = ProgressReportTemplate()
    result = template.fill({
        "heading": "恢复进度",
        "stage": "executing",
        "steps": [
            {"step_id": "s1", "label": "扫描", "status": "completed"},
            {"step_id": "s2", "label": "恢复", "status": "failed"},
        ],
    })
    ui = result.activity_content["ui"]
    badge = _find_node_by_type(ui, "badge-row")
    assert badge is not None
    items = badge["props"]["items"]
    assert any("completed" in i["text"] for i in items)
    assert any("failed" in i["text"] for i in items)


def test_progress_report_with_progress_chart() -> None:
    template = ProgressReportTemplate()
    result = template.fill({
        "heading": "恢复进度",
        "stage": "executing",
        "steps": [{"step_id": "s1", "label": "扫描", "status": "completed"}],
        "progress_percent": 65,
    })
    ui = result.activity_content["ui"]
    chart_node = _find_node_by_type(ui, "chart")
    assert chart_node is not None
    assert chart_node["props"]["items"][0]["value"] == 65


def test_progress_report_with_error_callout() -> None:
    template = ProgressReportTemplate()
    result = template.fill({
        "heading": "恢复进度",
        "stage": "failed",
        "steps": [{"step_id": "s1", "label": "扫描", "status": "failed"}],
        "error": {"message": "连接超时", "tone": "danger", "title": "错误"},
    })
    ui = result.activity_content["ui"]
    c = _find_node_by_type(ui, "callout")
    assert c is not None
    assert c["props"]["tone"] == "danger"
    assert c["props"]["title"] == "错误"


def test_progress_report_with_extra_actions() -> None:
    template = ProgressReportTemplate()
    result = template.fill({
        "heading": "恢复进度",
        "stage": "executing",
        "steps": [{"step_id": "s1", "label": "扫描", "status": "in_progress"}],
        "extra_actions": [{"id": "cancel-op", "kind": "submit_message", "label": "取消", "payload": {}}],
    })
    ui = result.activity_content["ui"]
    ar = _find_node_by_type(ui, "action-row")
    assert ar is not None
    assert "cancel-op" in ar["props"]["actionIds"]


def test_progress_report_with_metadata() -> None:
    template = ProgressReportTemplate()
    result = template.fill({
        "heading": "恢复进度",
        "stage": "executing",
        "steps": [{"step_id": "s1", "label": "扫描", "status": "in_progress"}],
        "metadata": [{"label": "Started", "value": "2026-05-13 10:00"}],
    })
    ui = result.activity_content["ui"]
    kv = _find_node_by_type(ui, "kv-list")
    assert kv is not None


# --- ClarificationRequest tests ---


def test_clarification_template_with_3_options() -> None:
    template = ClarificationRequestTemplate()
    result = template.fill({
        "question": "选择恢复类型",
        "options": [
            {"option_id": "1", "label": "全量恢复"},
            {"option_id": "2", "label": "增量恢复"},
            {"option_id": "3", "label": "日志恢复"},
        ],
    })
    assert result.activity_content["contract"] == "conversation.ui.layout-tree@1"
    assert result.meta["intent"] == "clarification"
    assert len(result.actions) == 3


def test_clarification_with_recommendation() -> None:
    template = ClarificationRequestTemplate()
    result = template.fill({
        "question": "选择恢复类型",
        "options": [
            {"option_id": "1", "label": "全量恢复", "is_recommended": True},
            {"option_id": "2", "label": "增量恢复"},
        ],
    })
    ui = result.activity_content["ui"]
    card_nodes = _find_all_nodes_by_type(ui, "card")
    assert any(c["props"].get("tone") == "highlight" for c in card_nodes)
    badge = _find_node_by_type(ui, "badge-row")
    assert badge is not None
    assert any(b["text"] == "Recommended" for b in badge["props"]["items"])


def test_clarification_with_free_text() -> None:
    template = ClarificationRequestTemplate()
    result = template.fill({
        "question": "选择恢复类型",
        "options": [{"option_id": "1", "label": "全量恢复"}],
        "allows_free_text": True,
        "free_text_placeholder": "输入自定义答案",
    })
    assert len(result.actions) == 2
    free_text_action = [a for a in result.actions if a["id"] == "clarification-free-text"]
    assert len(free_text_action) == 1
    assert free_text_action[0]["payload"]["freeText"] is True


def test_clarification_with_option_metadata() -> None:
    template = ClarificationRequestTemplate()
    result = template.fill({
        "question": "选择恢复类型",
        "options": [
            {
                "option_id": "1",
                "label": "全量恢复",
                "badges": [{"text": "快速", "tone": "positive"}],
                "metadata": [{"label": "Duration", "value": "~30min"}],
                "callouts": [{"text": "将覆盖现有数据", "tone": "warning", "title": "注意"}],
            },
        ],
    })
    ui = result.activity_content["ui"]
    kv = _find_node_by_type(ui, "kv-list")
    assert kv is not None
    assert any(r["label"] == "Duration" for r in kv["props"]["rows"])
    c = _find_node_by_type(ui, "callout")
    assert c is not None


# --- CapacityForecast tests ---


def test_capacity_forecast_basic() -> None:
    template = CapacityForecastTemplate()
    result = template.fill({
        "metrics": [
            {"label": "Storage", "current": "2.1TB", "capacity": "5TB", "unit": ""},
        ],
    })
    assert result.activity_content["contract"] == "conversation.ui.layout-tree@1"
    assert result.meta["intent"] == "result"


def test_capacity_forecast_renders_forecast_data() -> None:
    template = CapacityForecastTemplate()
    result = template.fill({
        "metrics": [
            {"label": "Storage", "current": "2.1TB", "capacity": "5TB", "unit": ""},
        ],
        "forecast": {
            "items": [
                {"label": "Current", "value": 42, "tone": "positive"},
                {"label": "Projected (30d)", "value": 78, "tone": "warning"},
            ],
            "title": "30-Day Forecast",
        },
    })
    ui = result.activity_content["ui"]
    chart_node = _find_node_by_type(ui, "chart")
    assert chart_node is not None
    assert chart_node["props"]["title"] == "30-Day Forecast"
    assert len(chart_node["props"]["items"]) == 2


def test_capacity_forecast_with_chart_and_table() -> None:
    template = CapacityForecastTemplate()
    result = template.fill({
        "metrics": [
            {"label": "Storage", "current": "2.1TB", "capacity": "5TB", "unit": ""},
        ],
        "forecast": {
            "items": [{"label": "Current", "value": 42}],
            "columns": [{"key": "month", "label": "Month"}, {"key": "usage", "label": "Usage"}],
            "rows": [{"month": "Jan", "usage": "42%"}, {"month": "Feb", "usage": "55%"}],
            "chart_type": "bar",
        },
    })
    ui = result.activity_content["ui"]
    chart_node = _find_node_by_type(ui, "chart")
    assert chart_node is not None
    dt = _find_node_by_type(ui, "data-table")
    assert dt is not None
    assert dt["props"]["columns"][0]["key"] == "month"


def test_capacity_forecast_block_id_suffix() -> None:
    template = CapacityForecastTemplate()
    result = template.fill({
        "metrics": [{"label": "Storage", "current": "2.1TB", "capacity": "5TB"}],
        "block_id_suffix": "storage-pool-1",
    })
    assert result.activity_content["blockId"] == "capacity-forecast-storage-pool-1"


def test_capacity_forecast_with_callouts() -> None:
    template = CapacityForecastTemplate()
    result = template.fill({
        "metrics": [{"label": "Storage", "current": "2.1TB", "capacity": "5TB"}],
        "callouts": [{"text": "建议扩容", "tone": "warning", "title": "建议"}],
    })
    ui = result.activity_content["ui"]
    c = _find_node_by_type(ui, "callout")
    assert c is not None
    assert c["props"]["title"] == "建议"


# --- ReportDetail tests ---


def test_report_detail_basic() -> None:
    template = ReportDetailTemplate()
    result = template.fill({
        "heading": "恢复报告",
        "sections": [
            {"section_id": "s1", "title": "概述", "content": "恢复已完成"},
        ],
    })
    assert result.activity_content["contract"] == "conversation.ui.layout-tree@1"
    assert result.meta["intent"] == "result"


def test_report_detail_with_dict_content_renders_kv_list() -> None:
    template = ReportDetailTemplate()
    result = template.fill({
        "heading": "恢复报告",
        "sections": [
            {"section_id": "s1", "title": "详细信息", "content": {"key1": "value1", "key2": "value2"}},
        ],
    })
    ui = result.activity_content["ui"]
    kv = _find_node_by_type(ui, "kv-list")
    assert kv is not None
    labels = [r["label"] for r in kv["props"]["rows"]]
    assert "key1" in labels
    assert "key2" in labels


def test_report_detail_section_type_steps() -> None:
    template = ReportDetailTemplate()
    result = template.fill({
        "heading": "恢复报告",
        "sections": [
            {"section_id": "s1", "title": "执行步骤", "section_type": "steps",
             "content": {"step1": "扫描数据", "step2": "执行恢复"}},
        ],
    })
    ui = result.activity_content["ui"]
    md = _find_node_by_type(ui, "markdown")
    assert md is not None


def test_report_detail_section_type_data() -> None:
    template = ReportDetailTemplate()
    result = template.fill({
        "heading": "恢复报告",
        "sections": [
            {"section_id": "s1", "title": "数据", "section_type": "data",
             "content": {"name": "db1", "size": "10GB"}},
        ],
    })
    ui = result.activity_content["ui"]
    dt = _find_node_by_type(ui, "data-table")
    assert dt is not None


def test_report_detail_section_type_risk() -> None:
    template = ReportDetailTemplate()
    result = template.fill({
        "heading": "恢复报告",
        "sections": [
            {"section_id": "s1", "title": "风险评估", "section_type": "risk",
             "content": {"data_loss": "possible", "downtime": "2h"}},
        ],
    })
    ui = result.activity_content["ui"]
    c = _find_node_by_type(ui, "callout")
    assert c is not None
    assert c["props"]["tone"] == "warning"


def test_report_detail_with_layout_nodes() -> None:
    template = ReportDetailTemplate()
    result = template.fill({
        "heading": "恢复报告",
        "sections": [
            {
                "section_id": "s1",
                "title": "自定义段落",
                "layout_nodes": [
                    {"type": "metric-list", "props": {"items": [{"label": "X", "value": "99", "unit": "%"}]}},
                ],
            },
        ],
    })
    ui = result.activity_content["ui"]
    ml = _find_node_by_type(ui, "metric-list")
    assert ml is not None


def test_report_detail_with_tabs() -> None:
    template = ReportDetailTemplate()
    sections = [
        {"section_id": f"s{i}", "title": f"段落{i}", "content": f"内容{i}"}
        for i in range(5)
    ]
    result = template.fill({
        "heading": "详细报告",
        "sections": sections,
        "use_tabs": True,
    })
    ui = result.activity_content["ui"]
    tabs_node = _find_node_by_type(ui, "tabs")
    assert tabs_node is not None
    assert len(tabs_node["props"]["items"]) == 5


def test_report_detail_with_navigation() -> None:
    template = ReportDetailTemplate()
    result = template.fill({
        "heading": "报告",
        "sections": [
            {"section_id": "s1", "title": "概述", "content": "内容"},
        ],
        "navigation": [{"section_id": "s1", "title": "概述"}],
    })
    ui = result.activity_content["ui"]
    badge = _find_node_by_type(ui, "badge-row")
    assert badge is not None


def test_report_detail_with_header_badges_and_metadata() -> None:
    template = ReportDetailTemplate()
    result = template.fill({
        "heading": "报告",
        "header_badges": [{"text": "Final", "tone": "positive"}],
        "metadata": [{"label": "Author", "value": "System"}],
        "sections": [
            {"section_id": "s1", "title": "概述", "content": "内容"},
        ],
    })
    ui = result.activity_content["ui"]
    badge = _find_node_by_type(ui, "badge-row")
    assert badge is not None
    kv = _find_node_by_type(ui, "kv-list")
    assert kv is not None


# --- AttachmentList tests ---


def test_attachment_list_basic() -> None:
    template = AttachmentListTemplate()
    result = template.fill({
        "heading": "附件列表",
        "attachments": [
            {"attachment_id": "a1", "filename": "report.pdf", "size": 1024, "download_url": "/dl/a1"},
        ],
    })
    assert result.activity_content["contract"] == "conversation.ui.layout-tree@1"
    assert result.meta["intent"] == "result"


def test_attachment_list_with_title_and_summary() -> None:
    template = AttachmentListTemplate()
    result = template.fill({
        "heading": "附件列表",
        "attachments": [
            {
                "attachment_id": "a1",
                "filename": "report.pdf",
                "size": 1024,
                "download_url": "/dl/a1",
                "title": "恢复报告",
                "summary": "2026年5月恢复结果报告",
            },
        ],
    })
    ui = result.activity_content["ui"]
    al = _find_node_by_type(ui, "attachment-list")
    assert al is not None
    item = al["props"]["items"][0]
    assert item["title"] == "恢复报告"
    assert item["summary"] == "2026年5月恢复结果报告"


def test_attachment_list_with_badges() -> None:
    template = AttachmentListTemplate()
    result = template.fill({
        "heading": "附件列表",
        "attachments": [
            {
                "attachment_id": "a1",
                "filename": "report.pdf",
                "size": 1024,
                "download_url": "/dl/a1",
                "badges": [{"text": "PDF", "tone": "info"}],
                "metadata": [{"label": "Created", "value": "2026-05-13"}],
            },
        ],
    })
    ui = result.activity_content["ui"]
    badge = _find_node_by_type(ui, "badge-row")
    assert badge is not None


# --- TextMessage tests ---


def test_text_message_template_is_text_only() -> None:
    template = TextMessageTemplate()
    result = template.fill({"text": "操作完成"})
    assert result.is_text_only is True
    assert result.text_content == "操作完成"


def test_text_message_with_markdown_format() -> None:
    template = TextMessageTemplate()
    result = template.fill({
        "text": "**重要通知**\n\n恢复已完成，请查看[报告](/report)。",
        "format_hint": "markdown",
    })
    assert result.is_text_only is False
    ui = result.activity_content["ui"]
    md = _find_node_by_type(ui, "markdown")
    assert md is not None


def test_text_message_with_badges() -> None:
    template = TextMessageTemplate()
    result = template.fill({
        "text": "**重要通知**",
        "format_hint": "markdown",
        "badges": [{"text": "System", "tone": "info"}],
    })
    ui = result.activity_content["ui"]
    badge = _find_node_by_type(ui, "badge-row")
    assert badge is not None


# --- IncrementalUpdate tests ---


def test_incremental_update_basic() -> None:
    template = IncrementalUpdateTemplate()
    result = template.fill({
        "target_block_id": "progress-restore",
        "patch": [{"op": "replace", "path": "/stage", "value": "completed"}],
    })
    assert result.activity_content["contract"] == "conversation.ui.layout-tree@1"
    assert result.meta["intent"] == "update"


def test_incremental_update_with_patch_type() -> None:
    template = IncrementalUpdateTemplate()
    result = template.fill({
        "target_block_id": "progress-restore",
        "patch": [{"op": "replace", "path": "/stage", "value": "completed"}],
        "patch_type": "status_change",
        "version": 3,
    })
    assert result.meta["patch_type"] == "status_change"
    assert result.activity_content["version"] == 3


# --- Layout nodes builder tests ---


def test_data_table_uses_column_key_schema() -> None:
    node = layout_nodes.data_table(
        columns=[{"key": "name", "label": "Name"}, {"key": "age", "label": "Age"}],
        rows=[{"name": "Alice", "age": "30"}, {"name": "Bob", "age": "25"}],
    )
    assert node["type"] == "data-table"
    assert node["props"]["columns"][0]["key"] == "name"
    assert node["props"]["rows"][0]["name"] == "Alice"


def test_attachment_list_includes_title_and_summary() -> None:
    node = layout_nodes.attachment_list([
        {
            "attachment_id": "a1",
            "filename": "report.pdf",
            "size": 1024,
            "download_url": "/dl/a1",
            "title": "恢复报告",
            "summary": "2026年5月",
        },
    ])
    item = node["props"]["items"][0]
    assert item["title"] == "恢复报告"
    assert item["summary"] == "2026年5月"
    assert item["text"] == "report.pdf"


def test_callout_with_title() -> None:
    node = layout_nodes.callout("message", title="Warning")
    assert node["props"]["title"] == "Warning"


def test_card_with_title_and_tone() -> None:
    node = layout_nodes.card([], title="Plan A", tone="highlight")
    assert node["props"]["title"] == "Plan A"
    assert node["props"]["tone"] == "highlight"


def test_tabs_builder() -> None:
    node = layout_nodes.tabs(
        [],
        items=[{"id": "tab1", "label": "Tab 1"}],
        default_tab_id="tab1",
    )
    assert node["type"] == "tabs"
    assert node["props"]["items"][0]["id"] == "tab1"
    assert node["props"]["defaultTabId"] == "tab1"


def test_divider_builder() -> None:
    node = layout_nodes.divider()
    assert node["type"] == "divider"


def test_chart_with_items_and_title() -> None:
    node = layout_nodes.chart(
        items=[{"label": "A", "value": 10}, {"label": "B", "value": 20}],
        title="Usage Chart",
        chart_type="bar",
    )
    assert node["type"] == "chart"
    assert node["props"]["title"] == "Usage Chart"
    assert node["props"]["chartType"] == "bar"
    assert len(node["props"]["items"]) == 2


# --- Helpers ---


def _find_node_by_type(tree: dict[str, Any], node_type: str) -> dict[str, Any] | None:
    result = _find_all_nodes_by_type(tree, node_type)
    return result[0] if result else None


def _find_all_nodes_by_type(tree: dict[str, Any], node_type: str) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    _walk_tree(tree, node_type, results)
    return results


def _walk_tree(node: Any, target_type: str, results: list[dict[str, Any]]) -> None:
    if isinstance(node, dict):
        if node.get("type") == target_type:
            results.append(node)
        for v in node.values():
            _walk_tree(v, target_type, results)
    elif isinstance(node, list):
        for item in node:
            _walk_tree(item, target_type, results)
