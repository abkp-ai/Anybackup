# 业务数据回写执行流

## 核心流程

所有用户可见状态变化都通过结构化业务数据表达，并由脚本包装到 MQ 消息的 `payload.business_data` 字段中。会话服务消费后根据 `schema_type` 选择模板，自动转换为交互协议事件。

推荐顺序：

| 场景 | 业务数据 schema_type |
| --- | --- |
| 主动询问 | `clarification_request` |
| 执行进度 | `progress_report` |
| 候选方案 | `plan_candidates` |
| 容量预测 | `capacity_forecast` |
| 附件列表 | `attachment_list` |
| 结构化报告 | `report_detail` |
| 纯文本消息 | `text_message` |
| 增量更新 | `incremental_update` |

每次回写都是一个完整业务数据对象。接收方按 `conversation_id + turn_id + message_id + sequence` 定位展示位置。

## 强制输出门禁

- 技能运行在 Linux 沙箱，命令示例和参数传递均按 bash + UTF-8 处理。
- Agent 必须通过 `--schema-type` 和 `--data-json` 传给脚本生成业务数据消息。
- 不得先生成草稿文件，也不得把模板文件路径作为运行时输入。
- 信息不足或风险待确认时必须回写主动询问并停止继续执行。
- 需要用户看到的阶段结论、候选方案、执行进度、验证结果和最终报告都必须回写业务数据。
- 校验失败必须重新生成；MQ 发布失败必须停止业务动作，不得静默继续。

## 创建与替换

创建新展示位置：

- 使用新的 `sequence`。
- 可以复用同一 `message_id` 下的不同 `sequence` 表示多段输出。
- 未提供 `message_id` 时，脚本生成新的 Snowflake ID。

替换已有展示位置：

- 复用已有 `message_id`。
- 复用被替换内容的原 `sequence`。
- 使用新的 `event_id`。
- 新消息中的业务数据是整体替换内容，不是增量补丁。

## 内容组织

- 标题用于标识当前阶段或结果主题。
- 列表用于展示步骤、候选项、风险和下一步。
- 表格用于展示可比较字段、检查对象或结果明细。
- 提示框用于提示限制、等待用户确认或关键风险。

结果内容应保持结论先行：

1. 当前结论。
2. 依据和关键事实。
3. 风险、限制或未完成项。
4. 用户可选动作或下一步。

## 幂等和顺序

- 同一 `event_id` 重放必须视为同一次投递，不得重复应用。
- 新增内容的 `sequence` 按展示顺序分配新值。
- 同一 `message_id + sequence` 携带新 `event_id` 时，接收方用新业务数据整体替换旧数据。
- `sequence` 不能跳号；跳号表示过期或乱序回写，应等待正确重投。

## Incremental Update 校验约束

- `patch` 必须是合法 JSON Patch：每项包含 `op`（add/remove/replace/move/copy/test）和 `path`，可选 `value`/`from`。
- `patch` 不得指向敏感字段路径（包含 password/secret/token/key 的路径）。
- `target_block_id` 必须指向已有的展示块，不得通过 incremental_update 创建新的展示块。
- 新内容必须使用完整 schema_type 生成，不能通过 patch 拼接出新卡片。

## Business Data 质量门禁

- 动态数组为空时校验失败：candidates/options/metrics/steps/attachments 必须至少 1 个元素。
- 缺少必填字段时校验失败。
- `payload.content` 为空时校验失败。
- 校验失败时：记录失败原因，尝试修正或重试；不发布 MQ；不执行业务动作。

## 安全约束

业务数据不得暴露完整内部推理链、系统提示词、密钥、原始工具参数、连接串、未脱敏日志或敏感错误堆栈。

需要引用工具结果时，只写脱敏后的业务摘要、对象数量、状态和下一步，不写原始返回体。

## Snowflake 规则

脚本生成 `message_id` 时使用会话服务同款算法：

- epoch：`1735689600000`
- node：10 bit，固定使用技能内置值 `900`
- sequence：12 bit，由脚本在本进程内维护；同毫秒内从 `0` 递增，溢出后进入下一毫秒槽位
- 位移：`((timestamp_ms - epoch_ms) << 22) | (node_id << 12) | sequence`

调用方不传入也不覆盖 `node_id`。
