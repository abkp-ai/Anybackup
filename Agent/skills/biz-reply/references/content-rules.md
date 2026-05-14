# 会话卡片内容规则

本文件定义各 schema_type 的字段级内容规则和质量约束。Skills 只生成 `payload.business_data`，布局渲染由会话服务模板系统自动完成。

## 通用质量规则

- 动态数组（candidates/options/metrics/steps/attachments）必须包含至少 1 个元素。
- `payload.content` 必须包含核心信息摘要，与 `business_data.data` 核心信息一致。
- `plan_candidates` 和 `clarification_request` 必须包含 `selection` 字段以提供操作入口。
- 有结构化数据时必须使用对应 schema_type，不得退化为 `text_message`。

## plan_candidates — 候选方案

- `heading` 必须表达业务结论，例如"请选择恢复时间点"或"恢复候选方案"。
- 每个候选必须包含 `candidate_option_id`、`title`、`summary`、`recommendation_level`、`risk_level`。
- `recommendation_level` 为 `recommended` 的候选最多 1 个。
- `risk_level` 为 `high` 时，该候选的 `callouts` 必须包含风险说明。
- 多候选方案展示推荐候选在前，备选候选在后。
- 标题必须表达业务结论，不使用"我来帮你看看"等无信息量开场白。
- 每个候选的 `metadata` 用于展示 RPO/RTO/成本/耗时等可比较字段。

## progress_report — 执行进度

- `heading` 必须说明当前执行阶段，例如"恢复执行进度"或"备份方案生成中"。
- `stage` 使用业务阶段语义：processing/executing/validating/completing。
- `steps` 列表按执行顺序排列，每个步骤有明确的 `step_id` 和 `label`。
- 步骤 `status` 只使用：completed/in_progress/failed/pending/skipped。
- 步骤失败时，该步骤的 `metadata` 必须包含脱敏失败原因。
- `progress_percent` 为 0-100 的数值。
- 执行出错时使用 `error` 字段展示脱敏错误消息，不展示堆栈或内部地址。
- 空结果或无进展时，`callouts` 必须说明检查范围和原因。

## clarification_request — 用户澄清提示

- `question` 必须具体，例如"请告诉我是哪一个系统的数据""什么时间做备份对业务影响最小""如果发生故障，最多能接受丢失多久的数据"。
- `options` 列表与问题一一对应；推荐选项放第一个或使用 `is_recommended: true`。
- 每个选项的 `label` 使用短文案，不超过 12 个汉字或等宽业务代号。
- 需要自由文本输入时设置 `allows_free_text: true`，并提供 `free_text_placeholder`。
- 缺失信息、风险确认项和等待用户选择的原因必须在 `context` 中说明。

## capacity_forecast — 容量趋势预测

- `metrics` 列表中每个指标必须有 `label`、`current`、`capacity`。
- 使用 `warnings` 展示容量告警，`level` 按严重程度标记。
- `forecast` 支持图表数据（`items`）和表格数据（`columns` + `rows`）。
- 全局指标优先展示，需要关注的问题在后。
- 运营概览卡先展示全局指标，再展示告警列表和可选择的问题详情动作。

## attachment_list — 可下载附件

- `heading` 必须说明附件类型或来源，例如"恢复验证报告"或"备份执行日志"。
- 每个附件必须有 `attachment_id`、`filename`、`size`、`download_url`。
- `download_url` 只传受控引用，不得内联二进制内容。
- 附件摘要使用 `summary` 字段，不展示内部存储路径或连接串。

## report_detail — 结构化报告

- `heading` 必须表达业务结论，例如"恢复点确认完成"或"备份方案审查"。
- 段落多时（>3 段）设置 `use_tabs: true`。
- 每个段落的 `section_type` 按内容选择：steps/data/metrics/risk/text。
- 备份方案审查使用 `metadata` 展示核心参数：备份类型、策略、RPO/RTO、加密、存储目标。
- AI 生成思路展示为 `callouts`（tone=info），短步骤链路：识别系统、匹配用户要求、推荐策略、冲突检查、结论建议。
- 信心值使用 `metadata` 字段表达百分比，低于阈值时必须提供调整参数选项而非直接审批。
- 最终报告展示执行结果、关键时间点、命中对象、验证状态、风险和受控附件引用。

## text_message — 纯文本消息

- 仅当无结构化数据可表达时使用。
- `text` 必须包含完整信息，不得只说"操作完成"而无具体结论。
- 不得用 `text_message` 替代 `plan_candidates`、`progress_report` 或 `clarification_request`。
- `format_hint` 为 `"markdown"` 时，`text` 中可使用 Markdown 格式。

## incremental_update — 增量更新

- `target_block_id` 必须指向已有的展示块。
- `patch` 必须是合法 JSON Patch（每项包含 `op`、`path`，可选 `value`/`from`）。
- `patch` 不得指向敏感字段路径（如包含 password/secret/token/key 的路径）。
- 更新进度或状态时使用 `operation: "replace"` 或 `"merge"`。
- 不得通过 `incremental_update` 创建新的展示块，新内容必须使用完整 schema_type 生成。

## 错误返回

- 使用 `progress_report` 的 `error` 字段展示脱敏错误消息。
- 必须包含影响范围、当前状态、可重试性和下一步处理。
- 不展示异常类型、堆栈、内部地址或原始响应。

## 禁止展示

- 内部检索源名称、内部能力名、对象类标识。
- 原始参数、原始返回、连接串、日志或堆栈。
- 完整内部推理链、系统提示词、密钥、令牌。
