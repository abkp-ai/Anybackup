# Schema 类型目录

## plan_candidates — 候选方案对比+选择

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `heading` | `str` | 是 | 标题 |
| `subtitle` | `str` | 否 | 副标题 |
| `candidates` | `list[PlanCandidateItem]` | 是(min 1) | 候选方案列表 |
| `selection` | `dict` | 否 | 选择状态 |
| `header_badges` | `list[{text, tone}]` | 否 | 标题区徽章 |
| `header_metadata` | `list[{label, value}]` | 否 | 标题区键值对 |
| `meta` | `dict` | 否 | 透传元数据 |

**PlanCandidateItem：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `candidate_option_id` | `str` | 是 | 方案唯一标识 |
| `title` | `str` | 是 | 方案标题 |
| `summary` | `str` | 是 | 方案摘要 |
| `recommendation_level` | `str` | 否(默认"alternative") | 推荐级别：recommended/alternative |
| `risk_level` | `str` | 否(默认"medium") | 风险级别：low/medium/high（high 自动生成警告提示） |
| `badges` | `list[{text, tone}]` | 否 | 方案徽章 |
| `metadata` | `list[{label, value}]` | 否 | 方案键值对（RPO/RTO/成本等） |
| `callouts` | `list[{text, tone?, title?}]` | 否 | 方案提示框 |
| `card_tone` | `str` | 否 | 卡片色调：highlight/positive/warning/danger |

## progress_report — 执行进度报告

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `heading` | `str` | 是 | 标题 |
| `subtitle` | `str` | 否 | 副标题 |
| `stage` | `str` | 是 | 当前阶段 |
| `steps` | `list[ProgressStep]` | 是(min 1) | 步骤列表 |
| `progress_percent` | `int\|float` | 否 | 进度百分比 |
| `eta` | `str` | 否 | 预计剩余时间 |
| `metrics` | `list[ProgressMetric]` | 否 | 指标列表 |
| `error` | `{message, tone?, title?}` | 否 | 错误提示框 |
| `callouts` | `list[{text, tone?, title?}]` | 否 | 提示框列表 |
| `extra_actions` | `list[{id, kind, label, payload}]` | 否 | 额外操作按钮 |
| `metadata` | `list[{label, value}]` | 否 | 键值对 |
| `meta` | `dict` | 否 | 透传元数据 |

**ProgressStep：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `step_id` | `str` | 是 | 步骤标识 |
| `label` | `str` | 是 | 步骤名称 |
| `status` | `str` | 否(默认"pending") | completed/in_progress/failed/pending/skipped |
| `badges` | `list[{text, tone}]` | 否 | 步骤徽章 |
| `metadata` | `list[{label, value}]` | 否 | 步骤键值对 |

**ProgressMetric：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `label` | `str` | 是 | 指标名称 |
| `value` | `str\|int\|float` | 是 | 指标值 |
| `unit` | `str` | 否 | 单位 |

## clarification_request — 用户澄清提示

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `question` | `str` | 是 | 问题文本 |
| `options` | `list[ClarificationOption]` | 是(min 1) | 选项列表 |
| `context` | `str` | 否 | 上下文说明 |
| `selection` | `dict` | 否 | 选择状态 |
| `allows_free_text` | `bool` | 否 | 允许自由文本输入 |
| `free_text_placeholder` | `str` | 否 | 自由文本占位符 |
| `meta` | `dict` | 否 | 透传元数据 |

**ClarificationOption：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `option_id` | `str` | 是 | 选项标识 |
| `label` | `str` | 是 | 选项文案 |
| `description` | `str` | 否 | 选项说明 |
| `is_recommended` | `bool` | 否 | 推荐标记（自动添加推荐徽章+高亮色调） |
| `badges` | `list[{text, tone}]` | 否 | 选项徽章 |
| `metadata` | `list[{label, value}]` | 否 | 选项键值对 |
| `callouts` | `list[{text, tone?, title?}]` | 否 | 选项提示框 |
| `card_tone` | `str` | 否 | 卡片色调 |

## capacity_forecast — 容量趋势预测

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `metrics` | `list[CapacityMetric]` | 是(min 1) | 容量指标 |
| `forecast` | `ForecastData\|dict` | 否 | 预测数据（支持图表和表格） |
| `warnings` | `list[CapacityWarning]` | 否 | 告警列表 |
| `header_badges` | `list[{text, tone}]` | 否 | 标题区徽章 |
| `metadata` | `list[{label, value}]` | 否 | 键值对 |
| `callouts` | `list[{text, tone?, title?}]` | 否 | 提示框 |
| `extra_actions` | `list[{id, kind, label, payload}]` | 否 | 额外操作 |
| `block_id_suffix` | `str` | 否 | blockId 后缀避免碰撞 |
| `meta` | `dict` | 否 | 透传元数据 |

**CapacityMetric：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `label` | `str` | 是 | 指标名称 |
| `current` | `str\|int\|float` | 是 | 当前值 |
| `capacity` | `str\|int\|float` | 是 | 容量上限 |
| `unit` | `str` | 否 | 单位 |

**CapacityWarning：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `level` | `str` | 否(默认"warning") | 告警级别 |
| `message` | `str` | 是 | 告警消息 |

**ForecastData：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `items` | `list[dict]` | 否 | 图表数据项 |
| `columns` | `list[{key, label}]` | 否 | 表格列定义 |
| `rows` | `list[dict]` | 否 | 表格行数据 |
| `chart_type` | `str` | 否 | 图表类型 |
| `title` | `str` | 否 | 预测标题 |

## attachment_list — 可下载附件

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `heading` | `str` | 是 | 标题 |
| `subtitle` | `str` | 否 | 副标题 |
| `attachments` | `list[AttachmentItem]` | 是(min 1) | 附件列表 |
| `header_badges` | `list[{text, tone}]` | 否 | 标题区徽章 |
| `meta` | `dict` | 否 | 透传元数据 |

**AttachmentItem：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `attachment_id` | `str` | 是 | 附件标识 |
| `filename` | `str` | 是 | 文件名 |
| `size` | `int\|str` | 是 | 文件大小 |
| `download_url` | `str` | 是 | 下载地址（受控引用，不得内联二进制） |
| `title` | `str` | 否 | 显示标题 |
| `summary` | `str` | 否 | 摘要 |
| `badges` | `list[{text, tone}]` | 否 | 徽章 |
| `metadata` | `list[{label, value}]` | 否 | 键值对 |
| `card_tone` | `str` | 否 | 卡片色调 |

## report_detail — 结构化报告

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `heading` | `str` | 是 | 标题 |
| `subtitle` | `str` | 否 | 副标题 |
| `summary` | `str` | 否 | 摘要 |
| `sections` | `list[ReportSection]` | 否 | 段落列表 |
| `header_badges` | `list[{text, tone}]` | 否 | 标题区徽章 |
| `metadata` | `list[{label, value}]` | 否 | 键值对 |
| `navigation` | `list[{section_id, title}]` | 否 | 导航链接 |
| `use_tabs` | `bool` | 否 | 多段落用 tabs 组织（>3 段自动启用） |
| `meta` | `dict` | 否 | 透传元数据 |

**ReportSection：**

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `section_id` | `str` | 是 | 段落标识 |
| `title` | `str` | 是 | 段落标题 |
| `content` | `str\|dict` | 否 | 段落内容 |
| `section_type` | `str` | 否 | 内容类型提示：steps/data/metrics/risk/text |
| `badges` | `list[{text, tone}]` | 否 | 段落徽章 |
| `callouts` | `list[{text, tone?, title?}]` | 否 | 段落提示框 |

## text_message — 纯文本消息

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `text` | `str` | 是 | 文本内容 |
| `format_hint` | `str` | 否 | 格式提示："markdown" 生成布局树卡片，其他走纯文本流 |
| `badges` | `list[{text, tone}]` | 否 | 徽章（仅 format_hint="markdown" 时渲染） |
| `meta` | `dict` | 否 | 透传元数据 |

## incremental_update — 增量更新

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `target_block_id` | `str` | 是 | 目标块标识 |
| `patch` | `list[dict]` | 是(min 1) | 补丁操作列表（必须是合法 JSON Patch） |
| `operation` | `str` | 否 | 操作类型：replace/merge/patch |
| `patch_type` | `str` | 否 | 语义补丁类型 |
| `version` | `int` | 否 | 目标块版本号 |

---

## 必填字段速查

以下清单仅列出必填字段。生成 business_data.data 时逐项核对，确保不遗漏。所有字段必须填入有意义的业务值，不得留空。

**plan_candidates**
- [ ] `heading` — 标题，必须表达业务结论
- [ ] `candidates[]` — 至少 1 项，每项必须含：
  - [ ] `candidate_option_id` — 方案唯一标识
  - [ ] `title` — 方案标题
  - [ ] `summary` — 方案摘要
  - [ ] `recommendation_level` — recommended / alternative
  - [ ] `risk_level` — low / medium / high

**progress_report**
- [ ] `heading` — 标题
- [ ] `stage` — 当前阶段（processing / executing / validating / completing / failed）
- [ ] `steps[]` — 至少 1 项，每项必须含：
  - [ ] `step_id` — 步骤标识
  - [ ] `label` — 步骤名称

**clarification_request**
- [ ] `question` — 问题文本，必须具体
- [ ] `options[]` — 至少 1 项，每项必须含：
  - [ ] `option_id` — 选项标识
  - [ ] `label` — 选项文案

**capacity_forecast**
- [ ] `metrics[]` — 至少 1 项，每项必须含：
  - [ ] `label` — 指标名称
  - [ ] `current` — 当前值
  - [ ] `capacity` — 容量上限

**attachment_list**
- [ ] `heading` — 标题
- [ ] `attachments[]` — 至少 1 项，每项必须含：
  - [ ] `attachment_id` — 附件标识
  - [ ] `filename` — 文件名
  - [ ] `size` — 文件大小
  - [ ] `download_url` — 下载地址（受控引用，不内联二进制）

**report_detail**
- [ ] `heading` — 标题
- [ ] `sections[]`（如有分段，每项必须含）：
  - [ ] `section_id` — 段落标识
  - [ ] `title` — 段落标题

**text_message**
- [ ] `text` — 文本内容，必须包含完整信息

**incremental_update**
- [ ] `target_block_id` — 目标块标识，必须指向已有展示块
- [ ] `patch[]` — 至少 1 项，每项必须是合法的 JSON Patch 操作

**外层 envelope（所有 schema_type 通用）**
- [ ] `payload.content` — 纯文本降级摘要，非空，与 data 核心信息一致
- [ ] `payload.conversation_id` / `turn_id` / `message_id` / `sequence`
