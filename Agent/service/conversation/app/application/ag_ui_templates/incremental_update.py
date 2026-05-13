from typing import Any

from app.application.ag_ui_templates.base import AgUiTemplate, AgUiTemplateResult


class IncrementalUpdateTemplate(AgUiTemplate):
    def fill(self, data: dict[str, Any]) -> AgUiTemplateResult:
        return AgUiTemplateResult(
            activity_content={
                "contract": "conversation.ui.layout-tree@1",
                "blockId": data["target_block_id"],
                "patch": data["patch"],
            },
            meta={"intent": "update"},
        )
