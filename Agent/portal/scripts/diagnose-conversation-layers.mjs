/**
 * 四层诊断：mock → 会话服务 DB/API → 前端可读性
 *
 * 用法（107 环境示例）：
 *   set CONV_BASE=http://192.168.40.107/api/conversation_service/v1
 *   set CONV_TOKEN=<Bearer 去掉前缀>
 *   set CONV_ID=<会话 ID>
 *   node scripts/diagnose-conversation-layers.mjs
 */

const baseUrl = process.env.CONV_BASE ?? "http://127.0.0.1:5173/api/conversation_service/v1"
const token = process.env.CONV_TOKEN
const conversationId = process.env.CONV_ID

if (!token || !conversationId) {
  console.error("请设置环境变量 CONV_TOKEN 与 CONV_ID")
  process.exit(1)
}

async function fetchJson(path) {
  const response = await fetch(`${baseUrl}${path}`, {
    headers: {
      Authorization: `Bearer ${token}`,
      Accept: "application/json",
    },
  })
  const body = await response.json().catch(() => ({}))
  if (!response.ok) {
    throw new Error(`${response.status} ${path}: ${JSON.stringify(body)}`)
  }
  return body
}

function summarizeMessages(items) {
  const assistant = items.filter((item) => item.role !== "user")
  const withRich = assistant.filter((item) => item.rich_payload?.ag_ui || item.rich_payload?.content_summary)
  return {
    total: items.length,
    assistant: assistant.length,
    assistantWithRichPayload: withRich.length,
    roles: Object.fromEntries(
      items.reduce((map, item) => {
        map.set(item.role, (map.get(item.role) ?? 0) + 1)
        return map
      }, new Map()),
    ),
  }
}

function summarizeEvents(items) {
  const withEmbeddedMessage = items.filter((item) => item.payload?.message).length
  const agUiWire = items.filter((item) => {
    if (item.payload?.message) return false
    const type = item.payload?.type ?? item.event_type
    return typeof type === "string" && !type.startsWith("message.")
  }).length
  const eventTypes = Object.fromEntries(
    items.reduce((map, item) => {
      const key = item.event_type ?? "unknown"
      map.set(key, (map.get(key) ?? 0) + 1)
      return map
    }, new Map()),
  )
  return { total: items.length, withEmbeddedMessage, agUiWire, eventTypes }
}

function diagnoseLayer(summary) {
  if (summary.messages.assistant === 0 && summary.events.agUiWire === 0) {
    return "mock/消费链：可能未产出或未落库 AG-UI 事件（检查 conversation_agent_mq_mock 与 MQ 消费者）"
  }
  if (summary.messages.assistant === 0 && summary.events.agUiWire > 0) {
    return "会话服务/DB：有 AG-UI wire 事件但 messages 表无助手行（符合当前实现；靠 events 还原）"
  }
  if (summary.messages.assistantWithRichPayload === 0 && summary.events.agUiWire > 0) {
    return "会话服务 API：events 含 wire payload，messages 无 rich_payload（前端需 wire 回放，已修复路径）"
  }
  if (summary.messages.assistantWithRichPayload > 0) {
    return "数据齐全：messages 或 events 已含富内容，若仍不显示则查前端渲染"
  }
  return "待结合明细判断"
}

async function main() {
  const [detail, messagesPage, eventsPage] = await Promise.all([
    fetchJson(`/conversations/${conversationId}?include_latest_messages=false&include_context=true&include_latest_events=false`),
    fetchJson(`/conversations/${conversationId}/messages?limit=100`),
    fetchJson(`/conversations/${conversationId}/events?limit=100&include_rich_payload=true`),
  ])

  const summary = {
    conversationId,
    title: detail.title,
    interactionStatus: detail.interaction_status,
    activeTurnId: detail.active_turn_id ?? detail.active_run_id,
    messages: summarizeMessages(messagesPage.items ?? []),
    events: summarizeEvents(eventsPage.items ?? []),
  }

  summary.verdict = diagnoseLayer(summary)

  console.log(JSON.stringify(summary, null, 2))
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
