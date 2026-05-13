from __future__ import annotations

from typing import TYPE_CHECKING

from app.application.ag_ui_templates.base import AgUiTemplate, AgUiTemplateResult

if TYPE_CHECKING:
    pass


class AgUiTemplateRegistry:
    def __init__(self) -> None:
        self._templates: dict[tuple[str, str], AgUiTemplate] = {}
        self._register_defaults()

    def get_template(self, schema_type: str, schema_version: str) -> AgUiTemplate:
        key = (schema_type, schema_version)
        template = self._templates.get(key)
        if template is None:
            raise KeyError(f"no template registered for schema_type={schema_type}, schema_version={schema_version}")
        return template

    def register(self, schema_type: str, schema_version: str, template: AgUiTemplate) -> None:
        self._templates[(schema_type, schema_version)] = template

    def _register_defaults(self) -> None:
        from app.application.ag_ui_templates.plan_candidates import PlanCandidatesTemplate
        from app.application.ag_ui_templates.progress_report import ProgressReportTemplate
        from app.application.ag_ui_templates.clarification_request import ClarificationRequestTemplate
        from app.application.ag_ui_templates.capacity_forecast import CapacityForecastTemplate
        from app.application.ag_ui_templates.attachment_list import AttachmentListTemplate
        from app.application.ag_ui_templates.report_detail import ReportDetailTemplate
        from app.application.ag_ui_templates.text_message import TextMessageTemplate
        from app.application.ag_ui_templates.incremental_update import IncrementalUpdateTemplate

        defaults: dict[str, type[AgUiTemplate]] = {
            "plan_candidates": PlanCandidatesTemplate,
            "progress_report": ProgressReportTemplate,
            "clarification_request": ClarificationRequestTemplate,
            "capacity_forecast": CapacityForecastTemplate,
            "attachment_list": AttachmentListTemplate,
            "report_detail": ReportDetailTemplate,
            "text_message": TextMessageTemplate,
            "incremental_update": IncrementalUpdateTemplate,
        }
        for schema_type, template_cls in defaults.items():
            self.register(schema_type, "1", template_cls())
