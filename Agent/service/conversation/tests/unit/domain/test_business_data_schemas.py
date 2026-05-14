import pytest

from app.domain.business_data_schemas import (
    ALLOWED_SCHEMA_TYPES,
    validate_business_data,
)


def test_validate_plan_candidates() -> None:
    result = validate_business_data("plan_candidates", "1", {
        "heading": "恢复候选方案",
        "candidates": [
            {
                "candidate_option_id": "a",
                "title": "方案A",
                "summary": "推荐方案",
                "recommendation_level": "recommended",
                "risk_level": "medium",
            }
        ],
    })
    assert result.model_dump()["heading"] == "恢复候选方案"


def test_validate_plan_candidates_rejects_empty_candidates() -> None:
    with pytest.raises(Exception):
        validate_business_data("plan_candidates", "1", {
            "heading": "空方案",
            "candidates": [],
        })


def test_validate_text_message() -> None:
    result = validate_business_data("text_message", "1", {"text": "hello"})
    assert result.model_dump()["text"] == "hello"


def test_validate_clarification_request() -> None:
    result = validate_business_data("clarification_request", "1", {
        "question": "选择恢复类型",
        "options": [
            {"option_id": "1", "label": "全量恢复"},
            {"option_id": "2", "label": "增量恢复"},
        ],
    })
    assert len(result.model_dump()["options"]) == 2


def test_validate_progress_report() -> None:
    result = validate_business_data("progress_report", "1", {
        "heading": "恢复进度",
        "stage": "processing",
        "steps": [
            {"step_id": "1", "label": "连接数据库", "status": "completed"},
            {"step_id": "2", "label": "传输数据", "status": "running"},
        ],
    })
    assert result.model_dump()["stage"] == "processing"


def test_validate_rejects_unknown_schema_type() -> None:
    with pytest.raises(ValueError, match="unknown schema_type"):
        validate_business_data("unknown_type", "1", {})


def test_validate_rejects_unsupported_version() -> None:
    with pytest.raises(ValueError, match="unsupported schema_version"):
        validate_business_data("text_message", "2", {"text": "hello"})


def test_allowed_schema_types_has_8_entries() -> None:
    assert len(ALLOWED_SCHEMA_TYPES) == 8


@pytest.mark.parametrize("schema_type", [
    "plan_candidates", "progress_report", "clarification_request",
    "capacity_forecast", "attachment_list", "report_detail",
    "text_message", "incremental_update",
])
def test_all_schema_types_are_allowed(schema_type: str) -> None:
    assert schema_type in ALLOWED_SCHEMA_TYPES


# --- Extension fields validation ---


def test_plan_candidates_with_extension_fields() -> None:
    result = validate_business_data("plan_candidates", "1", {
        "heading": "选择方案",
        "candidates": [
            {
                "candidate_option_id": "a",
                "title": "方案A",
                "summary": "推荐",
                "badges": [{"text": "Gold", "tone": "positive"}],
                "metadata": [{"label": "Cost", "value": "¥500"}],
                "callouts": [{"text": "需要前置配置", "tone": "info"}],
                "card_tone": "highlight",
            },
        ],
        "header_badges": [{"text": "3 options", "tone": "info"}],
        "header_metadata": [{"label": "Policy", "value": "Daily"}],
    })
    d = result.model_dump()
    assert d["candidates"][0]["badges"] == [{"text": "Gold", "tone": "positive"}]
    assert d["candidates"][0]["card_tone"] == "highlight"
    assert d["header_badges"] is not None


def test_plan_candidates_legacy_fields_still_valid() -> None:
    result = validate_business_data("plan_candidates", "1", {
        "heading": "选择方案",
        "candidates": [
            {
                "candidate_option_id": "a",
                "title": "方案A",
                "summary": "推荐",
                "rpo": "1h",
                "rto": "4h",
                "target": "存储A",
                "impact_summary": "影响较小",
            },
        ],
    })
    d = result.model_dump()
    assert d["candidates"][0]["rpo"] == "1h"


def test_progress_report_with_extension_fields() -> None:
    result = validate_business_data("progress_report", "1", {
        "heading": "恢复进度",
        "stage": "executing",
        "steps": [{"step_id": "s1", "label": "扫描", "status": "completed"}],
        "error": {"message": "连接超时", "tone": "danger"},
        "callouts": [{"text": "网络不稳定", "tone": "warning"}],
        "extra_actions": [{"id": "cancel", "kind": "submit_message", "label": "取消"}],
        "metadata": [{"label": "Started", "value": "2026-05-13"}],
    })
    d = result.model_dump()
    assert d["error"]["message"] == "连接超时"
    assert len(d["extra_actions"]) == 1


def test_clarification_with_extension_fields() -> None:
    result = validate_business_data("clarification_request", "1", {
        "question": "选择恢复类型",
        "options": [
            {
                "option_id": "1",
                "label": "全量恢复",
                "is_recommended": True,
                "badges": [{"text": "快速", "tone": "positive"}],
                "metadata": [{"label": "Duration", "value": "~30min"}],
                "callouts": [{"text": "将覆盖现有数据", "tone": "warning"}],
                "card_tone": "highlight",
            },
        ],
        "allows_free_text": True,
        "free_text_placeholder": "输入自定义答案",
    })
    d = result.model_dump()
    assert d["options"][0]["is_recommended"] is True
    assert d["allows_free_text"] is True


def test_capacity_forecast_with_forecast_data() -> None:
    result = validate_business_data("capacity_forecast", "1", {
        "metrics": [{"label": "Storage", "current": "2.1TB", "capacity": "5TB"}],
        "forecast": {
            "items": [{"label": "Current", "value": 42}],
            "columns": [{"key": "month", "label": "Month"}],
            "rows": [{"month": "Jan", "usage": "42%"}],
            "title": "30-Day Forecast",
        },
        "header_badges": [{"text": "Warning", "tone": "warning"}],
        "callouts": [{"text": "建议扩容", "tone": "warning"}],
        "block_id_suffix": "pool-1",
    })
    d = result.model_dump()
    assert d["forecast"]["title"] == "30-Day Forecast"
    assert d["block_id_suffix"] == "pool-1"


def test_attachment_list_with_extension_fields() -> None:
    result = validate_business_data("attachment_list", "1", {
        "heading": "附件列表",
        "attachments": [
            {
                "attachment_id": "a1",
                "filename": "report.pdf",
                "size": 1024,
                "download_url": "/dl/a1",
                "title": "恢复报告",
                "summary": "2026年5月",
                "badges": [{"text": "PDF", "tone": "info"}],
                "metadata": [{"label": "Created", "value": "2026-05-13"}],
            },
        ],
        "header_badges": [{"text": "2 files", "tone": "info"}],
    })
    d = result.model_dump()
    assert d["attachments"][0]["title"] == "恢复报告"
    assert d["attachments"][0]["badges"] is not None


def test_report_detail_with_extension_fields() -> None:
    result = validate_business_data("report_detail", "1", {
        "heading": "恢复报告",
        "sections": [
            {
                "section_id": "s1",
                "title": "执行步骤",
                "section_type": "steps",
                "content": {"step1": "扫描", "step2": "恢复"},
                "badges": [{"text": "5 steps", "tone": "info"}],
                "callouts": [{"text": "注意数据一致性", "tone": "warning"}],
            },
        ],
        "header_badges": [{"text": "Final", "tone": "positive"}],
        "metadata": [{"label": "Author", "value": "System"}],
        "navigation": [{"section_id": "s1", "title": "执行步骤"}],
        "use_tabs": True,
    })
    d = result.model_dump()
    assert d["sections"][0]["section_type"] == "steps"
    assert d["use_tabs"] is True
    assert len(d["navigation"]) == 1


def test_text_message_with_extension_fields() -> None:
    result = validate_business_data("text_message", "1", {
        "text": "**重要通知**",
        "format_hint": "markdown",
        "badges": [{"text": "System", "tone": "info"}],
    })
    d = result.model_dump()
    assert d["format_hint"] == "markdown"
    assert d["badges"] is not None


def test_incremental_update_with_extension_fields() -> None:
    result = validate_business_data("incremental_update", "1", {
        "target_block_id": "progress-1",
        "patch": [{"op": "replace", "path": "/stage", "value": "completed"}],
        "patch_type": "status_change",
        "version": 3,
    })
    d = result.model_dump()
    assert d["patch_type"] == "status_change"
    assert d["version"] == 3
