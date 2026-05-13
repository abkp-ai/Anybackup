from typing import Any


def stack(children: list[dict[str, Any]], *, gap: str = "md", node_id: str | None = None) -> dict[str, Any]:
    node: dict[str, Any] = {"type": "stack", "props": {"children": children, "gap": gap}}
    if node_id is not None:
        node["id"] = node_id
    return node


def section(children: list[dict[str, Any]], *, node_id: str | None = None) -> dict[str, Any]:
    node: dict[str, Any] = {"type": "section", "props": {"children": children}}
    if node_id is not None:
        node["id"] = node_id
    return node


def heading(text: str, *, level: int = 2) -> dict[str, Any]:
    return {"type": "heading", "props": {"text": text, "level": level}}


def paragraph(text: str) -> dict[str, Any]:
    return {"type": "paragraph", "props": {"text": text}}


def card(children: list[dict[str, Any]], *, node_id: str | None = None) -> dict[str, Any]:
    node: dict[str, Any] = {"type": "card", "props": {"children": children}}
    if node_id is not None:
        node["id"] = node_id
    return node


def kv_list(items: list[dict[str, str]]) -> dict[str, Any]:
    rows = [{"label": it["label"], "value": it["value"]} for it in items]
    return {"type": "kv-list", "props": {"rows": rows}}


def metric_list(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    items = [{"label": m["label"], "value": str(m["value"]), "unit": m.get("unit", "")} for m in metrics]
    return {"type": "metric-list", "props": {"items": items}}


def data_table(headers: list[str], rows: list[list[str | int | float]]) -> dict[str, Any]:
    return {
        "type": "data-table",
        "props": {
            "headers": [{"label": h} for h in headers],
            "rows": [{"cells": [str(c) for c in row]} for row in rows],
        },
    }


def chart(data: dict[str, Any]) -> dict[str, Any]:
    return {"type": "chart", "props": data}


def callout(text: str, *, tone: str = "warning") -> dict[str, Any]:
    return {"type": "callout", "props": {"text": text, "tone": tone}}


def action_row(action_ids: list[str]) -> dict[str, Any]:
    return {"type": "action-row", "props": {"actionIds": action_ids}}


def badge_row(items: list[dict[str, str]]) -> dict[str, Any]:
    return {"type": "badge-row", "props": {"items": items}}


def grid(children: list[dict[str, Any]], *, columns: int = 2) -> dict[str, Any]:
    return {"type": "grid", "props": {"children": children, "columns": columns}}


def markdown(text: str) -> dict[str, Any]:
    return {"type": "markdown", "props": {"text": text}}


def attachment_list(attachments: list[dict[str, Any]]) -> dict[str, Any]:
    items = [
        {
            "attachmentId": a["attachment_id"],
            "filename": a["filename"],
            "size": str(a["size"]),
            "downloadUrl": a["download_url"],
        }
        for a in attachments
    ]
    return {"type": "attachment-list", "props": {"items": items}}
