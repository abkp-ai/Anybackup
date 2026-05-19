---
name: conversation-rich-content
description: "当需要让底层智能体、Agent CLI 或消息服务生成、校验、修改 Conversation Service 的 JSON 会话消息 payload 时使用；约束输出必须是结构化 JSON，包括 payload.blocks 以及 text、table、key_value、status、clarification、candidate_options、timeline、metric_cards、chart、attachment、log_excerpt、error 等 block。MVP 范围默认不生成通用 actions。"
---

# 会话富内容

生成能被 Conversation Service 和下游消费方稳定解析的 JSON 会话消息。

当智能体或消息服务需要返回结构化 JSON 会话内容，而不是自由文本或 Markdown 表格时，使用本 skill。

## 事实来源

- 运行时 API 上下文：`../../../aa-feat/docs/需求上下文/2026-04-会话管理/契约`
- MVP block schema 参考：`references/block-schema-v1.md`

当需要精确字段、示例或校验规则时，读取 `references/block-schema-v1.md`。

## MVP 规则：不生成通用 Actions

MVP 富内容块默认不要输出 `actions`，除非用户明确要求设计或启用动作协议。

原因：

- 第一阶段只约束稳定 JSON 内容块。
- 通用 `actions` 会提前引入工作流副作用和后端编排决策。
- 交互类 block 不依赖通用 `actions` 也能工作：
  - `clarification` 提供 `question`、`input_mode`、`options`。
  - `candidate_options` 提供 `reasoning_trace_id` 和 `option_id`。
  - 消费方根据业务语义提交下一条 `POST /api/conversations/{conversation_id}/messages`。

如果输出里需要按钮，优先使用语义 block 字段表达，不要发明任意 action 类型。

## 输出形态

返回带可选富内容 payload 的 `ConversationMessage` 外壳：

```ts
{
  message_id: string
  conversation_id: string
  role: "user" | "assistant" | "system" | "status"
  content_type: "text" | "clarification" | "rich_content" | "status"
  content?: string
  payload?: {
    schema_version: "1.0"
    blocks: RichBlock[]
  }
  status: "received" | "persisted" | "published" | "processing" | "responded" | "failed"
  trace_id?: string
  correlation_id?: string
  created_at: string
}
```

规则：

- 简单纯文本消息使用 `content_type: "text"`。
- 需要 `payload.blocks` 表达结构化内容时使用 `content_type: "rich_content"`。
- 主要内容是在向用户补充提问时使用 `content_type: "clarification"`。
- 仅展示进度或处理中状态时使用 `content_type: "status"`。
- 始终提供简短的 `content` 兜底摘要，用于无障碍、通知和未知 block 兜底。
- 时间使用 ISO 8601 字符串。

## Block 选择规则

选择能保留业务语义的最小 block 类型：

| 需求 | Block |
| --- | --- |
| 自然语言回答 | `text` |
| 行列数据 | `table` |
| 少量字段摘要 | `key_value` |
| 处理中、成功、失败、等待 | `status` |
| 缺少用户输入 | `clarification` |
| 多个方案或推荐方案 | `candidate_options` |
| 步骤或执行流程 | `timeline` |
| 多个核心指标 | `metric_cards` |
| 趋势或分布 | `chart` |
| 文件、报告、日志包 | `attachment` |
| 短日志或命令输出 | `log_excerpt` |
| 可恢复或致命问题 | `error` |

能用 `table` 表达的数据，不要输出 Markdown 表格。

## Table 规则

对于 `type: "table"`：

- 必须包含 `columns` 和 `rows`。
- `columns[].key` 必须能映射到行对象字段。
- 使用 `data_type` 表达语义，例如 `status`、`datetime`、`duration`、`bytes`、`percent`、`risk`。
- 状态值使用对象单元格：`{ "label": "失败", "status": "danger" }`。
- 行数保持精简。大结果返回摘要表格加 `attachment`。
- 不返回 CSS、className、颜色值或 HTML。

## 安全与边界规则

- 不暴露原始 chain-of-thought，只返回用户可见摘要。
- 不暴露 `platform_session_id` 或其他底层平台内部标识。
- 不把完整 Plan、Asset、Foundation 或执行结果主数据复制进消息，只返回摘要或引用。
- 不返回 HTML、JavaScript、CSS class、内联 style 或消费方内部实现名。
- 不指示任何消费方直接调用 Plan Service、Foundation 或其他业务服务。
- payload 必须是有效 JSON，并且重试时保持稳定。

## 校验清单

返回富内容消息前，检查：

- `payload.schema_version` 是 `"1.0"`。
- 当 `content_type` 是 `rich_content` 或 `clarification` 时，`payload.blocks` 是非空数组。
- 每个 block 都有受支持的 `type`。
- `table` block 有 `columns` 和 `rows`。
- `candidate_options` block 有 `reasoning_trace_id` 和稳定的 `option_id`。
- `clarification` block 有 `question` 和 `input_mode`。
- MVP 输出中不包含 `actions`。
- 不包含 HTML、CSS class、内联 style 或 JavaScript。
