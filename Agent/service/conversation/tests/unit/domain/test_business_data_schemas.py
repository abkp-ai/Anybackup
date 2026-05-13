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
