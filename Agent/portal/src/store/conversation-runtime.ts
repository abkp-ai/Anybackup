import type {
  ConversationDetail,
  ConversationMessageSummary,
  ConversationStatusEvent,
} from "@/types/conversation"

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

function deriveInteractionStateFromMessages(
  messages: ConversationMessageSummary[],
  activeTurnId?: string,
): ConversationDetail["interactionState"] | undefined {
  const terminalStatuses = new Set<ConversationMessageSummary["status"]>(["responded", "failed"])
  const candidates = [...messages]
    .filter((message) => {
      if (activeTurnId && message.turnId && message.turnId !== activeTurnId) return false
      if (message.status && terminalStatuses.has(message.status)) return false
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
): PendingTurnState {
  const interactionState =
    deriveInteractionStateFromMessages(messages, detail.activeTurnId) ??
    fallbackInteractionState ??
    detail.interactionState
  const turnId = detail.activeTurnId ?? messages[messages.length - 1]?.turnId

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

  if (interactionState === "error") {
    return {
      state: "error",
      ...(turnId ? { turnId } : {}),
    }
  }

  return { state: "idle" }
}
