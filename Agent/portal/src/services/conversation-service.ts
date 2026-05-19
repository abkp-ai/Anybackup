import { createId } from "@/lib/ids"
import { translate } from "@/i18n/messages"
import { jsonHeaders, requestJson } from "@/services/conversation-api-client"
import {
  mapConversationDetailRecord,
  mapConversationMessageRecord,
  mapConversationStatusEventRecord,
  mapConversationSummaryRecord,
  type ConversationApiModel,
  type ConversationMessageApiModel,
  type ConversationStatusEventApiModel,
} from "@/services/conversation-response-adapter"
import type {
  ConversationDetail,
  ConversationEventListResult,
  ConversationScenarioBinding,
  ConversationSummary,
  CopyConversationConfigInput,
  CreateConversationInput,
  CreateConversationMessageInput,
  InitialConversationContext,
  MessageAcceptedResult,
  UserMessageInput,
} from "@/types/conversation"

interface PageMetaApi {
  next_cursor?: string | null
  has_more: boolean
  limit: number
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

interface CreateConversationRequestApi {
  initial_message: UserMessageRequestApi
  title?: string
  tags?: string[]
  scenario_binding?: ScenarioBindingApi
  initial_context?: InitialConversationContextApi
  source: "web"
  idempotency_key?: string
}

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

function normalizedText(value?: string | null): string | undefined {
  const trimmed = value?.trim()
  return trimmed ? trimmed : undefined
}

function normalizedTags(tags?: string[]): string[] | undefined {
  const nextTags = tags?.map((tag) => tag.trim()).filter(Boolean)
  return nextTags && nextTags.length > 0 ? nextTags : undefined
}

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

function resolveClientMessageId(input: { clientMessageId?: string }): string {
  return normalizedText(input.clientMessageId) ?? createId("client_msg")
}

function resolveIdempotencyKey(input: { idempotencyKey?: string }, fallbackPrefix: string): string {
  return normalizedText(input.idempotencyKey) ?? createId(fallbackPrefix)
}

function writeHeaders(idempotencyKey?: string): Record<string, string> {
  const headers = jsonHeaders()
  if (idempotencyKey) {
    headers["Idempotency-Key"] = idempotencyKey
  }
  return headers
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
  const initialMessage = toUserMessageRequest(input.initialMessage)

  return {
    initial_message: initialMessage,
    title: normalizedText(input.title),
    tags: normalizedTags(input.tags),
    scenario_binding: toScenarioBinding(input.scenarioBinding),
    initial_context: toInitialContext(input.initialContext),
    source: "web",
    idempotency_key: resolveIdempotencyKey({ idempotencyKey: input.idempotencyKey }, "idem_conversation"),
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

async function listConversationCollection(keyword?: string): Promise<ConversationSummary[]> {
  const query = new URLSearchParams()
  appendIfPresent(query, "limit", DEFAULT_CONVERSATION_LIMIT)
  appendIfPresent(query, "sort", "last_active_desc")
  appendIfPresent(query, "archived", false)
  appendIfPresent(query, "keyword", normalizedText(keyword))

  const response = await requestJson<ConversationListResponseApi>(
    buildPath(CONVERSATIONS_PATH, query),
    { method: "GET" },
    translate("conversation.error.listLoadFailed"),
  )

  return response.items.map(mapConversationSummaryRecord)
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

  return mapConversationDetailRecord(detail)
}

export async function getConversationMessages(conversationId: string) {
  const query = new URLSearchParams()
  appendIfPresent(query, "limit", DEFAULT_MESSAGE_LIMIT)

  const response = await requestJson<MessageListResponseApi>(
    buildPath(messagesPath(conversationId), query),
    { method: "GET" },
    translate("conversation.error.messagesLoadFailed"),
  )

  return response.items.map((message) => mapConversationMessageRecord(message))
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
    events: response.items.map(mapConversationStatusEventRecord),
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

  const statusEvent = mapConversationStatusEventRecord(response.status_event)

  return {
    conversation: mapConversationDetailRecord(response.conversation),
    message: mapConversationMessageRecord(response.message, { fallbackCreatedAt: statusEvent.createdAt }),
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

  const statusEvent = mapConversationStatusEventRecord(response.status_event)

  return {
    conversation: mapConversationDetailRecord(response.conversation),
    message: mapConversationMessageRecord(response.message, { fallbackCreatedAt: statusEvent.createdAt }),
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

  return mapConversationDetailRecord(response)
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

  return mapConversationDetailRecord(response)
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

  return mapConversationDetailRecord(response)
}
