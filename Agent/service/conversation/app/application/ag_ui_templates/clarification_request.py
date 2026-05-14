from typing import Any

from app.application.ag_ui_templates.layout_nodes import (
    badge_row,
    callout,
    card,
    grid,
    heading,
    kv_list,
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
        allows_free_text = data.get("allows_free_text")
        free_text_placeholder = data.get("free_text_placeholder")

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
        actions = _build_option_actions(options, allows_free_text, free_text_placeholder)
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

    is_recommended = option.get("is_recommended")
    if is_recommended:
        children.append(badge_row([{"text": "Recommended", "tone": "positive"}]))

    description = option.get("description")
    if description:
        children.append(paragraph(description))

    # 通用扩展：badges
    badges = option.get("badges")
    if badges:
        children.append(badge_row(badges))

    # 通用扩展：metadata
    metadata = option.get("metadata")
    if metadata:
        children.append(kv_list(metadata))

    # 通用扩展：callouts
    for c in option.get("callouts") or []:
        children.append(callout(c["text"], tone=c.get("tone", "info"), title=c.get("title")))

    card_tone = option.get("card_tone")
    if is_recommended and card_tone is None:
        card_tone = "highlight"
    return card(children, node_id=f"option-{option['option_id']}", tone=card_tone)


def _build_option_actions(
    options: list[dict[str, Any]],
    allows_free_text: bool | None = None,
    free_text_placeholder: str | None = None,
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for option in options:
        option_id = option["option_id"]
        actions.append({
            "kind": "selection",
            "id": f"select-{option_id}",
            "label": option["label"],
            "payload": {"selected_option_id": option_id},
        })
    if allows_free_text:
        actions.append({
            "kind": "submit_message",
            "id": "clarification-free-text",
            "label": free_text_placeholder or "Type your answer",
            "style": "secondary",
            "payload": {
                "clarification_response": True,
                "freeText": True,
            },
        })
    return actions
