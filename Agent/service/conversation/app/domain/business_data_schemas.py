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
    meta: dict[str, Any] | None = None


# --- progress_report ---


class ProgressStep(BaseModel):
    step_id: str
    label: str
    status: str = "pending"


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
    meta: dict[str, Any] | None = None


# --- clarification_request ---


class ClarificationOption(BaseModel):
    option_id: str
    label: str
    description: str | None = None


class ClarificationRequestData(BaseModel):
    question: str
    options: list[ClarificationOption] = Field(min_length=1)
    context: str | None = None
    selection: dict[str, Any] | None = None
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


class CapacityForecastData(BaseModel):
    metrics: list[CapacityMetric] = Field(min_length=1)
    forecast: dict[str, Any] | None = None
    warnings: list[CapacityWarning] | None = None
    meta: dict[str, Any] | None = None


# --- attachment_list ---


class AttachmentItem(BaseModel):
    attachment_id: str
    filename: str
    size: int | str
    download_url: str


class AttachmentListData(BaseModel):
    heading: str
    subtitle: str | None = None
    attachments: list[AttachmentItem] = Field(min_length=1)


# --- report_detail ---


class ReportSection(BaseModel):
    section_id: str
    title: str
    content: str | dict[str, Any] | None = None


class ReportDetailData(BaseModel):
    heading: str
    subtitle: str | None = None
    summary: str | None = None
    sections: list[ReportSection] | None = None
    meta: dict[str, Any] | None = None


# --- text_message ---


class TextMessageData(BaseModel):
    text: str
    format_hint: str | None = None


# --- incremental_update ---


class IncrementalUpdateData(BaseModel):
    target_block_id: str
    patch: list[dict[str, Any]] = Field(min_length=1)
    operation: Literal["replace", "merge", "patch"] | None = None


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
