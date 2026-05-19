# 会话富内容 Block Schema v1

本参考定义智能体和消息服务在 MVP 阶段可生成的 JSON block 子集。

MVP 不包含通用 `actions`。交互类内容只表达语义字段，不在 JSON 中定义具体执行动作。

## 通用 Payload

```ts
type ConversationRichPayload = {
  schema_version: "1.0"
  blocks: RichBlock[]
}

type BaseBlock = {
  block_id?: string
  type: string
  title?: string
  description?: string
  visibility?: "primary" | "secondary" | "collapsed"
}
```

## 支持的 Block

```ts
type RichBlock =
  | TextBlock
  | TableBlock
  | KeyValueBlock
  | StatusBlock
  | ClarificationBlock
  | CandidateOptionsBlock
  | TimelineBlock
  | MetricCardsBlock
  | ChartBlock
  | AttachmentBlock
  | LogExcerptBlock
  | ErrorBlock
```

## `text`

```ts
type TextBlock = BaseBlock & {
  type: "text"
  text: string
  tone?: "normal" | "muted" | "success" | "warning" | "danger"
}
```

示例：

```json
{
  "type": "text",
  "text": "我查到了最近 3 次订单数据库备份记录。"
}
```

## `table`

```ts
type TableBlock = BaseBlock & {
  type: "table"
  columns: TableColumn[]
  rows: Array<Record<string, TableCellValue>>
  row_key?: string
  empty_state?: {
    title: string
    description?: string
  }
  pagination?: {
    mode: "client" | "server"
    next_cursor?: string
    total?: number
  }
  sort?: {
    key: string
    direction: "asc" | "desc"
  }
}

type TableColumn = {
  key: string
  label: string
  data_type?: "string" | "number" | "datetime" | "duration" | "status" | "boolean" | "percent" | "bytes" | "link" | "risk"
  width?: number | string
  align?: "left" | "center" | "right"
  primary?: boolean
  hidden?: boolean
}

type TableCellValue =
  | string
  | number
  | boolean
  | null
  | {
      label?: string
      value?: string | number | boolean | null
      status?: "success" | "warning" | "danger" | "info" | "neutral" | "running"
      href?: string
      tooltip?: string
      meta?: Record<string, unknown>
    }
```

示例：

```json
{
  "type": "table",
  "title": "备份任务列表",
  "row_key": "task_id",
  "columns": [
    { "key": "task_name", "label": "任务名称", "data_type": "string", "primary": true },
    { "key": "status", "label": "状态", "data_type": "status" },
    { "key": "started_at", "label": "开始时间", "data_type": "datetime" },
    { "key": "duration_seconds", "label": "耗时", "data_type": "duration", "align": "right" }
  ],
  "rows": [
    {
      "task_id": "task_001",
      "task_name": "订单库每日备份",
      "status": { "label": "成功", "status": "success" },
      "started_at": "2026-04-20T02:00:00+08:00",
      "duration_seconds": 426
    }
  ]
}
```

## `key_value`

```ts
type KeyValueBlock = BaseBlock & {
  type: "key_value"
  items: KeyValueItem[]
  columns?: 1 | 2 | 3
}

type KeyValueItem = {
  key: string
  label: string
  value: string | number | boolean | null
  data_type?: "string" | "number" | "datetime" | "duration" | "status" | "boolean" | "percent" | "bytes" | "link" | "risk"
  status?: "success" | "warning" | "danger" | "info" | "neutral" | "running"
  tooltip?: string
}
```

## `status`

```ts
type StatusBlock = BaseBlock & {
  type: "status"
  state: "queued" | "running" | "waiting" | "success" | "warning" | "failed" | "cancelled"
  label: string
  detail?: string
  progress?: {
    current?: number
    total?: number
    percent?: number
  }
}
```

## `clarification`

```ts
type ClarificationBlock = BaseBlock & {
  type: "clarification"
  question: string
  input_mode: "single_choice" | "multi_choice" | "text" | "datetime" | "form"
  options?: Array<{
    id: string
    label: string
    description?: string
    recommended?: boolean
    disabled?: boolean
  }>
  required?: boolean
}
```

处理约束：

- `clarification` 只表达需要补充的问题、输入模式和可选项。
- 用户补充信息应作为新的用户消息提交到 Conversation Service。
- 不依赖 `actions`。

## `candidate_options`

```ts
type CandidateOptionsBlock = BaseBlock & {
  type: "candidate_options"
  reasoning_trace_id: string
  options: CandidateOption[]
  allow_revise?: boolean
}

type CandidateOption = {
  option_id: string
  title: string
  summary: string
  recommended?: boolean
  risk_level?: "low" | "medium" | "high"
  pros?: string[]
  cons?: string[]
  metrics?: KeyValueItem[]
}
```

处理约束：

- `candidate_options` 只表达候选方案数据。
- 确认、拒绝或修改应作为新的 `candidate_selection` 用户消息提交。
- 提交时携带 `reasoning_trace_id`、`candidate_option_id` 和 `selection`。
- 不依赖 `actions`。

## `timeline`

```ts
type TimelineBlock = BaseBlock & {
  type: "timeline"
  items: Array<{
    id: string
    title: string
    description?: string
    state: "pending" | "running" | "success" | "warning" | "failed" | "skipped"
    started_at?: string
    ended_at?: string
    trace_id?: string
  }>
}
```

## `metric_cards`

```ts
type MetricCardsBlock = BaseBlock & {
  type: "metric_cards"
  metrics: Array<{
    key: string
    label: string
    value: string | number
    unit?: string
    trend?: "up" | "down" | "flat"
    tone?: "normal" | "success" | "warning" | "danger"
    description?: string
  }>
}
```

## `chart`

不要返回 ECharts 或第三方图表库配置，只返回语义化图表数据。

```ts
type ChartBlock = BaseBlock & {
  type: "chart"
  chart_type: "line" | "bar" | "pie" | "area"
  x_key?: string
  y_keys?: string[]
  category_key?: string
  value_key?: string
  series?: Array<{
    key: string
    label: string
  }>
  data: Array<Record<string, string | number | null>>
}
```

## `attachment`

```ts
type AttachmentBlock = BaseBlock & {
  type: "attachment"
  attachments: Array<{
    id: string
    name: string
    mime_type?: string
    size_bytes?: number
    url?: string
    expires_at?: string
    description?: string
  }>
}
```

## `log_excerpt`

```ts
type LogExcerptBlock = BaseBlock & {
  type: "log_excerpt"
  language?: "text" | "shell" | "json" | "yaml"
  content: string
  truncated?: boolean
  source_ref?: string
}
```

## `error`

```ts
type ErrorBlock = BaseBlock & {
  type: "error"
  severity: "info" | "warning" | "danger"
  error_code?: string
  message: string
  detail?: string
  retryable?: boolean
}
```

## 完整示例

```json
{
  "message_id": "msg_1001",
  "conversation_id": "conv_9001",
  "role": "assistant",
  "content_type": "rich_content",
  "content": "我查到了最近的备份情况，并给出一个推荐恢复方案。",
  "status": "responded",
  "trace_id": "trace_abc",
  "correlation_id": "job_restore_001",
  "created_at": "2026-04-20T10:00:00+08:00",
  "payload": {
    "schema_version": "1.0",
    "blocks": [
      {
        "block_id": "text_intro",
        "type": "text",
        "text": "我查到了最近的备份情况，并给出一个推荐恢复方案。"
      },
      {
        "block_id": "backup_table",
        "type": "table",
        "title": "可用备份点",
        "row_key": "backup_id",
        "columns": [
          { "key": "asset", "label": "资产", "data_type": "string", "primary": true },
          { "key": "backup_time", "label": "备份时间", "data_type": "datetime" },
          { "key": "status", "label": "状态", "data_type": "status" }
        ],
        "rows": [
          {
            "backup_id": "bak_001",
            "asset": "订单数据库",
            "backup_time": "2026-04-19T14:45:00+08:00",
            "status": { "label": "可用", "status": "success" }
          }
        ]
      },
      {
        "block_id": "candidate_restore",
        "type": "candidate_options",
        "title": "推荐恢复方案",
        "reasoning_trace_id": "trace_abc",
        "options": [
          {
            "option_id": "option_restore_1445",
            "title": "恢复到 2026-04-19 14:45",
            "summary": "备份点可用，预计恢复时间 18 分钟。",
            "recommended": true,
            "risk_level": "low"
          }
        ]
      }
    ]
  }
}
```
