---
name: ag-ui-response
description: Use when an Agent must produce business data for the Decision Agent MQ field payload.business_data.
---

# AG-UI 业务数据回复技能

## 触发时机

在 Agent 需要向会话侧回写用户可见业务结果时，使用本技能生成结构化业务数据（`payload.business_data`），由会话服务转换为 AG-UI 事件。

适用内容包括：

- 候选方案对比与选择（plan_candidates）
- 执行进度报告（progress_report）
- 用户澄清提示与选择（clarification_request）
- 容量趋势预测（capacity_forecast）
- 可下载附件列表（attachment_list）
- 结构化报告（report_detail）
- 纯文本消息（text_message）
- 增量更新（incremental_update）

**Skills 不返回以下内容**（由 Core Agent 通过 KWeaver 透传路径进入会话服务）：工具调用、思考链、错误信息。

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
- `payload.content`：必须提供纯文本降级摘要。

## Schema 类型目录

| schema_type | 用途 | data 必填字段 |
|---|---|---|
| `plan_candidates` | 候选方案对比+选择 | heading, candidates[]（动态 N 个） |
| `progress_report` | 执行进度报告 | heading, stage, steps[]（动态 N 个） |
| `clarification_request` | 用户澄清提示 | question, options[]（动态 N 个） |
| `capacity_forecast` | 容量趋势预测 | metrics[]（动态 N 个） |
| `attachment_list` | 可下载附件 | heading, attachments[]（动态 N 个） |
| `report_detail` | 结构化报告 | heading |
| `text_message` | 纯文本内容 | text |
| `incremental_update` | 增量更新 | target_block_id, patch[] |

## 设计原则

- **结论先行**：输出必须先给出结论或关键信息，再提供支持细节。
- **业务对象优先**：显示内容围绕用户关心的业务对象组织，不展示内部系统概念。
- **低装饰高可读**：优先使用结构化字段展示关键信息。
- **审查优先**：风险、影响和注意事项必须优先展示。
- **完整降级**：`payload.content` 必须包含核心信息摘要。

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
2. 根据 schema_type 生成完整的 `payload.business_data.data` 结构。
3. 运行校验或生成脚本，脚本补齐 MQ envelope、`event_id`、`occurred_at` 等外层字段。
4. 需要发布时追加 `--publish --rabbitmq-url <url>`。
5. MQ 发布失败必须停止当前业务动作，并输出脱敏失败说明。

只生成本地消息 JSON：

```bash
python3 -X utf8 scripts/generate_ag_ui_mq_message.py \
  --schema-type plan_candidates \
  --data-json '{"heading":"恢复候选方案","candidates":[{"candidate_option_id":"a","title":"方案A","summary":"推荐","recommendation_level":"recommended","risk_level":"medium"}]}' \
  --conversation-id "100" \
  --turn-id "200" \
  --message-id "901" \
  --sequence 1 \
  --content "恢复候选方案"
```

校验消息 JSON：

```bash
python3 -X utf8 scripts/validate_ag_ui_mq_message.py \
  --json "$message_json"
```

生成、校验并发布：

```bash
python3 -X utf8 scripts/generate_validate_publish_ag_ui_mq_message.py \
  --schema-type plan_candidates \
  --data-json '{"heading":"恢复候选方案","candidates":[{"candidate_option_id":"a","title":"方案A","summary":"推荐","recommendation_level":"recommended","risk_level":"medium"}]}' \
  --conversation-id "100" \
  --turn-id "200" \
  --message-id "901" \
  --sequence 1 \
  --content "恢复候选方案" \
  --publish \
  --rabbitmq-url amqp://guest:guest@localhost:5672/
```

## Snowflake 规则

脚本生成 `message_id` 时使用会话服务同款算法：

- epoch：`1735689600000`
- node：10 bit，固定使用技能内置值 `900`
- sequence：12 bit，由脚本在本进程内维护；同毫秒内从 `0` 递增，溢出后进入下一毫秒槽位
- 位移：`((timestamp_ms - epoch_ms) << 22) | (node_id << 12) | sequence`

调用方不传入也不覆盖 `node_id`。
