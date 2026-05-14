from typing import Any

from app.application.ag_ui_templates.base import AgUiTemplate, AgUiTemplateResult


class IncrementalUpdateTemplate(AgUiTemplate):
    def fill(self, data: dict[str, Any]) -> AgUiTemplateResult:
        patch_type = data.get("patch_type")
        version = data.get("version")

        meta: dict[str, Any] = {"intent": "update"}
        if patch_type is not None:
            meta["patch_type"] = patch_type

        activity_content: dict[str, Any] = {
            "contract": "conversation.ui.layout-tree@1",
            "blockId": data["target_block_id"],
            "patch": data["patch"],
        }
        if version is not None:
            activity_content["version"] = version

        return AgUiTemplateResult(
            activity_content=activity_content,
            meta=meta,
        )
