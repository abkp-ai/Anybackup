import pytest

from app.application.ag_ui_templates.registry import AgUiTemplateRegistry
from app.application.ag_ui_templates.base import AgUiTemplate, AgUiTemplateResult
from app.application.ag_ui_templates.plan_candidates import PlanCandidatesTemplate
from app.application.ag_ui_templates.clarification_request import ClarificationRequestTemplate
from app.application.ag_ui_templates.text_message import TextMessageTemplate


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


def test_text_message_template_is_text_only() -> None:
    template = TextMessageTemplate()
    result = template.fill({"text": "操作完成"})
    assert result.is_text_only is True
    assert result.text_content == "操作完成"
