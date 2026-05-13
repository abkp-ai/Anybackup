from typing import Any

from app.application.ag_ui_templates.layout_nodes import (
    card,
    grid,
    heading,
    paragraph,
    section,
    stack,
)
from app.application.ag_ui_templates.base import AgUiTemplate, AgUiTemplateResult


class ClarificationRequestTemplate(AgUiTemplate):
    def fill(self, data: dict[str, Any]) -> AgUiTemplateResult:
        question = data["question"]
        options = data["options"]
        context = data.get("context")

        header_children: list[dict[str, Any]] = [heading("Clarification Needed", level=2)]
        header_children.append(paragraph(question))
        if context:
            header_children.append(paragraph(context))

        option_cards = [_build_option_card(opt) for opt in options]
        columns = min(len(options), 3) if len(options) > 1 else 1

        ui_children: list[dict[str, Any]] = [section(header_children)]
        ui_children.append(grid(option_cards, columns=columns))

        ui = stack(ui_children, gap="lg")
        meta: dict[str, Any] = {"intent": "clarification", "terminal": False}
        actions = _build_option_actions(options)
        state = None
        if "selection" in data:
            state = {"selection": data["selection"]}

        return AgUiTemplateResult(
            activity_content={
                "contract": "conversation.ui.layout-tree@1",
                "blockId": f"clarification-{question[:20]}",
                "ui": ui,
                "meta": meta,
                "actions": actions,
            },
            state=state,
            meta=meta,
            actions=actions,
        )


def _build_option_card(option: dict[str, Any]) -> dict[str, Any]:
    children: list[dict[str, Any]] = [heading(option["label"], level=3)]
    description = option.get("description")
    if description:
        children.append(paragraph(description))
    return card(children, node_id=f"option-{option['option_id']}")


def _build_option_actions(options: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for option in options:
        option_id = option["option_id"]
        actions.append({
            "kind": "selection",
            "id": f"select-{option_id}",
            "label": option["label"],
            "payload": {"selected_option_id": option_id},
        })
    return actions
