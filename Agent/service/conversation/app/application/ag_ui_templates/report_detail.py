from typing import Any

from app.application.ag_ui_templates.layout_nodes import (
    badge_row,
    callout,
    data_table,
    divider,
    heading,
    kv_list,
    markdown,
    metric_list,
    paragraph,
    section,
    stack,
    tabs,
)
from app.application.ag_ui_templates.base import AgUiTemplate, AgUiTemplateResult


class ReportDetailTemplate(AgUiTemplate):
    def fill(self, data: dict[str, Any]) -> AgUiTemplateResult:
        heading_text = data["heading"]
        subtitle = data.get("subtitle")
        summary = data.get("summary")
        sections = data.get("sections")
        use_tabs = data.get("use_tabs")
        navigation = data.get("navigation")

        ui_children: list[dict[str, Any]] = [section([heading(heading_text, level=2)])]

        # 标题区通用扩展
        header_badges = data.get("header_badges")
        if header_badges:
            ui_children.append(section([badge_row(header_badges)]))

        # 报告级 metadata
        report_metadata = data.get("metadata")
        if report_metadata:
            ui_children.append(section([kv_list(report_metadata)]))

        if subtitle:
            ui_children.append(section([paragraph(subtitle)]))
        if summary:
            ui_children.append(section([paragraph(summary)]))

        # 导航链接
        if navigation:
            nav_badges = [{"text": n["title"], "tone": "info"} for n in navigation if "title" in n]
            if nav_badges:
                ui_children.append(section([badge_row(nav_badges)]))

        ui_children.append(divider())

        if sections:
            if use_tabs and len(sections) > 3:
                tab_items = [{"id": s["section_id"], "label": s["title"]} for s in sections]
                tab_children = [_build_section(s) for s in sections]
                ui_children.append(tabs(tab_children, items=tab_items))
            else:
                for sec in sections:
                    ui_children.append(_build_section(sec))

        ui = stack(ui_children, gap="md")
        meta: dict[str, Any] = {"intent": "result", "terminal": True}

        return AgUiTemplateResult(
            activity_content={
                "contract": "conversation.ui.layout-tree@1",
                "blockId": f"report-{heading_text}",
                "ui": ui,
                "meta": meta,
            },
            meta=meta,
        )


def _build_section(sec: dict[str, Any]) -> dict[str, Any]:
    sec_children: list[dict[str, Any]] = [heading(sec["title"], level=3)]

    # 通用扩展：layout_nodes 优先于 content
    layout_nodes_data = sec.get("layout_nodes")
    if layout_nodes_data:
        sec_children.extend(layout_nodes_data)
        return section(sec_children, node_id=f"section-{sec.get('section_id', '')}")

    # 通用扩展：badges
    badges = sec.get("badges")
    if badges:
        sec_children.append(badge_row(badges))

    content = sec.get("content")
    if content is None:
        pass
    elif isinstance(content, str):
        sec_children.append(paragraph(content))
    elif isinstance(content, dict):
        # 修复 Bug：dict 内容按 section_type 分发渲染
        section_type = sec.get("section_type")
        if section_type == "steps":
            items = [f"{i+1}. {v}" for i, v in enumerate(content.values())]
            sec_children.append(markdown("\n".join(items)))
        elif section_type == "data":
            columns = [{"key": str(k), "label": str(k)} for k in content]
            sec_children.append(data_table(columns, [content]))
        elif section_type == "metrics":
            items = [{"label": str(k), "value": str(v)} for k, v in content.items()]
            sec_children.append(metric_list(items))
        elif section_type == "risk":
            sec_children.append(callout(
                "\n".join(f"- **{k}**: {v}" for k, v in content.items()),
                tone="warning",
                title="Risk Assessment",
            ))
        else:
            kv_items = [{"label": str(k), "value": str(v)} for k, v in content.items()]
            sec_children.append(kv_list(kv_items))

    # 通用扩展：callouts
    for c in sec.get("callouts") or []:
        sec_children.append(callout(c["text"], tone=c.get("tone", "warning"), title=c.get("title")))

    return section(sec_children, node_id=f"section-{sec.get('section_id', '')}")
