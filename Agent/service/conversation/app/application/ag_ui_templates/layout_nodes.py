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


def card(
    children: list[dict[str, Any]],
    *,
    node_id: str | None = None,
    title: str | None = None,
    tone: str | None = None,
) -> dict[str, Any]:
    props: dict[str, Any] = {"children": children}
    if title is not None:
        props["title"] = title
    if tone is not None:
        props["tone"] = tone
    node: dict[str, Any] = {"type": "card", "props": props}
    if node_id is not None:
        node["id"] = node_id
    return node


def kv_list(items: list[dict[str, str]]) -> dict[str, Any]:
    rows = [{"label": it["label"], "value": it["value"]} for it in items]
    return {"type": "kv-list", "props": {"rows": rows}}


def metric_list(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    items = [{"label": m["label"], "value": str(m["value"]), "unit": m.get("unit", "")} for m in metrics]
    return {"type": "metric-list", "props": {"items": items}}


def data_table(
    columns: list[dict[str, str]],
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    cols = [{"key": c["key"], "label": c["label"]} for c in columns]
    return {
        "type": "data-table",
        "props": {
            "columns": cols,
            "rows": rows,
        },
    }


def chart(
    items: list[dict[str, Any]],
    *,
    title: str | None = None,
    chart_type: str | None = None,
) -> dict[str, Any]:
    props: dict[str, Any] = {"items": items}
    if title is not None:
        props["title"] = title
    if chart_type is not None:
        props["chartType"] = chart_type
    return {"type": "chart", "props": props}


def callout(text: str, *, tone: str = "warning", title: str | None = None) -> dict[str, Any]:
    props: dict[str, Any] = {"text": text, "tone": tone}
    if title is not None:
        props["title"] = title
    return {"type": "callout", "props": props}


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
            "title": a.get("title", a["filename"]),
            "text": a["filename"],
            "summary": a.get("summary", f"{a['size']} bytes"),
        }
        for a in attachments
    ]
    return {"type": "attachment-list", "props": {"items": items}}


def tabs(
    children: list[dict[str, Any]],
    *,
    items: list[dict[str, str]] | None = None,
    default_tab_id: str | None = None,
    node_id: str | None = None,
) -> dict[str, Any]:
    props: dict[str, Any] = {"children": children}
    if items is not None:
        props["items"] = items
    if default_tab_id is not None:
        props["defaultTabId"] = default_tab_id
    node: dict[str, Any] = {"type": "tabs", "props": props}
    if node_id is not None:
        node["id"] = node_id
    return node


def divider() -> dict[str, Any]:
    return {"type": "divider"}
