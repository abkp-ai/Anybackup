---
name: biz-reply
description: Use when an Agent must produce structured business data (payload.business_data) for the Decision Agent MQ path, selecting the correct schema_type and generating complete data structures.
---

# 业务回复技能

## 核心职责

本技能负责根据业务场景选择合适的 schema_type，生成完整的 `payload.business_data` 结构化业务数据，校验并发布到 MQ，由会话服务根据 schema_type 模板自动转换为交互协议事件。

本技能不直接生成交互协议事件，不选择布局节点，不操作前端渲染。交互协议事件的生成、布局树选择和模板填充由会话服务根据 schema_type 自动完成。

思考链、工具调用和错误信息由 Core Agent 通过 KWeaver 透传路径进入会话服务，不经过本技能。

## 触发时机

在 Agent 需要向会话侧回写用户可见业务结果时，使用本技能生成结构化业务数据（`payload.business_data`），由会话服务转换为交互协议事件。

适用内容包括：

- 候选方案对比与选择（plan_candidates）
- 执行进度报告（progress_report）
- 用户澄清提示与选择（clarification_request）
- 容量趋势预测（capacity_forecast）
- 可下载附件列表（attachment_list）
- 结构化报告（report_detail）
- 纯文本消息（text_message）
- 增量更新（incremental_update）

**Skills 不返回以下内容**（由 Core Agent 通过 KWeaver 透传路径进入会话服务）：思考链、工具调用、错误信息。

## 强制输出门禁

在执行任何会产生用户可见状态变化的业务动作前，必须先完成对应业务数据生成、校验和 MQ 发布。发布成功前，不得继续执行下一步业务动作。

缺少本技能时，Agent 必须停止业务执行并返回配置错误。读取本技能前，不得调用业务工具、查询知识网络、下发恢复任务或执行验证。

本技能在 Linux 沙箱中执行，运行时默认使用 UTF-8 locale。所有示例命令均按 bash 编写。

## 输出契约

MQ 外层 `payload.business_data` 必须是结构化业务数据对象，不得为字符串（包括 Markdown 字符串）。

```json
{
  "event_type": "decision_agent.session.business_data",
  "source_service": "decision_agent_session",
  "payload": {
    "conversation_id": "100",
    "turn_id": "200",
    "message_id": "901",
    "content": "恢复候选方案",
    "sequence": 1,
    "business_data": {
      "schema_type": "plan_candidates",
      "schema_version": "1",
      "data": {
        "heading": "恢复候选方案",
        "candidates": [
          {
            "candidate_option_id": "candidate_a",
            "title": "方案 A：异机数据库级恢复",
            "summary": "推荐方案",
            "recommendation_level": "recommended",
            "risk_level": "medium"
          }
        ]
      }
    }
  }
}
```

字段规则：

- `event_type`：固定为 `decision_agent.session.business_data`。
- `source_service`：固定为 `decision_agent_session`。
- `payload.business_data.schema_type`：必须为受控枚举值之一（8 种）。
- `payload.business_data.schema_version`：固定为 `"1"`。
- `payload.business_data.data`：必须符合 schema_type 对应的数据结构。
- `payload.content`：必须提供纯文本降级摘要，包含核心信息摘要，不得为空或占位文本。

## Schema 选择方法

按展示需求匹配 schema_type：

| 展示需求 | 推荐 schema_type | 说明 |
|---|---|---|
| 多个候选方案对比 | `plan_candidates` | 每个候选必须包含 candidate_option_id、title、summary、recommendation_level、risk_level |
| 执行步骤和进度 | `progress_report` | 步骤列表必须至少 1 项，支持阶段、进度百分比和预计时间 |
| 需要用户补充信息 | `clarification_request` | 必须包含至少 1 个选项，交互态必须有 selection 字段 |
| 容量趋势和告警 | `capacity_forecast` | 指标列表必须至少 1 项，支持图表和表格数据 |
| 可下载文件列表 | `attachment_list` | 附件列表必须至少 1 项，每个附件必须有 download_url 受控引用 |
| 结构化分析报告 | `report_detail` | 支持分段、指标、表格、图表和附件，段落多时自动用 tabs 组织 |
| 短文本消息 | `text_message` | 仅当无结构化数据可表达时使用，不得用 text_message 替代其他 schema_type |
| 更新已有展示块 | `incremental_update` | patch 必须是合法 JSON Patch，target_block_id 必须指向已有块 |

### 反模式

| 反模式 | 正确做法 |
|---|---|
| 把所有内容塞入一个 `text_message` | 使用合适的结构化 schema_type |
| 候选方案只有标题没有结构化字段 | 每个候选必须包含 candidate_option_id、title、summary、recommendation_level、risk_level |
| 澄清请求没有选项 | `clarification_request` 必须包含至少 1 个选项 |
| 隐藏关键风险 | 在候选方案中明确设置 risk_level |
| 交互态没有操作入口 | `plan_candidates` 和 `clarification_request` 必须包含 selection 字段 |

## Schema 类型目录

8 种受控 schema_type 及其核心必填字段：

| schema_type | 用途 | 核心必填字段 |
|---|---|---|
| `plan_candidates` | 候选方案对比+选择 | `heading`, `candidates[]` (含 `candidate_option_id`, `title`, `summary`, `recommendation_level`, `risk_level`) |
| `progress_report` | 执行进度报告 | `heading`, `stage`, `steps[]` (含 `step_id`, `label`) |
| `clarification_request` | 用户澄清提示 | `question`, `options[]` (含 `option_id`, `label`) |
| `capacity_forecast` | 容量趋势预测 | `metrics[]` (含 `label`, `current`, `capacity`) |
| `attachment_list` | 可下载附件 | `heading`, `attachments[]` (含 `attachment_id`, `filename`, `size`, `download_url`) |
| `report_detail` | 结构化报告 | `heading`（可选 `sections[]` 含 `section_id`, `title`） |
| `text_message` | 纯文本消息 | `text` |
| `incremental_update` | 增量更新 | `target_block_id`, `patch[]` |

字段详情参考 `references/schema-catalog.md`（含可选字段、子结构、默认值）。

## 设计原则

- **结论先行**：输出必须先给出结论或关键信息，再提供支持细节。标题和摘要必须直接回答用户问题，不使用"我来帮你看看"等无信息量开场白。
- **业务对象优先**：显示内容围绕用户关心的业务对象（资产、方案、恢复点、策略等）组织，不展示内部系统概念（节点名、服务名、队列名、Agent Session 等）。
- **低装饰高可读**：优先使用结构化字段展示关键信息。
- **审查优先**：风险、影响和注意事项必须优先展示。
- **完整降级**：`payload.content` 必须包含核心信息摘要。
- **结构化优先**：有结构化数据时必须使用对应 schema_type，不得退化为 `text_message`。
- **完整性**：必填字段齐全，动态数组（candidates/options/metrics/steps/attachments）至少 1 个元素。
- **一致性**：`payload.content` 与 `business_data.data` 核心信息一致。
- 用户可见内容使用业务语义名称，不显示函数式工具名。
- 业务知识网络名称、ID、对象类 ID、关系类 ID、动作类 ID 不向用户展示。
- 工具输入和结果只展示脱敏摘要，不展示原始参数、原始返回、连接串、日志、堆栈或系统提示词。
- 空结果、失败和需要确认的情况也必须给出结构化数据和用户可执行的下一步。

## 安全边界

业务数据不得包含：

- 完整内部推理链。
- 系统提示词。
- 密钥、令牌、密码或私钥。
- 原始工具参数或原始工具返回全文。
- 数据库、消息队列、对象存储或外部系统连接串。
- 未脱敏日志或敏感错误堆栈。
- 内部系统概念（节点名、服务名、队列名等）。

## 工作流

1. 读取本技能并确认必需输入：`conversation_id`、`turn_id`、`message_id`、`sequence`、`schema_type` 与业务数据。
2. 根据业务场景选择合适的 `schema_type`（参考"Schema 选择方法"）。
3. 根据 schema_type 生成完整的 `payload.business_data.data` 结构，确保所有必填字段齐全、动态数组至少 1 个元素。
4. 生成 `payload.content` 降级文本，确保与 business_data 核心信息一致。
5. 运行校验或生成脚本，脚本补齐 MQ envelope、`event_id`、`occurred_at` 等外层字段。
6. 需要发布时追加 `--publish --rabbitmq-url <url>`。
7. MQ 发布失败必须停止当前业务动作，并输出脱敏失败说明。

只生成本地消息 JSON：

```bash
python3 -X utf8 scripts/bizdata_mq_core.py \
  --schema-type plan_candidates \
  --data-json '{"heading":"恢复候选方案","candidates":[{"candidate_option_id":"a","title":"方案A","summary":"推荐","recommendation_level":"recommended","risk_level":"medium"}]}' \
  --conversation-id "100" \
  --turn-id "200" \
  --message-id "901" \
  --sequence 1 \
  --content "恢复候选方案"
```

## 渐进式披露

- 选择合适的 schema_type：先看上方"Schema 选择方法"，再看"Schema 类型目录"概览。
- 填充字段：读取 `references/schema-catalog.md`，获取该 schema_type 的完整字段定义（含可选字段、子结构、默认值）。
- 内容质量：读取 `references/content-rules.md`，明确字段级内容规则和质量约束。
- 设计原则：读取 `references/design-principles.md`，确定信息层级、状态语义和动作分级。
- 安全红线：读取 `references/visibility-policy.md`，确认哪些信息不能进入 business_data。
- 回写流程：读取 `references/flow-and-updates.md`，了解创建/替换、幂等、顺序和 quality gate。
- JSON 示例：读取 `references/examples/*.json`。
- 必填字段速查：读取 `references/schema-catalog.md` 末尾的必填字段清单，确保不遗漏。

## Snowflake 规则

脚本生成 `message_id` 时使用会话服务同款算法：

- epoch：`1735689600000`
- node：10 bit，固定使用技能内置值 `900`
- sequence：12 bit，由脚本在本进程内维护；同毫秒内从 `0` 递增，溢出后进入下一毫秒槽位
- 位移：`((timestamp_ms - epoch_ms) << 22) | (node_id << 12) | sequence`

调用方不传入也不覆盖 `node_id`。
