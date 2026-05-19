import { parseSSEStream, runHttpRequest } from "@ag-ui/client"
import { EventSchemas, type BaseEvent, type Message, type RunAgentInput } from "@ag-ui/core"
import { conversationApiConfig } from "@/config/conversation"
import { createId } from "@/lib/ids"
import { translate } from "@/i18n/messages"
import { getAuthorizedSession } from "@/services/auth-service"
import type { ConversationAgUiEventApi } from "@/services/conversation-response-adapter"
import type { ConversationRunInput } from "@/types/conversation"
import { ServiceError } from "@/types/auth"

const RUNS_PATH = "/runs"
const SUPPORTED_EVENT_TYPES = new Set<ConversationAgUiEventApi["type"]>([
  "RUN_STARTED",
  "RUN_FINISHED",
  "RUN_ERROR",
  "ACTIVITY_SNAPSHOT",
  "ACTIVITY_DELTA",
  "STATE_SNAPSHOT",
  "STATE_DELTA",
  "TEXT_MESSAGE_START",
  "TEXT_MESSAGE_CONTENT",
  "TEXT_MESSAGE_END",
  "CUSTOM",
])

export interface ConversationRunStreamHandlers {
  onEvent: (event: ConversationAgUiEventApi) => void
}

function toRunsUrl(): string {
  return `${conversationApiConfig.basePath}${RUNS_PATH}`
}

function toAgentMessages(messages: ConversationRunInput["messages"]): Message[] {
  return messages.map((message) => ({
    id: createId("ag_msg"),
    role: message.role,
    content: message.content,
  }))
}

function toRunAgentInput(input: ConversationRunInput): RunAgentInput {
  return {
    threadId: input.threadId,
    runId: input.runId,
    messages: toAgentMessages(input.messages),
    state: input.state ?? {},
    tools: (input.tools ?? []) as never,
    context: (input.context ?? []) as never,
    ...(input.forwardedProps ? { forwardedProps: input.forwardedProps } : {}),
  }
}

function toRequestInit(input: RunAgentInput, accessToken: string, abortController: AbortController): RequestInit {
  return {
    method: "POST",
    headers: {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      "X-Request-Id": createId("req"),
    },
    body: JSON.stringify(input),
    signal: abortController.signal,
  }
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value)
}

function collectAgUiEventsFromPayload(value: unknown): unknown[] {
  if (!isRecord(value)) return []

  const agUi = value.ag_ui
  if (!isRecord(agUi)) return []

  return Array.isArray(agUi.events) ? agUi.events : []
}

function collectNestedAgUiEvents(record: Record<string, unknown>): unknown[] {
  const nestedCandidates: unknown[] = []

  nestedCandidates.push(...collectAgUiEventsFromPayload(record))

  if (isRecord(record.rich_payload)) {
    nestedCandidates.push(...collectAgUiEventsFromPayload(record.rich_payload))
  }

  if (isRecord(record.payload)) {
    nestedCandidates.push(...collectAgUiEventsFromPayload(record.payload))

    if (isRecord(record.payload.rich_payload)) {
      nestedCandidates.push(...collectAgUiEventsFromPayload(record.payload.rich_payload))
    }

    if (isRecord(record.payload.message)) {
      nestedCandidates.push(...collectNestedAgUiEvents(record.payload.message))
    }
  }

  if (isRecord(record.message)) {
    nestedCandidates.push(...collectNestedAgUiEvents(record.message))
  }

  return nestedCandidates
}

function collectEventCandidates(payload: unknown): unknown[] {
  if (Array.isArray(payload)) {
    return payload.flatMap((item) => collectEventCandidates(item))
  }

  if (!isRecord(payload)) return []

  const candidates: unknown[] = []

  if ("type" in payload) {
    candidates.push(payload)
  }

  if ("event" in payload) {
    candidates.push(...collectEventCandidates(payload.event))
  }

  if ("data" in payload) {
    candidates.push(...collectEventCandidates(payload.data))
  }

  candidates.push(...collectNestedAgUiEvents(payload))
  return candidates
}

function toRunErrorEvent(event: BaseEvent): ConversationAgUiEventApi {
  const eventRecord = event as Record<string, unknown>
  const error: Record<string, unknown> = {}

  if (typeof eventRecord.message === "string" && eventRecord.message.trim()) {
    error.message = eventRecord.message
  }

  if (typeof eventRecord.code === "string" && eventRecord.code.trim()) {
    error.code = eventRecord.code
  }

  return {
    type: "RUN_ERROR",
    ...(typeof eventRecord.timestamp === "number" ? { timestamp: eventRecord.timestamp } : {}),
    ...(typeof eventRecord.threadId === "string" ? { threadId: eventRecord.threadId } : {}),
    ...(typeof eventRecord.runId === "string" ? { runId: eventRecord.runId } : {}),
    error,
  }
}

function toSupportedConversationEvent(event: BaseEvent): ConversationAgUiEventApi | undefined {
  if (event.type === "RUN_ERROR") {
    return toRunErrorEvent(event)
  }

  if (!SUPPORTED_EVENT_TYPES.has(event.type as ConversationAgUiEventApi["type"])) {
    return undefined
  }

  return event as unknown as ConversationAgUiEventApi
}

function toConversationAgUiEvents(payload: unknown): ConversationAgUiEventApi[] {
  const nextEvents: ConversationAgUiEventApi[] = []

  for (const candidate of collectEventCandidates(payload)) {
    const parsedEvent = EventSchemas.safeParse(candidate)
    if (!parsedEvent.success) continue

    const supportedEvent = toSupportedConversationEvent(parsedEvent.data)
    if (supportedEvent) {
      nextEvents.push(supportedEvent)
    }
  }

  return nextEvents
}

function isAbortError(error: unknown): boolean {
  if (!error || typeof error !== "object") return false
  return "name" in error && error.name === "AbortError"
}

function toServiceError(error: unknown): ServiceError {
  if (error instanceof ServiceError) return error
  if (error instanceof Error && error.message.trim()) {
    return new ServiceError("SERVICE_UNAVAILABLE", error.message)
  }

  return new ServiceError("SERVICE_UNAVAILABLE", translate("conversation.serviceUnavailable"))
}

async function streamConversationRun(
  input: RunAgentInput,
  accessToken: string,
  handlers: ConversationRunStreamHandlers,
  abortController: AbortController,
): Promise<void> {
  await new Promise<void>((resolve, reject) => {
    let settled = false
    let subscription: { unsubscribe: () => void } | undefined

    const settleResolve = (): void => {
      if (settled) return
      settled = true
      resolve()
    }

    const settleReject = (error: unknown): void => {
      if (settled) return
      settled = true
      reject(error)
    }

    subscription = parseSSEStream(
      runHttpRequest(toRunsUrl(), toRequestInit(input, accessToken, abortController)),
    ).subscribe({
      next: (payload) => {
        try {
          for (const event of toConversationAgUiEvents(payload)) {
            handlers.onEvent(event)
          }
        } catch (error) {
          abortController.abort()
          queueMicrotask(() => subscription?.unsubscribe())
          settleReject(error)
        }
      },
      error: (error) => {
        settleReject(error)
      },
      complete: () => {
        settleResolve()
      },
    })
  })
}

export async function startConversationRun(
  input: ConversationRunInput,
  handlers: ConversationRunStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  if (signal?.aborted) return

  const session = await getAuthorizedSession()
  const abortController = new AbortController()
  const runInput = toRunAgentInput(input)

  const unsubscribeAbort = (() => {
    if (!signal) return () => undefined

    const onAbort = () => {
      abortController.abort()
    }

    signal.addEventListener("abort", onAbort, { once: true })
    return () => signal.removeEventListener("abort", onAbort)
  })()

  try {
    await streamConversationRun(runInput, session.accessToken, handlers, abortController)
  } catch (error) {
    if (abortController.signal.aborted || signal?.aborted || isAbortError(error)) {
      return
    }

    throw toServiceError(error)
  } finally {
    unsubscribeAbort()
  }
}
