import { emitDebugLog } from "@/lib/debug-log"
import {
  materializeMessagesFromAgUiWireEvents,
  type ConversationAgUiEventApi,
} from "@/services/conversation-response-adapter"
import type {
  ConversationDetail,
  ConversationMessageSummary,
  ConversationStatusEvent,
} from "@/types/conversation"

export type DerivePendingTurnOptions = {
  treatStaleUserOnlyAsComplete?: boolean
}

export type PendingTurnState =
  | {
      state: "idle"
      turnId?: string
      sourceMessageId?: string
    }
  | {
      state: "thinking" | "clarifying" | "submitting_selection" | "error"
      turnId?: string
      sourceMessageId?: string
    }

export type ChatTimelineItem =
  | {
      type: "user"
      message: ConversationMessageSummary
    }
  | {
      type: "assistant"
      key: string
      messages: ConversationMessageSummary[]
    }

function messageTurnKey(message: ConversationMessageSummary): string {
  return message.turnId ?? message.parentMessageId ?? message.messageId
}

function compareAssistantMessages(left: ConversationMessageSummary, right: ConversationMessageSummary): number {
  if (left.agUiSequence !== undefined && right.agUiSequence !== undefined && left.agUiSequence !== right.agUiSequence) {
    return left.agUiSequence - right.agUiSequence
  }

  return left.createdAt.localeCompare(right.createdAt)
}

export function buildChatTimeline(messages: ConversationMessageSummary[]): ChatTimelineItem[] {
  const buckets = new Map<
    string,
    {
      firstIndex: number
      userMessage?: ConversationMessageSummary
      assistantMessages: ConversationMessageSummary[]
    }
  >()

  messages.forEach((message, index) => {
    const key = messageTurnKey(message)
    const bucket = buckets.get(key) ?? { firstIndex: index, assistantMessages: [] }

    bucket.firstIndex = Math.min(bucket.firstIndex, index)

    if (message.role === "user") {
      bucket.userMessage = message
    } else {
      bucket.assistantMessages.push(message)
    }

    buckets.set(key, bucket)
  })

  return [...buckets.entries()]
    .sort((left, right) => left[1].firstIndex - right[1].firstIndex)
    .flatMap(([key, bucket]) => {
      const items: ChatTimelineItem[] = []

      if (bucket.userMessage) {
        items.push({
          type: "user",
          message: bucket.userMessage,
        })
      }

      if (bucket.assistantMessages.length > 0) {
        items.push({
          type: "assistant",
          key: `assistant-${key}`,
          messages: [...bucket.assistantMessages].sort(compareAssistantMessages),
        })
      }

      return items
    })
}

export function mergeConversationStatusEvent(
  messages: ConversationMessageSummary[],
  event: ConversationStatusEvent,
): ConversationMessageSummary[] {
  if (!event.message) return messages

  const nextMessages = [...messages]
  const existingIndex = nextMessages.findIndex((message) => message.messageId === event.message?.messageId)

  if (existingIndex >= 0) {
    nextMessages[existingIndex] = {
      ...nextMessages[existingIndex],
      ...event.message,
    }
    return nextMessages
  }

  return [...nextMessages, event.message]
}

export function mergeAgUiWireEventsIntoMessages(
  messages: ConversationMessageSummary[],
  events: ConversationStatusEvent[],
  conversationId: string,
  turnId?: string,
): ConversationMessageSummary[] {
  const wireEvents = events
    .filter((event) => event.agUiWireEvent)
    .sort((left, right) => left.sequence - right.sequence)
    .map((event) => event.agUiWireEvent as unknown as ConversationAgUiEventApi)

  if (wireEvents.length === 0) return messages

  const resolvedTurnId =
    turnId ?? messages.find((message) => message.role === "user")?.turnId ?? messages[messages.length - 1]?.turnId

  if (!resolvedTurnId) return messages

  const materialized = materializeMessagesFromAgUiWireEvents(
    conversationId,
    resolvedTurnId,
    messages,
    wireEvents,
  )

  // #region agent log
  emitDebugLog({
    location: "conversation-runtime.ts:mergeAgUiWireEventsIntoMessages",
    message: "materialized assistant messages from AG-UI wire events",
    hypothesisId: "H-H",
    data: {
      conversationId,
      turnId: resolvedTurnId,
      wireEventCount: wireEvents.length,
      messageCountBefore: messages.length,
      messageCountAfter: materialized.length,
      assistantWithRichPayload: materialized.filter(
        (message) => message.role !== "user" && message.richPayload != null,
      ).length,
    },
  })
  // #endregion

  return materialized
}

const TERMINAL_MESSAGE_STATUSES = new Set<ConversationMessageSummary["status"]>(["responded", "failed"])
const STALE_USER_ONLY_TURN_MS = 2 * 60 * 1000

function shouldClearActiveTurnId(interactionState?: ConversationDetail["interactionState"]): boolean {
  return interactionState === "idle" || interactionState === "completed" || interactionState === "error"
}

function toTimestampMs(value?: string): number | undefined {
  if (!value) return undefined
  const timestamp = Date.parse(value)
  return Number.isFinite(timestamp) ? timestamp : undefined
}

function turnMessagesForActiveId(
  messages: ConversationMessageSummary[],
  activeTurnId: string,
): ConversationMessageSummary[] {
  return messages.filter((message) => !message.turnId || message.turnId === activeTurnId)
}

export function isStaleUserOnlyActiveTurn(
  detail: ConversationDetail,
  messages: ConversationMessageSummary[],
): boolean {
  if (!detail.activeTurnId) return false

  const turnMessages = turnMessagesForActiveId(messages, detail.activeTurnId)
  if (!turnMessages.some((message) => message.role === "user")) return false
  if (turnMessages.some((message) => message.role !== "user")) return false

  const userTimestamps = turnMessages
    .filter((message) => message.role === "user")
    .map((message) => toTimestampMs(message.createdAt))
    .filter((timestamp): timestamp is number => typeof timestamp === "number")

  const lastActivityMs = Math.max(
    ...(userTimestamps.length > 0 ? userTimestamps : [0]),
    toTimestampMs(detail.updatedAt) ?? 0,
  )

  if (!Number.isFinite(lastActivityMs) || lastActivityMs <= 0) return false

  return Date.now() - lastActivityMs > STALE_USER_ONLY_TURN_MS
}

export function isActiveTurnSettled(
  messages: ConversationMessageSummary[],
  activeTurnId?: string,
): boolean {
  if (!activeTurnId) return false

  return messages.some(
    (message) =>
      (!message.turnId || message.turnId === activeTurnId) &&
      message.role !== "user" &&
      message.status !== undefined &&
      TERMINAL_MESSAGE_STATUSES.has(message.status),
  )
}

export function isTurnCompleteForRestore(
  detail: ConversationDetail,
  messages: ConversationMessageSummary[],
  fallbackInteractionState?: ConversationDetail["interactionState"],
  options?: DerivePendingTurnOptions,
): boolean {
  if (!detail.activeTurnId) return false
  if (options?.treatStaleUserOnlyAsComplete && isStaleUserOnlyActiveTurn(detail, messages)) return true
  if (!isActiveTurnSettled(messages, detail.activeTurnId)) return false
  if (deriveInteractionStateFromMessages(messages, detail.activeTurnId)) return false

  const fallback = fallbackInteractionState ?? detail.interactionState
  const fallbackLooksLive =
    fallback !== undefined &&
    fallback !== detail.interactionState &&
    (fallback === "thinking" || fallback === "executing")

  return !fallbackLooksLive
}

export function deriveInteractionStateFromMessages(
  messages: ConversationMessageSummary[],
  activeTurnId?: string,
): ConversationDetail["interactionState"] | undefined {
  const candidates = [...messages]
    .filter((message) => {
      if (activeTurnId && message.turnId && message.turnId !== activeTurnId) return false
      if (message.status && TERMINAL_MESSAGE_STATUSES.has(message.status)) return false
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

export function derivePendingTurnState(
  detail: ConversationDetail,
  messages: ConversationMessageSummary[],
  fallbackInteractionState?: ConversationDetail["interactionState"],
  fallbackSourceMessageId?: string,
  options?: DerivePendingTurnOptions,
): PendingTurnState {
  if (isTurnCompleteForRestore(detail, messages, fallbackInteractionState, options)) {
    // #region agent log
    emitDebugLog({
      location: "conversation-runtime.ts:derivePendingTurnState",
      message: "pending turn forced idle for completed restore",
      hypothesisId: "H-F",
      data: {
        conversationId: detail.conversationId,
        activeTurnId: detail.activeTurnId,
        staleUserOnly: options?.treatStaleUserOnlyAsComplete
          ? isStaleUserOnlyActiveTurn(detail, messages)
          : false,
        settled: detail.activeTurnId ? isActiveTurnSettled(messages, detail.activeTurnId) : false,
      },
    })
    // #endregion
    return { state: "idle" }
  }

  const fromMessages = deriveInteractionStateFromMessages(messages, detail.activeTurnId)
  const interactionState = fromMessages ?? fallbackInteractionState ?? detail.interactionState
  const turnId = detail.activeTurnId ?? messages[messages.length - 1]?.turnId

  // #region agent log
  if (interactionState === "thinking" || interactionState === "executing") {
    emitDebugLog({
      location: "conversation-runtime.ts:derivePendingTurnState",
      message: "pending turn resolved to thinking",
      hypothesisId: "H-C",
      data: {
        conversationId: detail.conversationId,
        fromMessages,
        fallbackInteractionState,
        detailInteractionState: detail.interactionState,
        resolvedInteractionState: interactionState,
        activeTurnId: detail.activeTurnId,
      },
    })
  }
  // #endregion

  if (interactionState === "clarifying") {
    return {
      state: "clarifying",
      ...(turnId ? { turnId } : {}),
      ...(fallbackSourceMessageId ? { sourceMessageId: fallbackSourceMessageId } : {}),
    }
  }

  if (interactionState === "thinking" || interactionState === "executing") {
    return {
      state: "thinking",
      ...(turnId ? { turnId } : {}),
    }
  }

  if (shouldClearActiveTurnId(interactionState)) {
    return { state: "idle" }
  }

  if (interactionState === "error") {
    return {
      state: "error",
      ...(turnId ? { turnId } : {}),
    }
  }

  return { state: "idle" }
}
