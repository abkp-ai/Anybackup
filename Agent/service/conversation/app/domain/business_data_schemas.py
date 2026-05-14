from typing import Any, Literal

from pydantic import BaseModel, Field

ALLOWED_SCHEMA_TYPES = frozenset(
    {
        "plan_candidates",
        "progress_report",
        "clarification_request",
        "capacity_forecast",
        "attachment_list",
        "report_detail",
        "text_message",
        "incremental_update",
    }
)


# --- plan_candidates ---


class PlanCandidateItem(BaseModel):
    candidate_option_id: str
    title: str
    summary: str
    recommendation_level: str = "alternative"
    risk_level: str = "medium"
    # 通用扩展
    badges: list[dict[str, str]] | None = None
    metadata: list[dict[str, str]] | None = None
    callouts: list[dict[str, Any]] | None = None
    card_tone: str | None = None
    # 向后兼容（deprecated → 使用 metadata / callouts）
    rpo: str | None = None
    rto: str | None = None
    target: str | None = None
    impact_summary: str | None = None
    execution_steps: list[str] | None = None
    validation_checks: list[str] | None = None


class PlanCandidatesData(BaseModel):
    heading: str
    subtitle: str | None = None
    candidates: list[PlanCandidateItem] = Field(min_length=1)
    selection: dict[str, Any] | None = None
    # 通用扩展
    header_badges: list[dict[str, str]] | None = None
    header_metadata: list[dict[str, str]] | None = None
    meta: dict[str, Any] | None = None


# --- progress_report ---


class ProgressStep(BaseModel):
    step_id: str
    label: str
    status: str = "pending"
    # 通用扩展
    badges: list[dict[str, str]] | None = None
    metadata: list[dict[str, str]] | None = None


class ProgressMetric(BaseModel):
    label: str
    value: str | int | float
    unit: str | None = None


class ProgressReportData(BaseModel):
    heading: str
    subtitle: str | None = None
    stage: str
    steps: list[ProgressStep] = Field(min_length=1)
    progress_percent: int | float | None = None
    eta: str | None = None
    metrics: list[ProgressMetric] | None = None
    # 通用扩展
    error: dict[str, Any] | None = None
    callouts: list[dict[str, Any]] | None = None
    extra_actions: list[dict[str, Any]] | None = None
    metadata: list[dict[str, str]] | None = None
    meta: dict[str, Any] | None = None


# --- clarification_request ---


class ClarificationOption(BaseModel):
    option_id: str
    label: str
    description: str | None = None
    # 通用扩展
    is_recommended: bool | None = None
    badges: list[dict[str, str]] | None = None
    metadata: list[dict[str, str]] | None = None
    callouts: list[dict[str, Any]] | None = None
    card_tone: str | None = None


class ClarificationRequestData(BaseModel):
    question: str
    options: list[ClarificationOption] = Field(min_length=1)
    context: str | None = None
    selection: dict[str, Any] | None = None
    # 通用扩展
    allows_free_text: bool | None = None
    free_text_placeholder: str | None = None
    meta: dict[str, Any] | None = None


# --- capacity_forecast ---


class CapacityMetric(BaseModel):
    label: str
    current: str | int | float
    capacity: str | int | float
    unit: str | None = None


class CapacityWarning(BaseModel):
    level: str = "warning"
    message: str


class ForecastData(BaseModel):
    items: list[dict[str, Any]] | None = None
    columns: list[dict[str, str]] | None = None
    rows: list[dict[str, Any]] | None = None
    chart_type: str | None = None
    title: str | None = None


class CapacityForecastData(BaseModel):
    metrics: list[CapacityMetric] = Field(min_length=1)
    forecast: ForecastData | dict[str, Any] | None = None
    warnings: list[CapacityWarning] | None = None
    # 通用扩展
    header_badges: list[dict[str, str]] | None = None
    metadata: list[dict[str, str]] | None = None
    callouts: list[dict[str, Any]] | None = None
    extra_actions: list[dict[str, Any]] | None = None
    block_id_suffix: str | None = None
    meta: dict[str, Any] | None = None


# --- attachment_list ---


class AttachmentItem(BaseModel):
    attachment_id: str
    filename: str
    size: int | str
    download_url: str
    # 通用扩展
    title: str | None = None
    summary: str | None = None
    badges: list[dict[str, str]] | None = None
    metadata: list[dict[str, str]] | None = None
    card_tone: str | None = None


class AttachmentListData(BaseModel):
    heading: str
    subtitle: str | None = None
    attachments: list[AttachmentItem] = Field(min_length=1)
    # 通用扩展
    header_badges: list[dict[str, str]] | None = None
    meta: dict[str, Any] | None = None


# --- report_detail ---


class ReportSection(BaseModel):
    section_id: str
    title: str
    content: str | dict[str, Any] | None = None
    # 通用扩展
    section_type: str | None = None
    layout_nodes: list[dict[str, Any]] | None = None
    badges: list[dict[str, str]] | None = None
    callouts: list[dict[str, Any]] | None = None


class ReportDetailData(BaseModel):
    heading: str
    subtitle: str | None = None
    summary: str | None = None
    sections: list[ReportSection] | None = None
    # 通用扩展
    header_badges: list[dict[str, str]] | None = None
    metadata: list[dict[str, str]] | None = None
    navigation: list[dict[str, str]] | None = None
    use_tabs: bool | None = None
    meta: dict[str, Any] | None = None


# --- text_message ---


class TextMessageData(BaseModel):
    text: str
    format_hint: str | None = None
    # 通用扩展
    badges: list[dict[str, str]] | None = None
    meta: dict[str, Any] | None = None


# --- incremental_update ---


class IncrementalUpdateData(BaseModel):
    target_block_id: str
    patch: list[dict[str, Any]] = Field(min_length=1)
    operation: Literal["replace", "merge", "patch"] | None = None
    # 通用扩展
    patch_type: str | None = None
    version: int | None = None


# --- Registry ---


SCHEMA_TYPE_MODELS: dict[str, type[BaseModel]] = {
    "plan_candidates": PlanCandidatesData,
    "progress_report": ProgressReportData,
    "clarification_request": ClarificationRequestData,
    "capacity_forecast": CapacityForecastData,
    "attachment_list": AttachmentListData,
    "report_detail": ReportDetailData,
    "text_message": TextMessageData,
    "incremental_update": IncrementalUpdateData,
}


def validate_business_data(schema_type: str, schema_version: str, data: dict[str, Any]) -> BaseModel:
    if schema_type not in ALLOWED_SCHEMA_TYPES:
        raise ValueError(f"unknown schema_type: {schema_type}")
    if schema_version != "1":
        raise ValueError(f"unsupported schema_version: {schema_version}")
    model_cls = SCHEMA_TYPE_MODELS[schema_type]
    return model_cls.model_validate(data)
