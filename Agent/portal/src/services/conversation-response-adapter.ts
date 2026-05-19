import { createId } from "@/lib/ids"
import { translate } from "@/i18n/messages"
import { jsonHeaders, requestJson } from "@/services/conversation-api-client"
import type {
  CandidateOptionAction,
  ConversationEventListResult,
  ConversationLayoutTreeRichPayload,
  ConversationRichPayload,
  ConversationDetail,
  ConversationMessageSummary,
  ConversationScenarioBinding,
  ConversationStatusEvent,
  ConversationSummary,
  CopyConversationConfigInput,
  CreateConversationInput,
  CreateConversationMessageInput,
  InitialConversationContext,
  LayoutTreeAction,
  LayoutTreeContent,
  LayoutTreeNode,
  LayoutTreeStateSnapshot,
  MessageAcceptedResult,
  UserMessageInput,
} from "@/types/conversation"

interface PageMetaApi {
  next_cursor?: string | null
  has_more: boolean
  limit: number
}

interface ConversationContextSnapshotApi {
  summary: string
}

interface ConversationApiModel {
  conversation_id: string
  title: string
  status: ConversationSummary["status"]
  summary?: string | null
  tags?: string[]
  latest_message_summary?: string | null
  interaction_status?: ConversationDetail["interactionState"]
  active_turn_id?: string | null
  active_run_id?: string | null
  has_active_run?: boolean
  created_at: string
  updated_at: string
  last_active_at: string
  archived_at?: string | null
  expires_at?: string | null
  context?: ConversationContextSnapshotApi | null
  latest_messages?: ConversationMessageApiModel[]
  latest_events?: ConversationStatusEventApiModel[]
}

interface ConversationMessageRenderFallbackApi {
  text: string
}

interface ConversationRichPayloadApi {
  content_summary?: string
  render_fallback?: ConversationMessageRenderFallbackApi | null
  ag_ui?: ConversationAgUiPayloadApi | string | null
}

interface ConversationAgUiCustomEventApi {
  type: "CUSTOM"
  timestamp?: number
  name: string
  value?: Record<string, unknown>
}

interface ConversationAgUiActivitySnapshotEventApi {
  type: "ACTIVITY_SNAPSHOT"
  timestamp?: number
  messageId?: string
  activityType?: string
  content?: Record<string, unknown>
}

interface ConversationAgUiActivityDeltaEventApi {
  type: "ACTIVITY_DELTA"
  timestamp?: number
  messageId?: string
  activityType?: string
  patch?: unknown
}

interface ConversationAgUiStateSnapshotEventApi {
  type: "STATE_SNAPSHOT"
  timestamp?: number
  snapshot?: Record<string, unknown>
  state?: Record<string, unknown>
}

interface ConversationAgUiStateDeltaEventApi {
  type: "STATE_DELTA"
  timestamp?: number
  delta?: unknown
  operation?: "patch" | "merge" | "replace" | string
}

interface ConversationAgUiRunStartedEventApi {
  type: "RUN_STARTED"
  timestamp?: number
  threadId?: string
  runId?: string
}

interface ConversationAgUiRunFinishedEventApi {
  type: "RUN_FINISHED"
  timestamp?: number
  threadId?: string
  runId?: string
  reason?: string
}

interface ConversationAgUiRunErrorEventApi {
  type: "RUN_ERROR"
  timestamp?: number
  threadId?: string
  runId?: string
  error?: Record<string, unknown>
}

interface ConversationAgUiTextMessageStartEventApi {
  type: "TEXT_MESSAGE_START"
  timestamp?: number
  messageId?: string
  role?: string
}

interface ConversationAgUiTextMessageContentEventApi {
  type: "TEXT_MESSAGE_CONTENT"
  timestamp?: number
  messageId?: string
  delta?: string
}

interface ConversationAgUiTextMessageEndEventApi {
  type: "TEXT_MESSAGE_END"
  timestamp?: number
  messageId?: string
}

export type ConversationAgUiEventApi =
  | ConversationAgUiCustomEventApi
  | ConversationAgUiActivitySnapshotEventApi
  | ConversationAgUiActivityDeltaEventApi
  | ConversationAgUiStateSnapshotEventApi
  | ConversationAgUiStateDeltaEventApi
  | ConversationAgUiRunStartedEventApi
  | ConversationAgUiRunFinishedEventApi
  | ConversationAgUiRunErrorEventApi
  | ConversationAgUiTextMessageStartEventApi
  | ConversationAgUiTextMessageContentEventApi
  | ConversationAgUiTextMessageEndEventApi

interface ConversationAgUiPayloadApi {
  version?: string
  events?: ConversationAgUiEventApi[]
}

interface ConversationMessageApiModel {
  message_id: string
  conversation_id: string
  turn_id?: string | null
  parent_message_id?: string | null
  client_message_id?: string | null
  role: ConversationMessageSummary["role"]
  content_type: ConversationMessageSummary["contentType"]
  content?: string | null
  rich_payload?: ConversationRichPayloadApi | null
  status: ConversationMessageSummary["status"]
  error_code?: string | null
  error_message?: string | null
  trace_id?: string | null
  correlation_id?: string | null
  created_at?: string | null
  updated_at?: string | null
}

interface ConversationListResponseApi {
  items: ConversationApiModel[]
  page: PageMetaApi
}

interface MessageListResponseApi {
  items: ConversationMessageApiModel[]
  page: PageMetaApi
}

interface MessageAcceptedResponseApi {
  message: ConversationMessageApiModel
  conversation: ConversationApiModel
  status_event: ConversationStatusEventApiModel
  next_poll_after_ms: number
}

interface ConversationStatusEventPayloadApi {
  message?: ConversationMessageApiModel
  rich_payload?: ConversationRichPayloadApi | null
  active_turn_id?: string | null
  completed_turn_id?: string
  ag_ui_sequence?: number | null
  type?: string
  [key: string]: unknown
}

interface ConversationStatusEventApiModel {
  status_event_id: string
  conversation_id: string
  turn_id?: string | null
  message_id?: string | null
  event_type: ConversationStatusEvent["eventType"]
  sequence: number
  interaction_status?: ConversationStatusEvent["interactionState"] | null
  message_status?: ConversationStatusEvent["messageStatus"] | null
  payload?: ConversationStatusEventPayloadApi | null
  rich_payload?: ConversationRichPayloadApi | null
  created_at?: string | null
  occurred_at?: string | null
}

interface EventListResponseApi {
  items: ConversationStatusEventApiModel[]
  page: PageMetaApi
  latest_sequence: number
  recommended_poll_interval_ms: number
  interaction_status?: ConversationDetail["interactionState"]
}

interface ScenarioBindingApi {
  scenario_id?: string
  scenario_name?: string
  task_type?: string
}

interface InitialConversationContextApi {
  summary?: string
  key_variables?: Record<string, string>
}

interface CreateConversationRequestApi {
  initial_message: UserMessageRequestApi
  title?: string
  tags?: string[]
  scenario_binding?: ScenarioBindingApi
  initial_context?: InitialConversationContextApi
  source: "web"
  idempotency_key?: string
}

interface UserMessageRequestApi {
  type: "user_message"
  content: string
  client_message_id?: string
  parent_message_id?: string
  idempotency_key?: string
}

interface CandidateSelectionRequestApi {
  type: "candidate_selection"
  message_id?: string
  reasoning_trace_id: string
  candidate_option_id: string
  selection: "confirm" | "reject" | "revise"
  additional_constraints?: string
  client_message_id?: string
  idempotency_key?: string
}

interface ClarificationResponseRequestApi {
  type: "clarification_response"
  message_id?: string
  clarification_id?: string
  selected_value?: string
  free_text?: string
  client_message_id?: string
  idempotency_key?: string
}

type CreateConversationMessageRequestApi =
  | UserMessageRequestApi
  | CandidateSelectionRequestApi
  | ClarificationResponseRequestApi

interface ArchiveConversationRequestApi {
  reason?: string
}

interface CopyConversationConfigRequestApi {
  title?: string
  copy_tags?: boolean
  copy_scenario_binding?: boolean
  additional_tags?: string[]
}

const CONVERSATIONS_PATH = "/conversations"
const DEFAULT_CONVERSATION_LIMIT = 100
const DEFAULT_MESSAGE_LIMIT = 100
const CANDIDATE_OPTIONS_RENDER_EVENT = "anybackup.conversation.candidate_options.render"
const CLARIFICATION_RENDER_EVENT = "anybackup.conversation.clarification.render"
const THOUGHT_RENDER_EVENT = "anybackup.conversation.thought.render"
const RESULT_RENDER_EVENT = "anybackup.conversation.result.render"
const LAYOUT_TREE_ACTIVITY_TYPE = "conversation.ui.layout-tree"
const LAYOUT_TREE_CONTRACT = "conversation.ui.layout-tree@1"

function appendIfPresent(params: URLSearchParams, key: string, value: string | number | boolean | undefined): void {
  if (value === undefined) return
  params.set(key, String(value))
}

function buildPath(path: string, query?: URLSearchParams): string {
  const serialized = query?.toString()
  return serialized ? `${path}?${serialized}` : path
}

function conversationPath(conversationId: string): string {
  return `${CONVERSATIONS_PATH}/${encodeURIComponent(conversationId)}`
}

function messagesPath(conversationId: string): string {
  return `${conversationPath(conversationId)}/messages`
}

function eventsPath(conversationId: string): string {
  return `${conversationPath(conversationId)}/events`
}

function archivePath(conversationId: string): string {
  return `${conversationPath(conversationId)}/archive`
}

function restorePath(conversationId: string): string {
  return `${conversationPath(conversationId)}/restore`
}

function copyConfigPath(conversationId: string): string {
  return `${conversationPath(conversationId)}/copy-config`
}

function normalizedText(value?: string | null): string | undefined {
  const trimmed = value?.trim()
  return trimmed ? trimmed : undefined
}

function normalizedUnknownText(value: unknown): string | undefined {
  return typeof value === "string" ? normalizedText(value) : undefined
}

function normalizedUnknownRecord(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : undefined
}

function normalizedUnknownArray<T = unknown>(value: unknown): T[] | undefined {
  return Array.isArray(value) ? (value as T[]) : undefined
}

type JsonPatchOperation = {
  op: string
  path: string
  value?: unknown
  from?: string
}

function deepClone<T>(value: T): T {
  if (value === undefined || value === null || typeof value !== "object") {
    return value
  }
  return JSON.parse(JSON.stringify(value)) as T
}

function decodeJsonPointerSegment(segment: string): string {
  return segment.replace(/~1/g, "/").replace(/~0/g, "~")
}

function getJsonPointerSegments(path: string): string[] | undefined {
  if (path === "") return []
  if (!path.startsWith("/")) return undefined
  return path
    .slice(1)
    .split("/")
    .map((segment) => decodeJsonPointerSegment(segment))
}

function getValueAtPointer(document: unknown, path: string): unknown {
  const segments = getJsonPointerSegments(path)
  if (!segments) return undefined

  let current: unknown = document
  for (const segment of segments) {
    if (Array.isArray(current)) {
      const index = Number(segment)
      if (!Number.isInteger(index) || index < 0 || index >= current.length) return undefined
      current = current[index]
      continue
    }

    if (!current || typeof current !== "object") return undefined
    current = (current as Record<string, unknown>)[segment]
  }

  return current
}

function getPointerContainer(
  document: unknown,
  path: string,
): { container: unknown[] | Record<string, unknown>; key: string } | undefined {
  const segments = getJsonPointerSegments(path)
  if (!segments || segments.length === 0) return undefined

  let current: unknown = document
  for (const segment of segments.slice(0, -1)) {
    if (Array.isArray(current)) {
      const index = Number(segment)
      if (!Number.isInteger(index) || index < 0 || index >= current.length) return undefined
      current = current[index]
      continue
    }

    if (!current || typeof current !== "object") return undefined
    current = (current as Record<string, unknown>)[segment]
  }

  if (Array.isArray(current) || (current && typeof current === "object")) {
    return {
      container: current as unknown[] | Record<string, unknown>,
      key: segments[segments.length - 1],
    }
  }

  return undefined
}

function applyAddLikeOperation(
  document: unknown,
  path: string,
  value: unknown,
  mode: "add" | "replace",
): unknown {
  if (path === "") return deepClone(value)

  const target = getPointerContainer(document, path)
  if (!target) return document

  if (Array.isArray(target.container)) {
    if (target.key === "-") {
      if (mode === "replace") return document
      target.container.push(deepClone(value))
      return document
    }

    const index = Number(target.key)
    if (!Number.isInteger(index) || index < 0) return document

    if (mode === "add") {
      if (index > target.container.length) return document
      target.container.splice(index, 0, deepClone(value))
      return document
    }

    if (index >= target.container.length) return document
    target.container[index] = deepClone(value)
    return document
  }

  target.container[target.key] = deepClone(value)
  return document
}

function removeAtPointer(document: unknown, path: string): unknown {
  if (path === "") return undefined

  const target = getPointerContainer(document, path)
  if (!target) return document

  if (Array.isArray(target.container)) {
    const index = Number(target.key)
    if (!Number.isInteger(index) || index < 0 || index >= target.container.length) return document
    target.container.splice(index, 1)
    return document
  }

  delete target.container[target.key]
  return document
}

function applyJsonPatch(document: unknown, patch: unknown): unknown {
  const operations = normalizedUnknownArray<JsonPatchOperation>(patch)
  if (!operations || operations.length === 0) return document

  let nextDocument = deepClone(document)

  for (const operation of operations) {
    const op = normalizedUnknownText(operation.op)
    const path = typeof operation.path === "string" ? operation.path : undefined
    if (!op || path === undefined) continue

    switch (op) {
      case "add":
        nextDocument = applyAddLikeOperation(nextDocument, path, operation.value, "add")
        break
      case "replace":
        nextDocument = applyAddLikeOperation(nextDocument, path, operation.value, "replace")
        break
      case "remove":
        nextDocument = removeAtPointer(nextDocument, path)
        break
      case "copy": {
        const from = typeof operation.from === "string" ? operation.from : undefined
        if (!from) break
        const copiedValue = getValueAtPointer(nextDocument, from)
        nextDocument = applyAddLikeOperation(nextDocument, path, copiedValue, "add")
        break
      }
      case "move": {
        const from = typeof operation.from === "string" ? operation.from : undefined
        if (!from) break
        const movedValue = getValueAtPointer(nextDocument, from)
        nextDocument = removeAtPointer(nextDocument, from)
        nextDocument = applyAddLikeOperation(nextDocument, path, movedValue, "add")
        break
      }
      case "test":
      default:
        break
    }
  }

  return nextDocument
}

function normalizedTags(tags?: string[]): string[] | undefined {
  const values = tags?.map((tag) => tag.trim()).filter(Boolean)
  return values && values.length > 0 ? values : undefined
}

function resolveMessageContent(message: ConversationMessageApiModel): string {
  const directContent = normalizedText(message.content)
  if (directContent) return directContent

  const agUiTextContent = resolveAgUiTextContent(message)
  if (agUiTextContent) return agUiTextContent

  const fallbackText = normalizedText(message.rich_payload?.render_fallback?.text)
  if (fallbackText) return fallbackText

  const summary = normalizedText(message.rich_payload?.content_summary)
  if (summary) return summary

  if (message.content_type === "rich_content") return translate("conversation.placeholder.richContent")
  if (message.content_type === "clarification") return translate("conversation.placeholder.clarification")
  if (message.content_type === "status") return translate("conversation.placeholder.status")
  return ""
}

function findAgUiEvent(
  message: ConversationMessageApiModel,
  eventName: string,
): ConversationAgUiCustomEventApi | undefined {
  return resolveAgUiEvents(message).find(
    (event): event is ConversationAgUiCustomEventApi => event.type === "CUSTOM" && event.name === eventName,
  )
}

function findFirstAgUiEvent(message: ConversationMessageApiModel): ConversationAgUiCustomEventApi | undefined {
  return resolveAgUiEvents(message).find((event): event is ConversationAgUiCustomEventApi => event.type === "CUSTOM")
}

function resolveLatestAgUiEventName(message: ConversationMessageApiModel): string | undefined {
  const events = resolveAgUiEvents(message)
  if (events.length === 0) return undefined

  const latestEvent = events[events.length - 1]
  if (latestEvent.type === "CUSTOM") {
    return normalizedUnknownText(latestEvent.name) ?? latestEvent.type
  }

  return latestEvent.type
}

function resolveAgUiPayload(message: ConversationMessageApiModel): ConversationAgUiPayloadApi | undefined {
  const payload = message.rich_payload?.ag_ui
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) return undefined
  return payload as ConversationAgUiPayloadApi
}

function createSyntheticAgUiMessage(events: ConversationAgUiEventApi[]): ConversationMessageApiModel {
  return {
    message_id: "synthetic_ag_ui_message",
    conversation_id: "synthetic_conversation",
    role: "assistant",
    content_type: "rich_content",
    status: "streaming",
    rich_payload: {
      ag_ui: {
        version: "1",
        events,
      },
    },
  }
}

function resolveAgUiEvents(message: ConversationMessageApiModel): ConversationAgUiEventApi[] {
  return resolveAgUiPayload(message)?.events ?? []
}

function resolveAgUiMarkdownContent(message: ConversationMessageApiModel): string | undefined {
  const payload = message.rich_payload?.ag_ui
  if (typeof payload !== "string") return undefined

  return decodePossiblyEscapedMarkdown(payload)
}

function decodePossiblyEscapedMarkdown(raw: string): string | undefined {
  const trimmed = raw.trim()
  if (!trimmed) return undefined

  const hasEscapedMarkdownSignals =
    trimmed.includes("\\n") || trimmed.includes('\\"') || trimmed.includes("\\t")
  if (!hasEscapedMarkdownSignals) {
    return normalizedText(trimmed)
  }

  try {
    const parsed = JSON.parse(trimmed)
    if (typeof parsed === "string") {
      return normalizedText(parsed)
    }
  } catch {
    // The payload can be a plain markdown string; keep fallback decoding below.
  }

  const fallbackDecoded = trimmed
    .replace(/\\r\\n/g, "\n")
    .replace(/\\n/g, "\n")
    .replace(/\\t/g, "\t")
    .replace(/\\"/g, '"')
    .replace(/\\\\/g, "\\")

  return normalizedText(fallbackDecoded)
}

function resolveAgUiTextContent(message: ConversationMessageApiModel): string | undefined {
  const events = resolveAgUiEvents(message)
  const buffers = new Map<string, string[]>()
  const order: string[] = []

  for (const event of events) {
    if (event.type === "TEXT_MESSAGE_START" || event.type === "TEXT_MESSAGE_END") {
      const messageId = normalizedUnknownText(event.messageId)
      if (!messageId) continue
      if (!buffers.has(messageId)) {
        buffers.set(messageId, [])
        order.push(messageId)
      }
      continue
    }

    if (event.type === "TEXT_MESSAGE_CONTENT") {
      const messageId = normalizedUnknownText(event.messageId)
      const delta = typeof event.delta === "string" ? event.delta : undefined
      if (!messageId || !delta) continue

      if (!buffers.has(messageId)) {
        buffers.set(messageId, [])
        order.push(messageId)
      }

      buffers.get(messageId)?.push(delta)
    }
  }

  for (const messageId of [...order].reverse()) {
    const text = normalizedText(buffers.get(messageId)?.join(""))
    if (text) return text
  }

  return undefined
}

function resolveLayoutTreeActivityContent(message: ConversationMessageApiModel): LayoutTreeContent | undefined {
  const events = resolveAgUiEvents(message)
  const activities = new Map<string, unknown>()
  const order: string[] = []

  for (const event of events) {
    if (
      event.type === "ACTIVITY_SNAPSHOT" &&
      event.activityType === LAYOUT_TREE_ACTIVITY_TYPE &&
      normalizedUnknownRecord(event.content)?.contract === LAYOUT_TREE_CONTRACT
    ) {
      const messageId = normalizedUnknownText(event.messageId)
      if (!messageId) continue
      activities.set(messageId, deepClone(event.content))
      if (!order.includes(messageId)) order.push(messageId)
      continue
    }

    if (event.type === "ACTIVITY_DELTA") {
      const messageId = normalizedUnknownText(event.messageId)
      if (!messageId || !activities.has(messageId)) continue
      activities.set(messageId, applyJsonPatch(activities.get(messageId), event.patch))
    }
  }

  for (const messageId of [...order].reverse()) {
    const activity = toLayoutTreeContent(activities.get(messageId))
    if (activity) return activity
  }

  return undefined
}

function resolveLayoutTreeStateSnapshot(message: ConversationMessageApiModel): LayoutTreeStateSnapshot | undefined {
  const events = resolveAgUiEvents(message)
  let snapshot: unknown

  for (const event of events) {
    if (event.type === "STATE_SNAPSHOT") {
      const sourceState = normalizedUnknownRecord((event as { state?: unknown }).state) ?? normalizedUnknownRecord(event.snapshot)
      if (!sourceState) continue
      snapshot = deepClone(sourceState)
      continue
    }

    if (event.type === "STATE_DELTA" && snapshot !== undefined) {
      const operation = normalizedUnknownText((event as { operation?: unknown }).operation) ?? "patch"

      const deltaRecord = normalizedUnknownRecord(event.delta)

      if (operation === "merge" && deltaRecord) {
        snapshot = {
          ...(normalizedUnknownRecord(snapshot) ?? {}),
          ...deltaRecord,
        }
        continue
      }

      if (operation === "replace") {
        snapshot = deepClone(event.delta)
        continue
      }

      snapshot = applyJsonPatch(snapshot, event.delta)
    }
  }

  return toLayoutTreeStateSnapshot(snapshot)
}

function normalizedDisplayValue(value: unknown): string | undefined {
  if (typeof value === "string") return normalizedText(value)
  if (typeof value === "number" || typeof value === "boolean") return String(value)
  return undefined
}

function normalizeLayoutTreeNodeProps(type: string, props: Record<string, unknown>): Record<string, unknown> {
  const nextProps = { ...props }

  if (type === "kv-list") {
    const rows = normalizedUnknownArray(nextProps.rows)
    if (rows && !normalizedUnknownArray(nextProps.items)) {
      nextProps.items = rows
    }
    delete nextProps.rows
  }

  if ("children" in nextProps) {
    delete nextProps.children
  }

  return nextProps
}

function resolveLayoutTreeChildNodes(record: Record<string, unknown>): unknown[] | undefined {
  const topLevelChildren = normalizedUnknownArray(record.children)
  if (topLevelChildren) return topLevelChildren

  const props = normalizedUnknownRecord(record.props)
  return normalizedUnknownArray(props?.children)
}

function toLayoutTreeNode(value: unknown): LayoutTreeNode | undefined {
  const record = normalizedUnknownRecord(value)
  const type = normalizedUnknownText(record?.type)
  if (!record || !type) return undefined

  const childNodes = resolveLayoutTreeChildNodes(record)
  const children = childNodes
    ?.map((child) => toLayoutTreeNode(child))
    .filter((child): child is NonNullable<typeof child> => child !== undefined)

  const rawProps = normalizedUnknownRecord(record.props)
  const props = rawProps ? normalizeLayoutTreeNodeProps(type, rawProps) : undefined

  return {
    ...(normalizedUnknownText(record.id) ? { id: normalizedUnknownText(record.id) } : {}),
    type: type as LayoutTreeNode["type"],
    ...(props && Object.keys(props).length > 0 ? { props } : {}),
    ...(children && children.length > 0 ? { children } : {}),
  }
}

function toLayoutTreeAction(value: unknown): LayoutTreeAction | undefined {
  const record = normalizedUnknownRecord(value)
  const id = normalizedUnknownText(record?.id)
  const kind = normalizedUnknownText(record?.kind)
  const label = normalizedUnknownText(record?.label)

  if (!record || !id || !kind || !label) return undefined

  return {
    id,
    kind: kind as LayoutTreeAction["kind"],
    label,
    ...(normalizedUnknownText(record.style) ? { style: normalizedUnknownText(record.style) as LayoutTreeAction["style"] } : {}),
    ...(normalizedUnknownRecord(record.payload) ? { payload: normalizedUnknownRecord(record.payload) } : {}),
    ...(normalizedUnknownText(record.confirmText) ? { confirmText: normalizedUnknownText(record.confirmText) } : {}),
  }
}

function toLayoutTreeContent(value: unknown): LayoutTreeContent | undefined {
  const record = normalizedUnknownRecord(value)
  const contract = normalizedUnknownText(record?.contract)
  const blockId = normalizedUnknownText(record?.blockId)
  const ui = toLayoutTreeNode(record?.ui)

  if (!record || contract !== LAYOUT_TREE_CONTRACT || !blockId || !ui) return undefined

  const actions = normalizedUnknownArray(record.actions)
    ?.map((action) => toLayoutTreeAction(action))
    .filter((action): action is NonNullable<typeof action> => action !== undefined)

  const metaRecord = normalizedUnknownRecord(record.meta)

  return {
    contract: LAYOUT_TREE_CONTRACT,
    blockId,
    ui,
    ...(actions && actions.length > 0 ? { actions } : {}),
    ...(metaRecord
      ? {
          meta: {
            ...(normalizedUnknownText(metaRecord.intent)
              ? { intent: normalizedUnknownText(metaRecord.intent) as NonNullable<LayoutTreeContent["meta"]>["intent"] }
              : {}),
            ...(typeof metaRecord.terminal === "boolean" ? { terminal: metaRecord.terminal } : {}),
            ...(normalizedUnknownText(metaRecord.sourceMessageId)
              ? { sourceMessageId: normalizedUnknownText(metaRecord.sourceMessageId) }
              : {}),
            ...(normalizedUnknownText(metaRecord.reasoningTraceId)
              ? { reasoningTraceId: normalizedUnknownText(metaRecord.reasoningTraceId) }
              : {}),
            ...(normalizedUnknownText(metaRecord.replaceStrategy)
              ? { replaceStrategy: normalizedUnknownText(metaRecord.replaceStrategy) as NonNullable<LayoutTreeContent["meta"]>["replaceStrategy"] }
              : {}),
          },
        }
      : {}),
  }
}

function toLayoutTreeStateSnapshot(value: unknown): LayoutTreeStateSnapshot | undefined {
  const record = normalizedUnknownRecord(value)
  if (!record) return undefined

  const interaction = normalizedUnknownRecord(record.interaction)
  const selection = normalizedUnknownRecord(record.selection)
  const view = normalizedUnknownRecord(record.view)
  const activeBlockIds = normalizedUnknownArray(view?.activeBlockIds)?.filter(
    (blockId): blockId is string => typeof blockId === "string" && blockId.trim().length > 0,
  )

  const snapshot: LayoutTreeStateSnapshot = {
    ...(interaction && normalizedUnknownText(interaction.status)
      ? {
          interaction: {
            status: normalizedUnknownText(interaction.status) as NonNullable<LayoutTreeStateSnapshot["interaction"]>["status"],
          },
        }
      : {}),
    ...(selection
      ? {
          selection: {
            ...(typeof selection.required === "boolean" ? { required: selection.required } : {}),
            ...(typeof selection.selectedCandidateOptionId === "string" || selection.selectedCandidateOptionId === null
              ? { selectedCandidateOptionId: selection.selectedCandidateOptionId as string | null }
              : {}),
            ...(typeof selection.selectionLocked === "boolean" ? { selectionLocked: selection.selectionLocked } : {}),
          },
        }
      : {}),
    ...(activeBlockIds && activeBlockIds.length > 0
      ? {
          view: {
            activeBlockIds,
          },
        }
      : {}),
  }

  return Object.keys(snapshot).length > 0 ? snapshot : undefined
}

function toConversationRichPayload(message: ConversationMessageApiModel): ConversationRichPayload | undefined {
  const agUiMarkdown = resolveAgUiMarkdownContent(message)

  if (agUiMarkdown) {
    return {
      kind: "markdown",
      data: {
        markdown: agUiMarkdown,
      },
    }
  }

  const layoutTreeActivity = resolveLayoutTreeActivityContent(message)

  if (layoutTreeActivity) {
    const stateSnapshot = resolveLayoutTreeStateSnapshot(message)
    const payload: ConversationLayoutTreeRichPayload = {
      activity: layoutTreeActivity,
      ...(stateSnapshot ? { stateSnapshot } : {}),
    }

    return {
      kind: "layout_tree",
      data: payload,
    }
  }

  const candidateEvent = findAgUiEvent(message, CANDIDATE_OPTIONS_RENDER_EVENT)

  if (candidateEvent?.value) {
    const value = candidateEvent.value as {
      trace_id?: string
      reasoning_trace_id?: string
      title?: string
      summary?: string
      selected_candidate_option_id?: string
      selection_locked?: boolean
      actions?: Array<{
        type?: string
        label?: string
        input_label?: string
        input_placeholder?: string
        submit_label?: string
      }>
      options?: Array<{
        candidate_option_id?: string
        option_id?: string
        title?: string
        summary?: string
        recommended?: boolean
        fields?: Array<{
          key?: string
          label?: string
          value?: unknown
        }>
        extra?: {
          title?: string
          content?: string
        }
      }>
    }

    const reasoningTraceId = normalizedText(value.reasoning_trace_id) ?? normalizedText(value.trace_id)
    const title = normalizedText(value.title)
    const summary = normalizedText(value.summary)
    const selectedOptionId = normalizedText(value.selected_candidate_option_id)
    const selectionLocked = value.selection_locked === true

    if (!reasoningTraceId || !title) return undefined

    const actions: CandidateOptionAction[] = (value.actions ?? [])
      .map((action) => {
        const type: CandidateOptionAction["type"] | undefined =
          action.type === "confirm" || action.type === "reject" || action.type === "revise" ? action.type : undefined
        const label = normalizedText(action.label)

        if (!type || !label) return null

        return {
          type,
          label,
          ...(normalizedText(action.input_label) ? { inputLabel: normalizedText(action.input_label) } : {}),
          ...(normalizedText(action.input_placeholder)
            ? { inputPlaceholder: normalizedText(action.input_placeholder) }
            : {}),
          ...(normalizedText(action.submit_label) ? { submitLabel: normalizedText(action.submit_label) } : {}),
        }
      })
      .filter((action): action is NonNullable<typeof action> => action !== null)

    if (actions.length === 0) return undefined

    const options = (value.options ?? [])
      .map((option) => {
        const optionId = normalizedText(option.candidate_option_id) ?? normalizedText(option.option_id)
        const optionTitle = normalizedText(option.title)
        const optionSummary = normalizedText(option.summary)

        if (!optionId || !optionTitle) return null

        const fields = (option.fields ?? [])
          .map((field) => {
            const fieldKey = normalizedText(field.key)
            const fieldLabel = normalizedText(field.label)
            const fieldValue = normalizedDisplayValue(field.value)

            if (!fieldKey || !fieldLabel || !fieldValue) return null

            return {
              key: fieldKey,
              label: fieldLabel,
              value: fieldValue,
            }
          })
          .filter((field): field is NonNullable<typeof field> => field !== null)

        if (fields.length === 0) return null

        const extraContent = normalizedText(option.extra?.content)

        return {
          optionId,
          title: optionTitle,
          ...(option.recommended === true ? { recommended: true } : {}),
          ...(optionSummary ? { summary: optionSummary } : {}),
          fields,
          ...(extraContent
            ? {
                extra: {
                  ...(normalizedText(option.extra?.title) ? { title: normalizedText(option.extra?.title) } : {}),
                  content: extraContent,
                },
              }
            : {}),
        }
      })
      .filter((option): option is NonNullable<typeof option> => option !== null)

    if (options.length === 0) return undefined

    return {
      kind: "candidate_options",
      data: {
        reasoningTraceId,
        title,
        ...(summary ? { summary } : {}),
        ...(selectedOptionId ? { selectedOptionId } : {}),
        ...(selectionLocked ? { selectionLocked: true } : {}),
        options,
        actions,
      },
    }
  }

  const clarificationEvent = findAgUiEvent(message, CLARIFICATION_RENDER_EVENT)

  if (clarificationEvent?.value) {
    const value = clarificationEvent.value as {
      clarification_id?: string
      prompt?: string
      selected_value?: string
      free_text?: string
      response_locked?: boolean
      options?: Array<{
        label?: string
        value?: string
      }>
      input_constraints?: {
        required?: boolean
        allow_free_text?: boolean
        free_text_label?: string
        free_text_placeholder?: string
      }
    }

    const prompt =
      normalizedText(value.prompt) ??
      normalizedText(message.rich_payload?.content_summary) ??
      normalizedText(message.rich_payload?.render_fallback?.text) ??
      resolveMessageContent(message)

    const options = (value.options ?? [])
      .map((option) => {
        const label = normalizedText(option.label)
        const optionValue = normalizedText(option.value)

        if (!label || !optionValue) return null

        return {
          label,
          value: optionValue,
        }
      })
      .filter((option): option is NonNullable<typeof option> => option !== null)

    if (!prompt || options.length === 0) return undefined

    const inputConstraints = value.input_constraints

    return {
      kind: "clarification",
      data: {
        ...(normalizedText(value.clarification_id) ? { clarificationId: normalizedText(value.clarification_id) } : {}),
        prompt,
        options,
        ...(inputConstraints
          ? {
              inputConstraints: {
                ...(inputConstraints.required === true ? { required: true } : {}),
                ...(inputConstraints.allow_free_text === true ? { allowFreeText: true } : {}),
                ...(normalizedText(inputConstraints.free_text_label)
                  ? { freeTextLabel: normalizedText(inputConstraints.free_text_label) }
                  : {}),
                ...(normalizedText(inputConstraints.free_text_placeholder)
                  ? { freeTextPlaceholder: normalizedText(inputConstraints.free_text_placeholder) }
                  : {}),
              },
            }
          : {}),
        ...(normalizedText(value.selected_value) ? { selectedValue: normalizedText(value.selected_value) } : {}),
        ...(normalizedText(value.free_text) ? { freeTextValue: normalizedText(value.free_text) } : {}),
        ...(value.response_locked === true ? { responseLocked: true } : {}),
      },
    }
  }

  const thoughtEvent = findAgUiEvent(message, THOUGHT_RENDER_EVENT)

  if (thoughtEvent) {
    const thoughtValue = thoughtEvent.value ?? {}
    const traceId =
      normalizedUnknownText(thoughtValue.reasoning_trace_id) ?? normalizedUnknownText(thoughtValue.trace_id)
    const title = normalizedUnknownText(thoughtValue.title)
    const status = normalizedUnknownText(thoughtValue.status)
    const summary =
      normalizedUnknownText(thoughtValue.summary) ??
      normalizedUnknownText(thoughtValue.content) ??
      normalizedText(message.rich_payload?.content_summary) ??
      normalizedText(message.rich_payload?.render_fallback?.text) ??
      resolveMessageContent(message)

    return {
      kind: "thought",
      data: {
        ...(traceId ? { traceId } : {}),
        ...(title ? { title } : {}),
        ...(status ? { status } : {}),
        summary,
      },
    }
  }

  const resultEvent = findAgUiEvent(message, RESULT_RENDER_EVENT)

  if (resultEvent) {
    const resultValue = resultEvent.value ?? {}
    const title = normalizedUnknownText(resultValue.title)
    const summary =
      normalizedUnknownText(resultValue.summary) ??
      normalizedUnknownText(resultValue.content) ??
      normalizedText(message.rich_payload?.content_summary) ??
      normalizedText(message.rich_payload?.render_fallback?.text) ??
      resolveMessageContent(message)

    return {
      kind: "result",
      data: {
        ...(title ? { title } : {}),
        summary,
        ...(normalizedUnknownText(resultValue.result_id)
          ? { resultId: normalizedUnknownText(resultValue.result_id) }
          : {}),
        ...(normalizedUnknownText(resultValue.source_message)
          ? { sourceMessage: normalizedUnknownText(resultValue.source_message) }
          : {}),
      },
    }
  }

  const genericEvent = findFirstAgUiEvent(message)

  if (!genericEvent) return undefined

  const genericValue = genericEvent.value ?? {}
  const title = normalizedUnknownText(genericValue.title)
  const summary =
    normalizedUnknownText(genericValue.summary) ??
    normalizedUnknownText(genericValue.content) ??
    title ??
    normalizedText(message.rich_payload?.content_summary) ??
    normalizedText(message.rich_payload?.render_fallback?.text) ??
    resolveMessageContent(message)

  return {
    kind: "ag_ui",
    data: {
      eventName: genericEvent.name,
      ...(title ? { title } : {}),
      summary,
      ...(normalizedUnknownRecord(genericEvent.value) ? { data: normalizedUnknownRecord(genericEvent.value) } : {}),
    },
  }
}

function toConversationSummary(conversation: ConversationApiModel): ConversationSummary {
  return {
    conversationId: conversation.conversation_id,
    title: conversation.title,
    displaySummary: normalizedText(conversation.summary) ?? normalizedText(conversation.latest_message_summary),
    updatedAt: conversation.updated_at,
    lastActiveAt: conversation.last_active_at,
    latestMessageSummary: normalizedText(conversation.latest_message_summary),
    tags: conversation.tags,
    status: conversation.status,
    attentionFlag: conversation.interaction_status === "error" ? true : undefined,
    archivedAt: conversation.archived_at ?? undefined,
    expiresAt: conversation.expires_at ?? undefined,
  }
}

function toConversationDetail(conversation: ConversationApiModel): ConversationDetail {
  const activeTurnId = conversation.active_turn_id ?? conversation.active_run_id ?? undefined
  const interactionState =
    conversation.interaction_status ?? (conversation.has_active_run && activeTurnId ? "thinking" : undefined)

  return {
    ...toConversationSummary(conversation),
    createdAt: conversation.created_at,
    interactionState,
    activeTurnId,
    contextSummary: normalizedText(conversation.context?.summary),
  }
}

function resolveInteractionStateFromMessages(
  messages: ConversationMessageSummary[],
  activeTurnId?: string,
): ConversationDetail["interactionState"] | undefined {
  const candidates = [...messages]
    .filter((message) => {
      if (activeTurnId && message.turnId && message.turnId !== activeTurnId) return false
      return message.richPayload?.kind === "layout_tree"
    })
    .reverse()

  for (const message of candidates) {
    const interactionState = message.richPayload?.kind === "layout_tree"
      ? message.richPayload.data.stateSnapshot?.interaction?.status
      : undefined

    if (interactionState) return interactionState
  }

  return undefined
}

function toConversationMessage(
  message: ConversationMessageApiModel,
  options: {
    fallbackCreatedAt?: string
    richPayload?: ConversationRichPayloadApi | null
    agUiSequence?: number
  } = {},
): ConversationMessageSummary {
  const messageRichPayload = message.rich_payload ?? options.richPayload ?? undefined
  const richPayloadMessage =
    messageRichPayload === message.rich_payload ? message : { ...message, rich_payload: messageRichPayload }

  return {
    messageId: message.message_id,
    conversationId: message.conversation_id,
    turnId: message.turn_id ?? undefined,
    parentMessageId: message.parent_message_id ?? undefined,
    clientMessageId: message.client_message_id ?? undefined,
    role: message.role,
    contentType: message.content_type,
    content: resolveMessageContent(richPayloadMessage),
    richPayload: toConversationRichPayload(richPayloadMessage),
    createdAt: normalizedText(message.created_at) ?? options.fallbackCreatedAt ?? "",
    updatedAt: message.updated_at ?? undefined,
    status: message.status,
    agUiSequence: options.agUiSequence,
    agUiEventName: resolveLatestAgUiEventName(richPayloadMessage),
    errorCode: message.error_code ?? undefined,
    errorMessage: message.error_message ?? undefined,
    traceId: message.trace_id ?? undefined,
    correlationId: message.correlation_id ?? undefined,
  }
}

const AG_UI_WIRE_EVENT_TYPES = new Set([
  "RUN_STARTED",
  "RUN_FINISHED",
  "RUN_ERROR",
  "TEXT_MESSAGE_START",
  "TEXT_MESSAGE_CONTENT",
  "TEXT_MESSAGE_END",
  "TEXT_MESSAGE_CHUNK",
  "ACTIVITY_SNAPSHOT",
  "ACTIVITY_DELTA",
  "STATE_SNAPSHOT",
  "STATE_DELTA",
  "CUSTOM",
  "TOOL_CALL_START",
  "TOOL_CALL_ARGS",
  "TOOL_CALL_END",
  "TOOL_CALL_RESULT",
])

function isAgUiWireEventType(value: string | undefined): value is ConversationAgUiEventApi["type"] {
  return typeof value === "string" && AG_UI_WIRE_EVENT_TYPES.has(value)
}

export function mapStatusApiEventToAgUiWireEvent(
  event: ConversationStatusEventApiModel,
): ConversationAgUiEventApi | undefined {
  if (event.payload?.message) return undefined

  const payload = event.payload
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) return undefined

  const wireType =
    typeof payload.type === "string"
      ? payload.type
      : typeof event.event_type === "string"
        ? event.event_type
        : undefined

  if (!isAgUiWireEventType(wireType)) return undefined

  return payload as ConversationAgUiEventApi
}

function toConversationStatusEvent(event: ConversationStatusEventApiModel): ConversationStatusEvent {
  const createdAt = normalizedText(event.created_at) ?? normalizedText(event.occurred_at) ?? ""
  const eventRichPayload = event.payload?.rich_payload ?? event.rich_payload
  const agUiSequence =
    typeof event.payload?.ag_ui_sequence === "number" ? event.payload.ag_ui_sequence : undefined
  const agUiWireEvent = mapStatusApiEventToAgUiWireEvent(event)

  return {
    statusEventId: event.status_event_id,
    conversationId: event.conversation_id,
    turnId: event.turn_id ?? undefined,
    messageId: event.message_id ?? undefined,
    eventType: event.event_type,
    sequence: event.sequence,
    interactionState: event.interaction_status ?? undefined,
    messageStatus: event.message_status ?? undefined,
    message: event.payload?.message
      ? toConversationMessage(event.payload.message, {
          fallbackCreatedAt: createdAt,
          richPayload: eventRichPayload,
          agUiSequence,
        })
      : undefined,
    agUiWireEvent: agUiWireEvent as Record<string, unknown> | undefined,
    activeTurnId: event.payload?.active_turn_id,
    completedTurnId: normalizedText(event.payload?.completed_turn_id),
    createdAt,
  }
}

function toScenarioBinding(binding?: ConversationScenarioBinding): ScenarioBindingApi | undefined {
  if (!binding) return undefined

  const scenarioId = normalizedText(binding.scenarioId)
  const scenarioName = normalizedText(binding.scenarioName)
  const taskType = normalizedText(binding.taskType)

  if (!scenarioId && !scenarioName && !taskType) return undefined

  return {
    scenario_id: scenarioId,
    scenario_name: scenarioName,
    task_type: taskType,
  }
}

function toInitialContext(context?: InitialConversationContext): InitialConversationContextApi | undefined {
  if (!context) return undefined

  const summary = normalizedText(context.summary)
  const keyVariables = context.keyVariables && Object.keys(context.keyVariables).length > 0 ? context.keyVariables : undefined

  if (!summary && !keyVariables) return undefined

  return {
    summary,
    key_variables: keyVariables,
  }
}

function resolveClientMessageId(input: { clientMessageId?: string }): string {
  return normalizedText(input.clientMessageId) ?? createId("client_msg")
}

function resolveIdempotencyKey(input: { idempotencyKey?: string }, fallbackPrefix: string): string {
  return normalizedText(input.idempotencyKey) ?? createId(fallbackPrefix)
}

function toUserMessageRequest(input: UserMessageInput): UserMessageRequestApi {
  return {
    type: "user_message",
    content: input.content.trim(),
    client_message_id: resolveClientMessageId(input),
    parent_message_id: normalizedText(input.parentMessageId),
    idempotency_key: resolveIdempotencyKey(input, "idem_msg"),
  }
}

function toCreateConversationRequest(input: CreateConversationInput): CreateConversationRequestApi {
  return {
    initial_message: toUserMessageRequest(input.initialMessage),
    title: normalizedText(input.title),
    tags: normalizedTags(input.tags),
    scenario_binding: toScenarioBinding(input.scenarioBinding),
    initial_context: toInitialContext(input.initialContext),
    source: "web",
    idempotency_key: resolveIdempotencyKey(input, "idem_conv"),
  }
}

function toMessageRequest(input: CreateConversationMessageInput): CreateConversationMessageRequestApi {
  if (input.type === "user_message") {
    return toUserMessageRequest(input)
  }

  if (input.type === "clarification_response") {
    return {
      type: "clarification_response",
      message_id: normalizedText(input.messageId),
      clarification_id: normalizedText(input.clarificationId),
      selected_value: normalizedText(input.selectedValue),
      free_text: normalizedText(input.freeText),
      client_message_id: resolveClientMessageId(input),
      idempotency_key: resolveIdempotencyKey(input, "idem_clarification"),
    }
  }

  return {
    type: "candidate_selection",
    message_id: normalizedText(input.messageId),
    reasoning_trace_id: input.reasoningTraceId,
    candidate_option_id: input.candidateOptionId,
    selection: input.selection,
    additional_constraints: normalizedText(input.additionalConstraints),
    client_message_id: resolveClientMessageId(input),
    idempotency_key: resolveIdempotencyKey(input, "idem_selection"),
  }
}

function writeHeaders(idempotencyKey?: string): Record<string, string> {
  const headers = jsonHeaders()
  if (idempotencyKey) {
    headers["Idempotency-Key"] = idempotencyKey
  }
  return headers
}

async function listConversationCollection(keyword?: string): Promise<ConversationSummary[]> {
  const query = new URLSearchParams()
  appendIfPresent(query, "limit", DEFAULT_CONVERSATION_LIMIT)
  appendIfPresent(query, "sort", "last_active_desc")
  appendIfPresent(query, "archived", false)

  const normalizedKeyword = normalizedText(keyword)
  if (normalizedKeyword) {
    appendIfPresent(query, "keyword", normalizedKeyword)
  }

  const response = await requestJson<ConversationListResponseApi>(
    buildPath(CONVERSATIONS_PATH, query),
    { method: "GET" },
    translate("conversation.error.listLoadFailed"),
  )

  return response.items.map(toConversationSummary)
}

export async function listConversations(): Promise<ConversationSummary[]> {
  return listConversationCollection()
}

export async function searchConversations(query: string): Promise<ConversationSummary[]> {
  const normalizedKeyword = normalizedText(query)
  if (!normalizedKeyword) return listConversations()
  return listConversationCollection(normalizedKeyword)
}

export async function getConversationDetail(conversationId: string): Promise<ConversationDetail> {
  const query = new URLSearchParams()
  appendIfPresent(query, "include_latest_messages", false)
  appendIfPresent(query, "include_context", true)
  appendIfPresent(query, "include_latest_events", false)

  const detail = await requestJson<ConversationApiModel>(
    buildPath(conversationPath(conversationId), query),
    { method: "GET" },
    translate("conversation.error.detailLoadFailed"),
  )

  return toConversationDetail(detail)
}

export async function getConversationMessages(conversationId: string): Promise<ConversationMessageSummary[]> {
  const query = new URLSearchParams()
  appendIfPresent(query, "limit", DEFAULT_MESSAGE_LIMIT)

  const response = await requestJson<MessageListResponseApi>(
    buildPath(messagesPath(conversationId), query),
    { method: "GET" },
    translate("conversation.error.messagesLoadFailed"),
  )

  return response.items.map((message) => toConversationMessage(message))
}

export async function listConversationEvents(
  conversationId: string,
  options: { cursor?: string | null; limit?: number } = {},
): Promise<ConversationEventListResult> {
  const query = new URLSearchParams()
  appendIfPresent(query, "limit", options.limit ?? 50)
  appendIfPresent(query, "cursor", options.cursor ?? undefined)
  appendIfPresent(query, "include_rich_payload", true)

  const response = await requestJson<EventListResponseApi>(
    buildPath(eventsPath(conversationId), query),
    { method: "GET" },
    translate("conversation.error.eventsLoadFailed"),
  )

  return {
    events: response.items.map(toConversationStatusEvent),
    nextCursor: response.page.next_cursor ?? null,
    hasMore: response.page.has_more,
    latestSequence: response.latest_sequence,
    recommendedPollIntervalMs: response.recommended_poll_interval_ms,
    interactionState: response.interaction_status,
  }
}

export async function createConversation(input: CreateConversationInput): Promise<MessageAcceptedResult> {
  const requestBody = toCreateConversationRequest(input)
  const response = await requestJson<MessageAcceptedResponseApi>(
    CONVERSATIONS_PATH,
    {
      method: "POST",
      headers: writeHeaders(requestBody.idempotency_key),
      body: JSON.stringify(requestBody),
    },
    translate("conversation.error.createFailed"),
  )

  const statusEvent = toConversationStatusEvent(response.status_event)

  return {
    conversation: toConversationDetail(response.conversation),
    message: toConversationMessage(response.message, { fallbackCreatedAt: statusEvent.createdAt }),
    statusEvent,
    nextPollAfterMs: response.next_poll_after_ms,
  }
}

export async function sendMessage(
  conversationId: string,
  input: CreateConversationMessageInput,
): Promise<MessageAcceptedResult> {
  const requestBody = toMessageRequest(input)
  const response = await requestJson<MessageAcceptedResponseApi>(
    messagesPath(conversationId),
    {
      method: "POST",
      headers: writeHeaders(requestBody.idempotency_key),
      body: JSON.stringify(requestBody),
    },
    translate("conversation.error.sendFailed"),
  )

  const statusEvent = toConversationStatusEvent(response.status_event)

  return {
    conversation: toConversationDetail(response.conversation),
    message: toConversationMessage(response.message, { fallbackCreatedAt: statusEvent.createdAt }),
    statusEvent,
    nextPollAfterMs: response.next_poll_after_ms,
  }
}

export async function archiveConversation(conversationId: string, reason?: string): Promise<ConversationDetail> {
  const requestBody: ArchiveConversationRequestApi = {
    reason: normalizedText(reason),
  }

  const response = await requestJson<ConversationApiModel>(
    archivePath(conversationId),
    {
      method: "POST",
      headers: writeHeaders(createId("idem_archive")),
      body: JSON.stringify(requestBody),
    },
    translate("conversation.error.archiveFailed"),
  )

  return toConversationDetail(response)
}

export async function restoreConversation(conversationId: string, reason?: string): Promise<ConversationDetail> {
  const requestBody: ArchiveConversationRequestApi = {
    reason: normalizedText(reason),
  }

  const response = await requestJson<ConversationApiModel>(
    restorePath(conversationId),
    {
      method: "POST",
      headers: writeHeaders(createId("idem_restore")),
      body: JSON.stringify(requestBody),
    },
    translate("conversation.error.restoreFailed"),
  )

  return toConversationDetail(response)
}

export async function copyConversationConfig(
  conversationId: string,
  input: CopyConversationConfigInput = {},
): Promise<ConversationDetail> {
  const requestBody: CopyConversationConfigRequestApi = {
    title: normalizedText(input.title),
    copy_tags: input.copyTags,
    copy_scenario_binding: input.copyScenarioBinding,
    additional_tags: normalizedTags(input.additionalTags),
  }

  const response = await requestJson<ConversationApiModel>(
    copyConfigPath(conversationId),
    {
      method: "POST",
      headers: writeHeaders(createId("idem_copy")),
      body: JSON.stringify(requestBody),
    },
    translate("conversation.error.copyConfigFailed"),
  )

  return toConversationDetail(response)
}

export type {
  ConversationApiModel,
  ConversationMessageApiModel,
  ConversationStatusEventApiModel,
}

export {
  toConversationSummary as mapConversationSummaryRecord,
  toConversationMessage as mapConversationMessageRecord,
  toConversationStatusEvent as mapConversationStatusEventRecord,
}

interface AgUiReplayMessageBuffer {
  messageId: string
  role: ConversationMessageSummary["role"]
  events: ConversationAgUiEventApi[]
  createdAt: string
  updatedAt: string
  status: ConversationMessageSummary["status"]
}

function agUiWireTimestampIso(value?: number): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    return new Date(value).toISOString()
  }

  return new Date().toISOString()
}

function upsertMaterializedMessage(
  messages: ConversationMessageSummary[],
  incoming: ConversationMessageSummary,
): ConversationMessageSummary[] {
  const existingIndex = messages.findIndex((message) => message.messageId === incoming.messageId)
  if (existingIndex < 0) {
    return [...messages, incoming]
  }

  return messages.map((message, index) => (index === existingIndex ? { ...message, ...incoming } : message))
}

export function materializeMessagesFromAgUiWireEvents(
  conversationId: string,
  turnId: string,
  seedMessages: ConversationMessageSummary[],
  wireEvents: ConversationAgUiEventApi[],
): ConversationMessageSummary[] {
  const replayState = {
    activeActivityMessageId: undefined as string | undefined,
    messagesById: {} as Record<string, AgUiReplayMessageBuffer>,
  }

  const appendWireEvent = (
    messageId: string,
    role: ConversationMessageSummary["role"],
    event: ConversationAgUiEventApi,
  ): void => {
    const timestamp = agUiWireTimestampIso(event.timestamp)
    const buffer =
      replayState.messagesById[messageId] ??
      ({
        messageId,
        role,
        events: [],
        createdAt: timestamp,
        updatedAt: timestamp,
        status: "streaming",
      } satisfies AgUiReplayMessageBuffer)

    buffer.events.push(event)
    buffer.updatedAt = timestamp
    replayState.messagesById[messageId] = buffer
  }

  let terminalStatus: ConversationMessageSummary["status"] | undefined

  for (const event of wireEvents) {
    if (event.type === "RUN_FINISHED") terminalStatus = "responded"
    if (event.type === "RUN_ERROR") terminalStatus = "failed"

    switch (event.type) {
      case "TEXT_MESSAGE_START":
      case "TEXT_MESSAGE_CONTENT":
      case "TEXT_MESSAGE_END": {
        const messageId =
          typeof event.messageId === "string" && event.messageId.trim() ? event.messageId : `msg_text_${turnId}`
        const role = event.type === "TEXT_MESSAGE_START" && event.role === "user" ? "user" : "assistant"
        appendWireEvent(messageId, role, event)
        break
      }
      case "ACTIVITY_SNAPSHOT":
      case "ACTIVITY_DELTA": {
        const messageId =
          typeof event.messageId === "string" && event.messageId.trim()
            ? event.messageId
            : `msg_activity_${turnId}`
        replayState.activeActivityMessageId = messageId
        appendWireEvent(messageId, "assistant", event)
        break
      }
      case "STATE_SNAPSHOT":
      case "STATE_DELTA":
      case "CUSTOM": {
        if (replayState.activeActivityMessageId) {
          appendWireEvent(replayState.activeActivityMessageId, "assistant", event)
        }
        break
      }
      default:
        break
    }
  }

  if (terminalStatus) {
    for (const buffer of Object.values(replayState.messagesById)) {
      buffer.status = terminalStatus
    }
  }

  return Object.values(replayState.messagesById)
    .map((buffer) => {
      const richPayload = mapAgUiEventsToRichPayload(buffer.events)
      const textContent = mapAgUiEventsToTextContent(buffer.events).trim()
      const content =
        textContent ||
        (richPayload?.kind === "layout_tree"
          ? translate("conversation.placeholder.richContent")
          : richPayload?.kind === "thought"
            ? richPayload.data.summary
            : richPayload?.kind === "result"
              ? richPayload.data.summary
              : richPayload?.kind === "markdown"
                ? richPayload.data.markdown
                : "")

      return {
        messageId: buffer.messageId,
        conversationId,
        turnId,
        role: buffer.role,
        contentType: richPayload ? ("rich_content" as const) : ("text" as const),
        content,
        richPayload,
        createdAt: buffer.createdAt,
        updatedAt: buffer.updatedAt,
        status: buffer.status,
        agUiEventName: mapAgUiEventsToEventName(buffer.events),
      } satisfies ConversationMessageSummary
    })
    .sort((left, right) => left.createdAt.localeCompare(right.createdAt))
    .reduce((messages, materialized) => upsertMaterializedMessage(messages, materialized), seedMessages)
}

export function mapAgUiEventsToRichPayload(events: ConversationAgUiEventApi[]): ConversationRichPayload | undefined {
  return toConversationRichPayload(createSyntheticAgUiMessage(events))
}

export function mapAgUiEventsToTextContent(events: ConversationAgUiEventApi[]): string {
  return resolveMessageContent(createSyntheticAgUiMessage(events))
}

export function mapAgUiEventsToEventName(events: ConversationAgUiEventApi[]): string | undefined {
  return resolveLatestAgUiEventName(createSyntheticAgUiMessage(events))
}

export function mapAgUiEventsToStateSnapshot(events: ConversationAgUiEventApi[]): LayoutTreeStateSnapshot | undefined {
  return resolveLayoutTreeStateSnapshot(createSyntheticAgUiMessage(events))
}

export function mapConversationDetailRecord(
  conversation: ConversationApiModel,
  messages: ConversationMessageSummary[] = [],
): ConversationDetail {
  const detail = toConversationDetail(conversation)
  const interactionState = resolveInteractionStateFromMessages(messages, detail.activeTurnId)

  if (!interactionState) return detail

  return {
    ...detail,
    interactionState,
  }
}
