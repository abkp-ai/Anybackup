import { create } from "zustand"
import { createId } from "@/lib/ids"
import { translate } from "@/i18n/messages"
import {
  conversationDraftKeyForConversation,
  conversationDraftKeyForLocalDraft,
  readConversationDraft,
  readConversationWorkspaceState,
  removeConversationDraft,
  writeConversationDraft,
  writeConversationWorkspaceState,
} from "@/lib/conversation-draft"
import {
  createConversation,
  getConversationDetail,
  getConversationMessages,
  listConversationEvents,
  listConversations,
  searchConversations,
  sendMessage,
} from "@/services/conversation-service"
import { startConversationRun } from "@/services/conversation-run-service"
import {
  mapAgUiEventsToEventName,
  mapAgUiEventsToRichPayload,
  mapAgUiEventsToStateSnapshot,
  mapAgUiEventsToTextContent,
  type ConversationAgUiEventApi,
} from "@/services/conversation-response-adapter"
import { ServiceError } from "@/types/auth"
import type {
  CandidateSelectionInput,
  ClarificationResponseInput,
  ConversationDetail,
  ConversationMessageSummary,
  ConversationRichPayload,
  ConversationRunInput,
  ConversationSummary,
  ConversationWorkspaceSelection,
  ConversationWorkspaceState,
  CreateConversationMessageInput,
  LocalDraftWorkspace,
  MessageAcceptedResult,
  UserMessageInput,
} from "@/types/conversation"
import {
  derivePendingTurnState,
  mergeConversationStatusEvent,
  type PendingTurnState,
} from "@/store/conversation-runtime"

interface ConversationState {
  bootstrapped: boolean
  listLoading: boolean
  conversationLoading: boolean
  query: string
  error: string | null
  conversations: ConversationSummary[]
  selectedWorkspace: ConversationWorkspaceSelection | null
  localDraftWorkspace: LocalDraftWorkspace | null
  detailsByConversationId: Record<string, ConversationDetail>
  messagesByConversationId: Record<string, ConversationMessageSummary[]>
  draftsByKey: Record<string, string>
  pendingTurnByConversationId: Record<string, PendingTurnState>
  pendingTurnStartedAtMsByConversationId: Record<string, number>
  nextPollAfterMsByConversationId: Record<string, number>
  eventCursorByConversationId: Record<string, string | null>
  latestEventSequenceByConversationId: Record<string, number>
  appliedStatusEventIdsByConversationId: Record<string, Record<string, true>>
  submittingWorkspaceKey: string | null
}

interface ConversationActions {
  hydrate: () => Promise<void>
  activateLocalDraftWorkspace: () => void
  selectConversation: (conversationId: string) => Promise<void>
  setSearchQuery: (query: string) => Promise<void>
  setDraft: (value: string) => void
  submitComposerMessage: () => Promise<void>
  submitCandidateSelection: (input: CandidateSelectionInput) => Promise<void>
  submitClarificationResponse: (input: ClarificationResponseInput) => Promise<void>
  submitLayoutTreeUserMessage: (input: UserMessageInput) => Promise<void>
  showInteractionError: (message: string) => void
  clearError: () => void
}

type ConversationStore = ConversationState & ConversationActions

interface RunMessageBuffer {
  messageId: string
  role: "assistant" | "user"
  events: ConversationAgUiEventApi[]
  createdAt: string
  updatedAt: string
  status: ConversationMessageSummary["status"]
}

interface ConversationRunBuffer {
  runId: string
  activeActivityMessageId?: string
  messagesById: Record<string, RunMessageBuffer>
}

const persistedWorkspaceState = readConversationWorkspaceState()
const conversationRunAbortControllers = new Map<string, AbortController>()
const conversationRunBuffers = new Map<string, ConversationRunBuffer>()
const conversationRunReconnectAttempts = new Map<string, number>()
const MAX_RUN_RECOVERY_ATTEMPTS = 2

function toMessage(error: unknown): string {
  if (error instanceof ServiceError) return error.message
  if (error instanceof Error && error.message.trim()) return error.message
  return translate("conversation.serviceUnavailable")
}

function createLocalDraftWorkspace(seedDraft = ""): LocalDraftWorkspace {
  const now = new Date().toISOString()
  return {
    localDraftId: createId("local_draft"),
    title: translate("conversation.newConversationTitle"),
    draft: seedDraft,
    createdAt: now,
    updatedAt: now,
  }
}

function persistWorkspaceState(state: ConversationWorkspaceState): void {
  writeConversationWorkspaceState(state)
}

function loadDraftForSelection(
  selection: ConversationWorkspaceSelection | null,
  localDraftWorkspace: LocalDraftWorkspace | null,
  draftsByKey: Record<string, string>,
): Record<string, string> {
  if (!selection) return draftsByKey

  const draftKey =
    selection.kind === "conversation"
      ? conversationDraftKeyForConversation(selection.conversationId)
      : localDraftWorkspace
        ? conversationDraftKeyForLocalDraft(localDraftWorkspace.localDraftId)
        : null

  if (!draftKey || draftKey in draftsByKey) return draftsByKey

  return {
    ...draftsByKey,
    [draftKey]: readConversationDraft(draftKey),
  }
}

function workspaceRequestKey(selection: ConversationWorkspaceSelection): string {
  return selection.kind === "conversation"
    ? `conversation:${selection.conversationId}`
    : `local:${selection.localDraftId}`
}

function omitRecordKey<T>(record: Record<string, T>, key: string): Record<string, T> {
  if (!(key in record)) return record

  const { [key]: _removed, ...rest } = record
  return rest
}

function replaceConversation(
  conversations: ConversationSummary[],
  conversation: ConversationSummary,
): ConversationSummary[] {
  return [conversation, ...conversations.filter((item) => item.conversationId !== conversation.conversationId)]
}

function upsertMessage(
  messages: ConversationMessageSummary[],
  incoming: ConversationMessageSummary,
): ConversationMessageSummary[] {
  const existingIndex = messages.findIndex((message) => message.messageId === incoming.messageId)
  if (existingIndex < 0) {
    return [...messages, incoming]
  }

  return messages.map((message, index) =>
    index === existingIndex
      ? {
          ...message,
          ...incoming,
        }
      : message,
  )
}

function normalizeMessageTimestamp(value?: number): string {
  if (typeof value === "number" && Number.isFinite(value)) {
    return new Date(value).toISOString()
  }

  return new Date().toISOString()
}

function toTimestampMs(value?: string): number | undefined {
  if (!value) return undefined
  const timestamp = Date.parse(value)
  return Number.isFinite(timestamp) ? timestamp : undefined
}

function resolvePendingTurnStartedAtMsFromMessages(
  messages: ConversationMessageSummary[],
  turnId?: string,
): number | undefined {
  if (!turnId) return undefined

  const turnMessages = messages.filter((message) => message.turnId === turnId)
  const userTurnMessages = turnMessages.filter((message) => message.role === "user")
  const candidateMessages = userTurnMessages.length > 0 ? userTurnMessages : turnMessages

  const timestamps = candidateMessages
    .map((message) => toTimestampMs(message.createdAt))
    .filter((timestamp): timestamp is number => typeof timestamp === "number")

  if (timestamps.length === 0) return undefined
  return Math.min(...timestamps)
}

function shouldClearActiveTurnId(interactionState?: ConversationDetail["interactionState"]): boolean {
  return interactionState === "idle" || interactionState === "completed" || interactionState === "error"
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
    const interactionState =
      message.richPayload?.kind === "layout_tree" ? message.richPayload.data.stateSnapshot?.interaction?.status : undefined

    if (interactionState) return interactionState
  }

  return undefined
}

function reconcileDetailWithMessages(detail: ConversationDetail, messages: ConversationMessageSummary[]): ConversationDetail {
  const interactionState = resolveInteractionStateFromMessages(messages, detail.activeTurnId) ?? detail.interactionState

  return {
    ...detail,
    interactionState,
    activeTurnId: shouldClearActiveTurnId(interactionState) ? undefined : detail.activeTurnId,
  }
}

function pendingTurnStartedAtMsByConversation(
  current: ConversationState,
  conversationId: string,
  pendingTurn: PendingTurnState,
  restoredStartedAtMs?: number,
): Record<string, number> {
  const startedAtByConversation = current.pendingTurnStartedAtMsByConversationId ?? {}

  if (pendingTurn.state !== "thinking") {
    return omitRecordKey(startedAtByConversation, conversationId)
  }

  const previousPendingTurn = current.pendingTurnByConversationId[conversationId]
  const previousStartedAtMs = startedAtByConversation[conversationId]

  if (
    previousPendingTurn?.state === "thinking" &&
    previousPendingTurn.turnId === pendingTurn.turnId &&
    previousPendingTurn.sourceMessageId === pendingTurn.sourceMessageId &&
    typeof previousStartedAtMs === "number"
  ) {
    return startedAtByConversation
  }

  return {
    ...startedAtByConversation,
    [conversationId]: restoredStartedAtMs ?? Date.now(),
  }
}

function shouldStreamPendingTurn(pendingTurn: PendingTurnState | undefined): boolean {
  return pendingTurn?.state === "thinking"
}

function resolveAcceptedActiveTurnId(accepted: MessageAcceptedResult): string | undefined {
  if (accepted.statusEvent.activeTurnId === null) return undefined

  return (
    accepted.statusEvent.activeTurnId ??
    accepted.conversation.activeTurnId ??
    accepted.statusEvent.turnId ??
    accepted.message.turnId
  )
}

function resolveAcceptedInteractionState(
  accepted: MessageAcceptedResult,
  activeTurnId?: string,
): ConversationDetail["interactionState"] | undefined {
  return accepted.statusEvent.interactionState ?? accepted.conversation.interactionState ?? (activeTurnId ? "thinking" : undefined)
}

function buildRunRequestState(messages: ConversationMessageSummary[], activeTurnId?: string): Record<string, unknown> | undefined {
  const candidate = [...messages]
    .filter((message) => {
      if (activeTurnId && message.turnId && message.turnId !== activeTurnId) return false
      return message.richPayload?.kind === "layout_tree"
    })
    .reverse()
    .find((message) => message.richPayload?.kind === "layout_tree" && message.richPayload.data.stateSnapshot)

  if (!candidate?.richPayload || candidate.richPayload.kind !== "layout_tree" || !candidate.richPayload.data.stateSnapshot) {
    return undefined
  }

  return JSON.parse(JSON.stringify(candidate.richPayload.data.stateSnapshot)) as Record<string, unknown>
}

function buildRunRequestMessages(messages: ConversationMessageSummary[]): ConversationRunInput["messages"] {
  return messages
    .filter((message) => message.role === "user" || message.role === "assistant")
    .map((message): ConversationRunInput["messages"][number] => ({
      role: message.role === "assistant" ? "assistant" : "user",
      content: message.content.trim(),
    }))
    .filter((message) => message.content.length > 0)
}

function runIdFromEvent(event: ConversationAgUiEventApi): string | undefined {
  if (event.type === "RUN_STARTED" || event.type === "RUN_FINISHED" || event.type === "RUN_ERROR") {
    return event.runId
  }

  return undefined
}

function ensureRunBuffer(conversationId: string, runId: string): ConversationRunBuffer {
  const current = conversationRunBuffers.get(conversationId)
  if (current?.runId === runId) return current

  const next: ConversationRunBuffer = {
    runId,
    messagesById: {},
  }
  conversationRunBuffers.set(conversationId, next)
  return next
}

function ensureRunMessageBuffer(
  runBuffer: ConversationRunBuffer,
  messageId: string,
  createdAt: string,
  role: "assistant" | "user" = "assistant",
): RunMessageBuffer {
  const existing = runBuffer.messagesById[messageId]
  if (existing) return existing

  const next: RunMessageBuffer = {
    messageId,
    role,
    events: [],
    createdAt,
    updatedAt: createdAt,
    status: "streaming",
  }
  runBuffer.messagesById[messageId] = next
  return next
}

function contentSummaryFromRichPayload(richPayload?: ConversationRichPayload): string {
  if (!richPayload) return ""

  switch (richPayload.kind) {
    case "markdown":
      return richPayload.data.markdown
    case "layout_tree":
      return translate("conversation.placeholder.richContent")
    case "candidate_options":
      return richPayload.data.summary ?? richPayload.data.title
    case "clarification":
      return richPayload.data.prompt
    case "thought":
      return richPayload.data.summary
    case "result":
      return richPayload.data.summary
    case "ag_ui":
      return richPayload.data.summary
    default:
      return ""
  }
}

function shouldIgnoreSyntheticTextContent(content: string): boolean {
  const placeholders = [
    translate("conversation.placeholder.richContent"),
    translate("conversation.placeholder.clarification"),
    translate("conversation.placeholder.status"),
  ]

  return placeholders.includes(content)
}

function toRuntimeMessageContent(events: ConversationAgUiEventApi[], richPayload?: ConversationRichPayload): string {
  const textContent = mapAgUiEventsToTextContent(events).trim()
  if (textContent && !shouldIgnoreSyntheticTextContent(textContent)) {
    return textContent
  }

  return contentSummaryFromRichPayload(richPayload)
}

function toRuntimeMessageContentType(
  richPayload: ConversationRichPayload | undefined,
): ConversationMessageSummary["contentType"] {
  if (richPayload?.kind === "clarification") return "clarification"
  if (richPayload) return "rich_content"
  return "text"
}

function buildRuntimeMessageSummary(
  conversationId: string,
  turnId: string,
  messageBuffer: RunMessageBuffer,
): ConversationMessageSummary {
  const richPayload = mapAgUiEventsToRichPayload(messageBuffer.events)

  return {
    messageId: messageBuffer.messageId,
    conversationId,
    turnId,
    role: messageBuffer.role,
    contentType: toRuntimeMessageContentType(richPayload),
    content: toRuntimeMessageContent(messageBuffer.events, richPayload),
    richPayload,
    createdAt: messageBuffer.createdAt,
    updatedAt: messageBuffer.updatedAt,
    status: messageBuffer.status,
    agUiEventName: mapAgUiEventsToEventName(messageBuffer.events),
  }
}

function appendRunEvent(
  conversationId: string,
  runId: string,
  event: ConversationAgUiEventApi,
): ConversationMessageSummary[] {
  const runBuffer = ensureRunBuffer(conversationId, runId)
  const timestamp = normalizeMessageTimestamp(event.timestamp)

  const appendEventToBuffer = (messageId: string, role: "assistant" | "user" = "assistant"): void => {
    const messageBuffer = ensureRunMessageBuffer(runBuffer, messageId, timestamp, role)
    messageBuffer.events.push(event)
    messageBuffer.updatedAt = timestamp
  }

  switch (event.type) {
    case "TEXT_MESSAGE_START":
    case "TEXT_MESSAGE_CONTENT":
    case "TEXT_MESSAGE_END": {
      const messageId = typeof event.messageId === "string" && event.messageId.trim() ? event.messageId : `msg_text_${runId}`
      const role = event.type === "TEXT_MESSAGE_START" && event.role === "user" ? "user" : "assistant"
      appendEventToBuffer(messageId, role)
      break
    }
    case "ACTIVITY_SNAPSHOT":
    case "ACTIVITY_DELTA": {
      const messageId =
        typeof event.messageId === "string" && event.messageId.trim() ? event.messageId : `msg_activity_${runId}`
      runBuffer.activeActivityMessageId = messageId
      appendEventToBuffer(messageId)
      break
    }
    case "STATE_SNAPSHOT":
    case "STATE_DELTA":
    case "CUSTOM": {
      const messageId = runBuffer.activeActivityMessageId
      if (messageId) {
        appendEventToBuffer(messageId)
      }
      break
    }
    default:
      break
  }

  return Object.values(runBuffer.messagesById)
    .map((messageBuffer) => buildRuntimeMessageSummary(conversationId, runId, messageBuffer))
    .sort((left, right) => left.createdAt.localeCompare(right.createdAt))
}

function markRunMessagesStatus(
  conversationId: string,
  status: ConversationMessageSummary["status"],
): ConversationMessageSummary[] {
  const runBuffer = conversationRunBuffers.get(conversationId)
  if (!runBuffer) return []

  for (const messageBuffer of Object.values(runBuffer.messagesById)) {
    messageBuffer.status = status
    messageBuffer.updatedAt = new Date().toISOString()
  }

  return Object.values(runBuffer.messagesById)
    .map((messageBuffer) => buildRuntimeMessageSummary(conversationId, runBuffer.runId, messageBuffer))
    .sort((left, right) => left.createdAt.localeCompare(right.createdAt))
}

function stopConversationRun(conversationId?: string | null, clearBuffers = true): void {
  if (!conversationId) return

  const controller = conversationRunAbortControllers.get(conversationId)
  if (controller) {
    controller.abort()
    conversationRunAbortControllers.delete(conversationId)
  }

  if (clearBuffers) {
    conversationRunBuffers.delete(conversationId)
  }
}

async function loadConversationPayload(conversationId: string): Promise<{
  detail: ConversationDetail
  messages: ConversationMessageSummary[]
}> {
  const [detail, messages] = await Promise.all([getConversationDetail(conversationId), getConversationMessages(conversationId)])

  return {
    detail: reconcileDetailWithMessages(detail, messages),
    messages,
  }
}

export const useConversationStore = create<ConversationStore>((set, get) => {
  async function recoverConversationAfterDisconnect(conversationId: string): Promise<void> {
    if (!conversationRunReconnectAttempts.has(conversationId)) {
      conversationRunReconnectAttempts.set(conversationId, 0)
    }

    const currentAttempt = (conversationRunReconnectAttempts.get(conversationId) ?? 0) + 1
    conversationRunReconnectAttempts.set(conversationId, currentAttempt)

    if (currentAttempt > MAX_RUN_RECOVERY_ATTEMPTS) {
      set((current) => ({
        error: translate("conversation.serviceUnavailable"),
        pendingTurnByConversationId: {
          ...current.pendingTurnByConversationId,
          [conversationId]: {
            state: "error",
            ...(current.pendingTurnByConversationId[conversationId]?.turnId
              ? { turnId: current.pendingTurnByConversationId[conversationId].turnId }
              : {}),
          },
        },
        pendingTurnStartedAtMsByConversationId: omitRecordKey(
          current.pendingTurnStartedAtMsByConversationId ?? {},
          conversationId,
        ),
      }))
      return
    }

    try {
      const { detail, messages } = await loadConversationPayload(conversationId)

      let recoveredMessages = messages
      let recoveredDetail = detail
      let nextCursor: string | null = get().eventCursorByConversationId[conversationId] ?? null
      let latestSequence = get().latestEventSequenceByConversationId[conversationId] ?? 0

      try {
        const eventsResult = await listConversationEvents(conversationId, { cursor: nextCursor })
        recoveredMessages = eventsResult.events.reduce(
          (currentMessages, event) => mergeConversationStatusEvent(currentMessages, event),
          recoveredMessages,
        )
        recoveredDetail = reconcileDetailWithMessages(
          {
            ...recoveredDetail,
            interactionState: eventsResult.interactionState ?? recoveredDetail.interactionState,
          },
          recoveredMessages,
        )
        nextCursor = eventsResult.nextCursor ?? null
        latestSequence = eventsResult.latestSequence
      } catch {
        // Recovery still falls back to latest detail + messages when event replay is unavailable.
      }

      const pendingTurn = derivePendingTurnState(recoveredDetail, recoveredMessages, recoveredDetail.interactionState)
      const restoredStartedAtMs = resolvePendingTurnStartedAtMsFromMessages(
        recoveredMessages,
        pendingTurn.turnId ?? recoveredDetail.activeTurnId,
      )

      conversationRunBuffers.delete(conversationId)

      set((current) => ({
        detailsByConversationId: {
          ...current.detailsByConversationId,
          [conversationId]: recoveredDetail,
        },
        messagesByConversationId: {
          ...current.messagesByConversationId,
          [conversationId]: recoveredMessages,
        },
        pendingTurnByConversationId: {
          ...current.pendingTurnByConversationId,
          [conversationId]: pendingTurn,
        },
        pendingTurnStartedAtMsByConversationId: pendingTurnStartedAtMsByConversation(
          current,
          conversationId,
          pendingTurn,
          restoredStartedAtMs,
        ),
        eventCursorByConversationId: {
          ...current.eventCursorByConversationId,
          [conversationId]: nextCursor,
        },
        latestEventSequenceByConversationId: {
          ...current.latestEventSequenceByConversationId,
          [conversationId]: latestSequence,
        },
        error: null,
      }))

      const selectedWorkspace = get().selectedWorkspace
      if (
        selectedWorkspace?.kind === "conversation" &&
        selectedWorkspace.conversationId === conversationId &&
        shouldStreamPendingTurn(pendingTurn)
      ) {
        await startRealtimeRun(conversationId, recoveredDetail, recoveredMessages)
      }
    } catch (error) {
      set({ error: toMessage(error) })
    }
  }

  function applyRunEvent(conversationId: string, event: ConversationAgUiEventApi): void {
    conversationRunReconnectAttempts.set(conversationId, 0)

    set((current) => {
      const currentDetail = current.detailsByConversationId[conversationId]
      const currentMessages = current.messagesByConversationId[conversationId] ?? []
      if (!currentDetail) return current

      let nextDetail = currentDetail
      let nextMessages = currentMessages
      let pendingError = current.error

      const applyRuntimeMessages = (status?: ConversationMessageSummary["status"]): void => {
        const runtimeMessages =
          status !== undefined
            ? markRunMessagesStatus(conversationId, status)
            : appendRunEvent(
                conversationId,
                currentDetail.activeTurnId ?? runIdFromEvent(event) ?? createId("turn"),
                event,
              )

        nextMessages = runtimeMessages.reduce(
          (messages, runtimeMessage) => upsertMessage(messages, runtimeMessage),
          nextMessages,
        )
      }

      const stateSnapshot = mapAgUiEventsToStateSnapshot([event])
      const stateInteraction = stateSnapshot?.interaction?.status

      switch (event.type) {
        case "RUN_STARTED":
          nextDetail = {
            ...nextDetail,
            interactionState: "thinking",
            activeTurnId: event.runId ?? nextDetail.activeTurnId,
          }
          break
        case "RUN_FINISHED":
          applyRuntimeMessages("responded")
          nextDetail = {
            ...nextDetail,
            interactionState: "completed",
            activeTurnId: undefined,
          }
          break
        case "RUN_ERROR":
          applyRuntimeMessages("failed")
          nextDetail = {
            ...nextDetail,
            interactionState: "error",
            activeTurnId: undefined,
          }
          pendingError =
            (typeof event.error?.message === "string" && event.error.message.trim()) ||
            translate("conversation.serviceUnavailable")
          break
        case "ACTIVITY_SNAPSHOT":
        case "ACTIVITY_DELTA":
        case "TEXT_MESSAGE_START":
        case "TEXT_MESSAGE_CONTENT":
        case "TEXT_MESSAGE_END":
        case "CUSTOM":
          applyRuntimeMessages()
          break
        case "STATE_SNAPSHOT":
        case "STATE_DELTA":
          applyRuntimeMessages()
          if (stateInteraction) {
            nextDetail = {
              ...nextDetail,
              interactionState: stateInteraction,
              activeTurnId: shouldClearActiveTurnId(stateInteraction)
                ? undefined
                : nextDetail.activeTurnId ?? currentDetail.activeTurnId,
            }
          }
          break
        default:
          break
      }

      nextDetail = reconcileDetailWithMessages(nextDetail, nextMessages)

      const pendingTurn = derivePendingTurnState(nextDetail, nextMessages, nextDetail.interactionState)

      return {
        ...current,
        detailsByConversationId: {
          ...current.detailsByConversationId,
          [conversationId]: nextDetail,
        },
        messagesByConversationId: {
          ...current.messagesByConversationId,
          [conversationId]: nextMessages,
        },
        conversations: replaceConversation(current.conversations, nextDetail),
        pendingTurnByConversationId: {
          ...current.pendingTurnByConversationId,
          [conversationId]: pendingTurn,
        },
        pendingTurnStartedAtMsByConversationId: pendingTurnStartedAtMsByConversation(
          current,
          conversationId,
          pendingTurn,
        ),
        error: pendingError,
      }
    })
  }

  async function startRealtimeRun(
    conversationId: string,
    detail: ConversationDetail,
    messages: ConversationMessageSummary[],
  ): Promise<void> {
    const pendingTurn = derivePendingTurnState(detail, messages, detail.interactionState)
    const effectiveRunId = detail.activeTurnId ?? (
      messages.length > 0 && messages[messages.length - 1].role === "user"
        ? messages[messages.length - 1].turnId
        : undefined
    )
    const shouldStartRun = shouldStreamPendingTurn(pendingTurn) || (
      typeof effectiveRunId === "string" && effectiveRunId
    )
    if (!shouldStartRun) return
    const selectedWorkspace = get().selectedWorkspace
    if (selectedWorkspace?.kind !== "conversation" || selectedWorkspace.conversationId !== conversationId) {
      return
    }

    stopConversationRun(conversationId)
    conversationRunReconnectAttempts.set(conversationId, 0)

    const runInput: ConversationRunInput = {
      threadId: conversationId,
      runId: effectiveRunId!,
      messages: buildRunRequestMessages(messages),
      state: buildRunRequestState(messages, detail.activeTurnId),
    }

    const abortController = new AbortController()
    conversationRunAbortControllers.set(conversationId, abortController)

    let receivedTerminalEvent = false

    void startConversationRun(
      runInput,
      {
        onEvent: (event) => {
          if (event.type === "RUN_FINISHED" || event.type === "RUN_ERROR") {
            receivedTerminalEvent = true
          }
          applyRunEvent(conversationId, event)
        },
      },
      abortController.signal,
    )
      .then(async () => {
        conversationRunAbortControllers.delete(conversationId)
        if (abortController.signal.aborted) return
        if (receivedTerminalEvent) {
          conversationRunBuffers.delete(conversationId)
          return
        }
        await recoverConversationAfterDisconnect(conversationId)
      })
      .catch(async (error) => {
        conversationRunAbortControllers.delete(conversationId)
        if (abortController.signal.aborted) return

        set({ error: toMessage(error) })
        await recoverConversationAfterDisconnect(conversationId)
      })
  }

  function applyAcceptedResponse(accepted: MessageAcceptedResult): PendingTurnState {
    const conversationId = accepted.conversation.conversationId
    const nextMessages = upsertMessage(get().messagesByConversationId[conversationId] ?? [], accepted.message)
    const activeTurnId = resolveAcceptedActiveTurnId(accepted)
    const interactionState = resolveAcceptedInteractionState(accepted, activeTurnId)
    const nextConversation = reconcileDetailWithMessages(
      {
        ...accepted.conversation,
        interactionState,
        activeTurnId,
      },
      nextMessages,
    )
    const pendingTurn = derivePendingTurnState(
      nextConversation,
      nextMessages,
      interactionState ?? nextConversation.interactionState,
    )

    set((current) => ({
      detailsByConversationId: {
        ...current.detailsByConversationId,
        [conversationId]: nextConversation,
      },
      messagesByConversationId: {
        ...current.messagesByConversationId,
        [conversationId]: nextMessages,
      },
      conversations: replaceConversation(current.conversations, nextConversation),
      pendingTurnByConversationId: {
        ...current.pendingTurnByConversationId,
        [conversationId]: pendingTurn,
      },
      pendingTurnStartedAtMsByConversationId: pendingTurnStartedAtMsByConversation(
        current,
        conversationId,
        pendingTurn,
      ),
      nextPollAfterMsByConversationId: {
        ...current.nextPollAfterMsByConversationId,
        [conversationId]: 0,
      },
      latestEventSequenceByConversationId: {
        ...current.latestEventSequenceByConversationId,
        [conversationId]: Math.max(
          current.latestEventSequenceByConversationId[conversationId] ?? 0,
          accepted.statusEvent.sequence,
        ),
      },
      appliedStatusEventIdsByConversationId: {
        ...current.appliedStatusEventIdsByConversationId,
        [conversationId]: {
          ...(current.appliedStatusEventIdsByConversationId[conversationId] ?? {}),
          [accepted.statusEvent.statusEventId]: true,
        },
      },
    }))

    return pendingTurn
  }

  return {
    bootstrapped: false,
    listLoading: false,
    conversationLoading: false,
    query: "",
    error: null,
    conversations: [],
    selectedWorkspace: persistedWorkspaceState.selectedWorkspace,
    localDraftWorkspace: persistedWorkspaceState.localDraftWorkspace,
    detailsByConversationId: {},
    messagesByConversationId: {},
    draftsByKey: loadDraftForSelection(
      persistedWorkspaceState.selectedWorkspace,
      persistedWorkspaceState.localDraftWorkspace,
      {},
    ),
    pendingTurnByConversationId: {},
    pendingTurnStartedAtMsByConversationId: {},
    nextPollAfterMsByConversationId: {},
    eventCursorByConversationId: {},
    latestEventSequenceByConversationId: {},
    appliedStatusEventIdsByConversationId: {},
    submittingWorkspaceKey: null,

    hydrate: async () => {
      set({ listLoading: true, error: null })

      try {
        const conversations = await listConversations()
        const state = get()
        const previouslySelectedConversationId =
          state.selectedWorkspace?.kind === "conversation" ? state.selectedWorkspace.conversationId : undefined

        let localDraftWorkspace = state.localDraftWorkspace
        let selectedWorkspace = state.selectedWorkspace
        const selectedConversationId =
          selectedWorkspace?.kind === "conversation" ? selectedWorkspace.conversationId : null

        if (selectedConversationId && !conversations.some((conversation) => conversation.conversationId === selectedConversationId)) {
          selectedWorkspace = null
        }

        if (selectedWorkspace?.kind === "localDraft") {
          if (!localDraftWorkspace || localDraftWorkspace.localDraftId !== selectedWorkspace.localDraftId) {
            localDraftWorkspace = createLocalDraftWorkspace()
            selectedWorkspace = {
              kind: "localDraft",
              localDraftId: localDraftWorkspace.localDraftId,
            }
          }
        }

        if (!selectedWorkspace) {
          localDraftWorkspace = localDraftWorkspace ?? createLocalDraftWorkspace()
          selectedWorkspace = {
            kind: "localDraft",
            localDraftId: localDraftWorkspace.localDraftId,
          }
        }

        const resolvedSelectedWorkspace = selectedWorkspace as ConversationWorkspaceSelection
        const draftsByKey = loadDraftForSelection(resolvedSelectedWorkspace, localDraftWorkspace, state.draftsByKey)

        if (
          previouslySelectedConversationId &&
          (resolvedSelectedWorkspace.kind !== "conversation" ||
            resolvedSelectedWorkspace.conversationId !== previouslySelectedConversationId)
        ) {
          stopConversationRun(previouslySelectedConversationId)
        }

        set({
          conversations,
          selectedWorkspace: resolvedSelectedWorkspace,
          localDraftWorkspace,
          draftsByKey,
          listLoading: false,
          bootstrapped: true,
        })

        persistWorkspaceState({ selectedWorkspace: resolvedSelectedWorkspace, localDraftWorkspace })

        if (resolvedSelectedWorkspace.kind === "conversation") {
          set({ conversationLoading: true })
          const { detail, messages } = await loadConversationPayload(resolvedSelectedWorkspace.conversationId)
          const pendingTurn = derivePendingTurnState(detail, messages, detail.interactionState)
          const restoredStartedAtMs = resolvePendingTurnStartedAtMsFromMessages(
            messages,
            pendingTurn.turnId ?? detail.activeTurnId,
          )

          set((current) => ({
            conversationLoading: false,
            detailsByConversationId: {
              ...current.detailsByConversationId,
              [detail.conversationId]: detail,
            },
            messagesByConversationId: {
              ...current.messagesByConversationId,
              [detail.conversationId]: messages,
            },
            pendingTurnByConversationId: {
              ...current.pendingTurnByConversationId,
              [detail.conversationId]: pendingTurn,
            },
            pendingTurnStartedAtMsByConversationId: pendingTurnStartedAtMsByConversation(
              current,
              detail.conversationId,
              pendingTurn,
              restoredStartedAtMs,
            ),
          }))

          await startRealtimeRun(detail.conversationId, detail, messages)
        }
      } catch (error) {
        const localDraftWorkspace = get().localDraftWorkspace ?? createLocalDraftWorkspace()
        const currentSelection = get().selectedWorkspace
        const previouslySelectedConversationId =
          currentSelection?.kind === "conversation" ? currentSelection.conversationId : undefined
        const selectedWorkspace: ConversationWorkspaceSelection = {
          kind: "localDraft",
          localDraftId: localDraftWorkspace.localDraftId,
        }

        stopConversationRun(previouslySelectedConversationId)

        set((current) => ({
          error: toMessage(error),
          listLoading: false,
          bootstrapped: true,
          selectedWorkspace,
          localDraftWorkspace,
          draftsByKey: loadDraftForSelection(selectedWorkspace, localDraftWorkspace, current.draftsByKey),
        }))

        persistWorkspaceState({ selectedWorkspace, localDraftWorkspace })
      }
    },

    activateLocalDraftWorkspace: () => {
      const state = get()
      const previouslySelectedConversationId =
        state.selectedWorkspace?.kind === "conversation" ? state.selectedWorkspace.conversationId : undefined
      const localDraftWorkspace = state.localDraftWorkspace ?? createLocalDraftWorkspace()
      const selectedWorkspace: ConversationWorkspaceSelection = {
        kind: "localDraft",
        localDraftId: localDraftWorkspace.localDraftId,
      }
      const draftsByKey = loadDraftForSelection(selectedWorkspace, localDraftWorkspace, state.draftsByKey)

      stopConversationRun(previouslySelectedConversationId)

      set({
        selectedWorkspace,
        localDraftWorkspace,
        draftsByKey,
        error: null,
      })

      persistWorkspaceState({ selectedWorkspace, localDraftWorkspace })
    },

    selectConversation: async (conversationId) => {
      const state = get()
      const previouslySelectedConversationId =
        state.selectedWorkspace?.kind === "conversation" ? state.selectedWorkspace.conversationId : undefined
      const selectedWorkspace: ConversationWorkspaceSelection = {
        kind: "conversation",
        conversationId,
      }
      const draftsByKey = loadDraftForSelection(selectedWorkspace, state.localDraftWorkspace, state.draftsByKey)

      if (previouslySelectedConversationId && previouslySelectedConversationId !== conversationId) {
        stopConversationRun(previouslySelectedConversationId)
      }

      set({
        selectedWorkspace,
        draftsByKey,
        conversationLoading: true,
        error: null,
      })

      persistWorkspaceState({ selectedWorkspace, localDraftWorkspace: state.localDraftWorkspace })

      try {
        const { detail, messages } = await loadConversationPayload(conversationId)
        const pendingTurn = derivePendingTurnState(detail, messages, detail.interactionState)
        const restoredStartedAtMs = resolvePendingTurnStartedAtMsFromMessages(
          messages,
          pendingTurn.turnId ?? detail.activeTurnId,
        )

        set((current) => ({
          conversationLoading: false,
          detailsByConversationId: {
            ...current.detailsByConversationId,
            [conversationId]: detail,
          },
          messagesByConversationId: {
            ...current.messagesByConversationId,
            [conversationId]: messages,
          },
          pendingTurnByConversationId: {
            ...current.pendingTurnByConversationId,
            [conversationId]: pendingTurn,
          },
          pendingTurnStartedAtMsByConversationId: pendingTurnStartedAtMsByConversation(
            current,
            conversationId,
            pendingTurn,
            restoredStartedAtMs,
          ),
        }))

        await startRealtimeRun(conversationId, detail, messages)
      } catch (error) {
        set({ conversationLoading: false, error: toMessage(error) })
        throw error
      }
    },

    setSearchQuery: async (query) => {
      set({ query, listLoading: true, error: null })

      try {
        const conversations = query.trim() ? await searchConversations(query) : await listConversations()
        set({ conversations, listLoading: false })
      } catch (error) {
        set({ listLoading: false, error: toMessage(error) })
      }
    },

    setDraft: (value) => {
      const state = get()
      const selection = state.selectedWorkspace
      if (!selection) return

      const draftKey =
        selection.kind === "conversation"
          ? conversationDraftKeyForConversation(selection.conversationId)
          : conversationDraftKeyForLocalDraft(selection.localDraftId)

      writeConversationDraft(draftKey, value)

      set((current) => {
        const nextDraftsByKey = {
          ...current.draftsByKey,
          [draftKey]: value,
        }

        if (selection.kind === "localDraft" && current.localDraftWorkspace) {
          const updatedAt = new Date().toISOString()
          const localDraftWorkspace = {
            ...current.localDraftWorkspace,
            draft: value,
            updatedAt,
          }

          persistWorkspaceState({
            selectedWorkspace: current.selectedWorkspace,
            localDraftWorkspace,
          })

          return {
            draftsByKey: nextDraftsByKey,
            localDraftWorkspace,
          }
        }

        return {
          draftsByKey: nextDraftsByKey,
        }
      })
    },

    submitComposerMessage: async () => {
      const state = get()
      const selection = state.selectedWorkspace
      if (!selection) return

      const draftKey =
        selection.kind === "conversation"
          ? conversationDraftKeyForConversation(selection.conversationId)
          : conversationDraftKeyForLocalDraft(selection.localDraftId)

      const content = (state.draftsByKey[draftKey] ?? "").trim()
      if (!content) return

      set({
        error: null,
        submittingWorkspaceKey: workspaceRequestKey(selection),
      })

      try {
        if (selection.kind === "localDraft") {
          const accepted = await createConversation({
            initialMessage: {
              type: "user_message",
              content,
            },
          })

          const pendingTurn = applyAcceptedResponse(accepted)
          const nextLocalDraftWorkspace = createLocalDraftWorkspace()
          const nextSelection: ConversationWorkspaceSelection = {
            kind: "conversation",
            conversationId: accepted.conversation.conversationId,
          }

          removeConversationDraft(draftKey)

          set((current) => ({
            selectedWorkspace: nextSelection,
            localDraftWorkspace: nextLocalDraftWorkspace,
            draftsByKey: {
              ...current.draftsByKey,
              [draftKey]: "",
              [conversationDraftKeyForLocalDraft(nextLocalDraftWorkspace.localDraftId)]: "",
            },
            submittingWorkspaceKey: null,
            error: null,
          }))

          persistWorkspaceState({
            selectedWorkspace: nextSelection,
            localDraftWorkspace: nextLocalDraftWorkspace,
          })

          if (shouldStreamPendingTurn(pendingTurn)) {
            const conversationId = accepted.conversation.conversationId
            const detail = get().detailsByConversationId[conversationId]
            const messages = get().messagesByConversationId[conversationId] ?? []
            if (detail) {
              await startRealtimeRun(conversationId, detail, messages)
            }
          }
          return
        }

        const accepted = await sendMessage(selection.conversationId, {
          type: "user_message",
          content,
        })

        const pendingTurn = applyAcceptedResponse(accepted)

        removeConversationDraft(draftKey)

        set((current) => ({
          draftsByKey: {
            ...current.draftsByKey,
            [draftKey]: "",
          },
          submittingWorkspaceKey: null,
          error: null,
        }))

        if (shouldStreamPendingTurn(pendingTurn)) {
          const detail = get().detailsByConversationId[selection.conversationId]
          const messages = get().messagesByConversationId[selection.conversationId] ?? []
          if (detail) {
            await startRealtimeRun(selection.conversationId, detail, messages)
          }
        }
      } catch (error) {
        set((current) => ({
          error: toMessage(error),
          submittingWorkspaceKey: null,
          pendingTurnByConversationId:
            selection.kind === "conversation"
              ? {
                  ...current.pendingTurnByConversationId,
                  [selection.conversationId]: { state: "error" },
                }
              : current.pendingTurnByConversationId,
          pendingTurnStartedAtMsByConversationId:
            selection.kind === "conversation"
              ? omitRecordKey(current.pendingTurnStartedAtMsByConversationId ?? {}, selection.conversationId)
              : current.pendingTurnStartedAtMsByConversationId,
        }))
      }
    },

    submitCandidateSelection: async (input) => {
      const state = get()
      const selection = state.selectedWorkspace
      if (!selection || selection.kind !== "conversation") return

      set((current) => ({
        error: null,
        pendingTurnByConversationId: {
          ...current.pendingTurnByConversationId,
          [selection.conversationId]: {
            state: "submitting_selection",
            sourceMessageId: input.messageId,
          },
        },
        pendingTurnStartedAtMsByConversationId: omitRecordKey(
          current.pendingTurnStartedAtMsByConversationId ?? {},
          selection.conversationId,
        ),
      }))

      try {
        const accepted = await sendMessage(selection.conversationId, input)
        const pendingTurn = applyAcceptedResponse(accepted)

        set({ error: null })

        if (shouldStreamPendingTurn(pendingTurn)) {
          const detail = get().detailsByConversationId[selection.conversationId]
          const messages = get().messagesByConversationId[selection.conversationId] ?? []
          if (detail) {
            await startRealtimeRun(selection.conversationId, detail, messages)
          }
        }
      } catch (error) {
        set((current) => ({
          error: toMessage(error),
          pendingTurnByConversationId: {
            ...current.pendingTurnByConversationId,
            [selection.conversationId]: {
              state: "clarifying",
              sourceMessageId: input.messageId,
            },
          },
          pendingTurnStartedAtMsByConversationId: omitRecordKey(
            current.pendingTurnStartedAtMsByConversationId ?? {},
            selection.conversationId,
          ),
        }))
      }
    },

    submitClarificationResponse: async (input) => {
      const state = get()
      const selection = state.selectedWorkspace
      if (!selection || selection.kind !== "conversation") return

      set((current) => ({
        error: null,
        pendingTurnByConversationId: {
          ...current.pendingTurnByConversationId,
          [selection.conversationId]: {
            state: "submitting_selection",
            sourceMessageId: input.messageId,
          },
        },
        pendingTurnStartedAtMsByConversationId: omitRecordKey(
          current.pendingTurnStartedAtMsByConversationId ?? {},
          selection.conversationId,
        ),
      }))

      try {
        const accepted = await sendMessage(selection.conversationId, input)
        const pendingTurn = applyAcceptedResponse(accepted)

        set({ error: null })

        if (shouldStreamPendingTurn(pendingTurn)) {
          const detail = get().detailsByConversationId[selection.conversationId]
          const messages = get().messagesByConversationId[selection.conversationId] ?? []
          if (detail) {
            await startRealtimeRun(selection.conversationId, detail, messages)
          }
        }
      } catch (error) {
        set((current) => ({
          error: toMessage(error),
          pendingTurnByConversationId: {
            ...current.pendingTurnByConversationId,
            [selection.conversationId]: {
              state: "clarifying",
              sourceMessageId: input.messageId,
            },
          },
          pendingTurnStartedAtMsByConversationId: omitRecordKey(
            current.pendingTurnStartedAtMsByConversationId ?? {},
            selection.conversationId,
          ),
        }))
      }
    },

    submitLayoutTreeUserMessage: async (input) => {
      const state = get()
      const selection = state.selectedWorkspace
      if (!selection || selection.kind !== "conversation") return

      const content = input.content.trim()
      if (!content) return

      set({
        error: null,
        submittingWorkspaceKey: workspaceRequestKey(selection),
      })

      try {
        const accepted = await sendMessage(selection.conversationId, {
          ...input,
          content,
        } as CreateConversationMessageInput)
        const pendingTurn = applyAcceptedResponse(accepted)

        set({
          error: null,
          submittingWorkspaceKey: null,
        })

        if (shouldStreamPendingTurn(pendingTurn)) {
          const detail = get().detailsByConversationId[selection.conversationId]
          const messages = get().messagesByConversationId[selection.conversationId] ?? []
          if (detail) {
            await startRealtimeRun(selection.conversationId, detail, messages)
          }
        }
      } catch (error) {
        set((current) => ({
          error: toMessage(error),
          submittingWorkspaceKey: null,
          pendingTurnByConversationId: {
            ...current.pendingTurnByConversationId,
            [selection.conversationId]: { state: "error" },
          },
          pendingTurnStartedAtMsByConversationId: omitRecordKey(
            current.pendingTurnStartedAtMsByConversationId ?? {},
            selection.conversationId,
          ),
        }))
      }
    },

    showInteractionError: (message) => set({ error: message }),

    clearError: () => set({ error: null }),
  }
})
