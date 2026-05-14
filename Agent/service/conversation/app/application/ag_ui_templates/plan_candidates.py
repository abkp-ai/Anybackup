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

_RECOMMENDATION_BADGE = {"recommended": "success", "alternative": "info", "not_recommended": "warning"}
_RISK_BADGE = {"low": "success", "medium": "warning", "high": "danger"}


class PlanCandidatesTemplate(AgUiTemplate):
    def fill(self, data: dict[str, Any]) -> AgUiTemplateResult:
        candidates = data["candidates"]
        heading_text = data["heading"]
        subtitle = data.get("subtitle")

        header_children: list[dict[str, Any]] = [heading(heading_text, level=2)]
        if subtitle:
            header_children.append(paragraph(subtitle))

        header_badges = data.get("header_badges")
        if header_badges:
            header_children.append(badge_row(header_badges))

        header_metadata = data.get("header_metadata")
        if header_metadata:
            header_children.append(kv_list(header_metadata))

        cards = [_build_candidate_card(c) for c in candidates]
        columns = min(len(candidates), 3) if len(candidates) > 1 else 1

        ui_children: list[dict[str, Any]] = [section(header_children)]
        ui_children.append(grid(cards, columns=columns))

        ui = stack(ui_children, gap="lg")

        meta: dict[str, Any] = {"intent": "result", "terminal": True}
        actions = _build_candidate_actions(candidates)
        state = None
        if "selection" in data:
            state = {"selection": data["selection"]}

        return AgUiTemplateResult(
            activity_content={
                "contract": "conversation.ui.layout-tree@1",
                "blockId": f"plan-candidates-{heading_text}",
                "ui": ui,
                "meta": meta,
                "actions": actions,
            },
            state=state,
            meta=meta,
            actions=actions,
        )


def _build_candidate_card(candidate: dict[str, Any]) -> dict[str, Any]:
    children: list[dict[str, Any]] = []

    children.append(heading(candidate["title"], level=3))

    badges: list[dict[str, str]] = []
    rec_level = candidate.get("recommendation_level", "alternative")
    badges.append({"text": rec_level, "tone": _RECOMMENDATION_BADGE.get(rec_level, "info")})
    risk_level = candidate.get("risk_level", "medium")
    badges.append({"text": f"risk: {risk_level}", "tone": _RISK_BADGE.get(risk_level, "warning")})

    for b in candidate.get("badges") or []:
        badges.append(b)
    children.append(badge_row(badges))

    children.append(paragraph(candidate["summary"]))

    kv_items: list[dict[str, str]] = []
    # 向后兼容：旧字段自动追加到 metadata
    for key, label in [("rpo", "RPO"), ("rto", "RTO"), ("target", "Target")]:
        value = candidate.get(key)
        if value is not None:
            kv_items.append({"label": label, "value": str(value)})
    for item in candidate.get("metadata") or []:
        kv_items.append({"label": item["label"], "value": item["value"]})
    if kv_items:
        children.append(kv_list(kv_items))

    if risk_level == "high":
        children.append(callout(f"High risk: {candidate['summary']}", tone="warning"))

    # 向后兼容：impact_summary 自动追加到 callouts
    impact = candidate.get("impact_summary")
    callout_items: list[dict[str, Any]] = list(candidate.get("callouts") or [])
    if impact and not any(c.get("text") == impact for c in callout_items):
        callout_items.insert(0, {"text": impact, "tone": "info", "title": "Impact"})
    for c in callout_items:
        children.append(callout(c["text"], tone=c.get("tone", "warning"), title=c.get("title")))

    card_tone = candidate.get("card_tone")
    return card(children, node_id=f"candidate-{candidate['candidate_option_id']}", tone=card_tone)


def _build_candidate_actions(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    for candidate in candidates:
        option_id = candidate["candidate_option_id"]
        actions.append({
            "kind": "selection",
            "id": f"select-{option_id}",
            "label": f"Select {candidate['title']}",
            "payload": {"selected_option_id": option_id},
        })
    return actions
