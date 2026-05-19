import { useEffect, useRef, useState } from "react"
import { ChevronDown, LoaderCircle, Sparkles } from "lucide-react"
import { MessageRichContent, canRenderRichContent } from "@/components/chat/components/message-rich-content"
import { WaitingMessage } from "@/components/chat/components/waiting-message"
import { useI18n } from "@/i18n"
import { getStoredLocale, translate } from "@/i18n/messages"
import { cn } from "@/lib/cn"
import { buildChatTimeline } from "@/store/conversation-runtime"
import type {
  CandidateSelectionInput,
  ClarificationResponseInput,
  ConversationMessageSummary,
  UserMessageInput,
} from "@/types/conversation"

interface ChatMessageListProps {
  title: string
  summary?: string
  showHeader?: boolean
  messages: ConversationMessageSummary[]
  submittingSelectionMessageId?: string
  isAwaitingReply?: boolean
  awaitingReplyStartedAtMs?: number
  expandToContent?: boolean
  onCandidateSelection: (input: CandidateSelectionInput) => void
  onClarificationResponse?: (input: ClarificationResponseInput) => void
  onUserMessageAction?: (input: UserMessageInput) => void
  onOpenReference?: (refId: string) => void
}

const STANDARD_MESSAGE_COLUMN_CLASS = "w-full max-w-3xl"
const EXPANDED_MESSAGE_COLUMN_CLASS = "w-full max-w-[min(100%,72rem)]"
const STANDARD_ASSISTANT_BUBBLE_CLASS = "w-fit max-w-[85%]"
const STANDARD_USER_WRAPPER_CLASS = "flex w-full max-w-3xl flex-col items-end"
const STANDARD_USER_BUBBLE_CLASS = "w-fit max-w-[85%] ml-auto"

function messageColumnVariant(message: ConversationMessageSummary): "standard" | "expanded" {
  const payload = message.richPayload
  if (!payload) return "standard"
  if (payload.kind === "candidate_options") return "expanded"
  if (payload.kind !== "layout_tree") return "standard"

  const actions = payload.data.activity.actions ?? []
  const hasCandidateSelectionAction = actions.some((action) => {
    const payloadRecord = action.payload
    const selection = payloadRecord?.selection ?? payloadRecord?.action
    const candidateId = payloadRecord?.candidate_option_id ?? payloadRecord?.candidateOptionId
    return Boolean(candidateId && (selection === "confirm" || selection === "reject" || selection === "revise"))
  })

  return hasCandidateSelectionAction ? "expanded" : "standard"
}

function messageColumnClass(variant: "standard" | "expanded"): string {
  return variant === "expanded" ? EXPANDED_MESSAGE_COLUMN_CLASS : STANDARD_MESSAGE_COLUMN_CLASS
}

function formatMessageTime(value: string): string {
  const date = new Date(value)
  if (!value || Number.isNaN(date.getTime())) return translate("chat.messageTime.invalid")

  const localeTag = getStoredLocale() === "zh-CN" ? "zh-CN" : "en-US"
  return new Intl.DateTimeFormat(localeTag, {
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date)
}

function richContentSummary(message: ConversationMessageSummary): string {
  const payload = message.richPayload
  if (!payload) return message.content
  if (payload.kind === "thought") return payload.data.summary
  if (payload.kind === "result") return payload.data.summary
  if (payload.kind === "ag_ui") return payload.data.summary
  return message.content
}

function isThoughtMessage(message: ConversationMessageSummary): boolean {
  return message.richPayload?.kind === "thought"
}

function isRunningMessageStatus(status: ConversationMessageSummary["status"]): boolean {
  return status === "processing" || status === "streaming"
}

function isRunningThoughtStatus(status?: string): boolean {
  const normalized = status?.toLowerCase()
  return normalized === "running" || normalized === "processing" || normalized === "streaming"
}

interface ThoughtTraceProps {
  messages: ConversationMessageSummary[]
  hasBodyContent: boolean
}

function ThoughtTrace({ messages, hasBodyContent }: ThoughtTraceProps) {
  const { t } = useI18n()
  const [expanded, setExpanded] = useState(true)
  const summaries = messages
    .map((message) => (message.richPayload?.kind === "thought" ? message.richPayload.data.summary : message.content))
    .filter(Boolean)
  const isRunning =
    !hasBodyContent &&
    messages.some(
      (message) =>
        (message.richPayload?.kind === "thought" && isRunningThoughtStatus(message.richPayload.data.status)) ||
        isRunningMessageStatus(message.status),
    )
  const statusLabel = isRunning ? t("chat.thought.running") : t("chat.thought.done")

  return (
    <section className="overflow-hidden rounded-xl border border-border/70 bg-white/60 text-sm leading-6 shadow-none backdrop-blur-sm">
      <button
        type="button"
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-muted-foreground transition-colors hover:text-foreground"
        aria-expanded={expanded}
        onClick={() => setExpanded((value) => !value)}
      >
        {isRunning ? <LoaderCircle className="h-3.5 w-3.5 animate-spin" /> : null}
        <span className="font-medium">{t("chat.thought.label")}</span>
        <span>{statusLabel}</span>
        <ChevronDown
          className={cn("ml-auto h-3.5 w-3.5 transition-transform", expanded ? "rotate-180" : "rotate-0")}
        />
      </button>
      {expanded ? (
        <div className="space-y-2 border-t border-border/50 px-3 pb-3 pt-2 text-muted-foreground">
          {summaries.map((summary, index) => (
            <p key={`${messages[index]?.messageId ?? "thought"}-${index}`} className="whitespace-pre-wrap break-words">
              {summary}
              {isRunning && index === summaries.length - 1 ? <span className="thinking-cursor-inline" /> : null}
            </p>
          ))}
        </div>
      ) : null}
    </section>
  )
}

function renderAssistantMessage(
  message: ConversationMessageSummary,
  submittingSelectionMessageId: string | undefined,
  onCandidateSelection: (input: CandidateSelectionInput) => void,
  onClarificationResponse: ((input: ClarificationResponseInput) => void) | undefined,
  onUserMessageAction: ((input: UserMessageInput) => void) | undefined,
  onOpenReference: ((refId: string) => void) | undefined,
) {
  if (canRenderRichContent(message)) {
    return (
      <div key={message.messageId} className="rounded-[24px] border-0 bg-transparent p-0 text-sm leading-6 shadow-none">
        <MessageRichContent
          message={message}
          submitting={submittingSelectionMessageId === message.messageId}
          onCandidateSelection={onCandidateSelection}
          onClarificationResponse={onClarificationResponse}
          onUserMessageAction={onUserMessageAction}
          onOpenReference={onOpenReference}
        />
      </div>
    )
  }

  if (message.richPayload?.kind === "result") {
    return (
      <div
        key={message.messageId}
        className={cn(
          "bubble-ai border border-border/70 bg-card px-4 py-3 text-sm leading-6 text-card-foreground shadow-card",
          STANDARD_ASSISTANT_BUBBLE_CLASS,
        )}
      >
        <p className="whitespace-pre-wrap break-words">{message.richPayload.data.summary}</p>
      </div>
    )
  }

  if (message.richPayload?.kind === "ag_ui") {
    const title = message.richPayload.data.title ?? translate("conversation.placeholder.richContent")

    return (
      <div
        key={message.messageId}
        className={cn(
          "bubble-ai border border-border/70 bg-card px-4 py-3 text-sm leading-6 text-card-foreground shadow-card",
          STANDARD_ASSISTANT_BUBBLE_CLASS,
        )}
      >
        <div className="mb-2 flex items-center gap-2 text-xs font-semibold text-ai">
          <Sparkles className="h-3.5 w-3.5" />
          <span>{title}</span>
        </div>
        <p className="whitespace-pre-wrap break-words">{message.richPayload.data.summary}</p>
      </div>
    )
  }

  return (
    <div
      key={message.messageId}
      className={cn(
        "bubble-ai border border-border/70 bg-card px-4 py-3 text-sm leading-6 text-card-foreground shadow-card",
        STANDARD_ASSISTANT_BUBBLE_CLASS,
      )}
    >
      <p className="whitespace-pre-wrap break-words">{richContentSummary(message)}</p>
    </div>
  )
}

export function ChatMessageList({
  title,
  summary,
  showHeader = true,
  messages,
  submittingSelectionMessageId,
  isAwaitingReply = false,
  awaitingReplyStartedAtMs,
  expandToContent = false,
  onCandidateSelection,
  onClarificationResponse,
  onUserMessageAction,
  onOpenReference,
}: ChatMessageListProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const timeline = buildChatTimeline(messages)

  useEffect(() => {
    const element = containerRef.current
    if (!element) return
    element.scrollTop = element.scrollHeight
  }, [messages, title])

  return (
    <div className={cn("flex min-h-0 flex-col", expandToContent ? "h-auto" : "flex-1")}>
      {showHeader ? (
        <div className="border-b border-border/60 bg-white/80 px-4 py-3 backdrop-blur-sm">
          <div className="mx-auto max-w-3xl">
            <h1 className="truncate text-sm font-semibold text-foreground">{title}</h1>
            {summary ? <p className="mt-1 text-xs text-muted-foreground">{summary}</p> : null}
          </div>
        </div>
      ) : null}

      <div
        ref={containerRef}
        className={cn(
          "px-4 py-6",
          expandToContent ? "overflow-visible" : "scrollbar-thin min-h-0 flex-1 overflow-y-auto",
        )}
      >
        <div className="mx-auto flex max-w-[72rem] flex-col gap-4">
          {timeline.map((item) => {
            if (item.type === "user") {
              return (
                <article key={item.message.messageId} className="flex animate-fade-in-up justify-end">
                  <div className={STANDARD_USER_WRAPPER_CLASS}>
                    <div
                      className={cn(
                        "bubble-user bg-primary px-4 py-3 text-sm leading-6 text-primary-foreground shadow-card",
                        STANDARD_USER_BUBBLE_CLASS,
                      )}
                    >
                      <p className="whitespace-pre-wrap break-words">{item.message.content}</p>
                    </div>
                    <p className="mt-1 px-1 text-right text-[11px] text-muted-foreground">
                      {formatMessageTime(item.message.createdAt)}
                    </p>
                  </div>
                </article>
              )
            }

            const thoughtMessages = item.messages.filter(isThoughtMessage)
            const bodyMessages = item.messages.filter((message) => !isThoughtMessage(message))
            const lastMessage = item.messages[item.messages.length - 1]
            const renderedBody = bodyMessages.map((message) => {
              const variant = messageColumnVariant(message)

              return (
                <div key={message.messageId} data-message-width={variant} className={cn(messageColumnClass(variant), "items-start")}>
                  {renderAssistantMessage(
                    message,
                    submittingSelectionMessageId,
                    onCandidateSelection,
                    onClarificationResponse,
                    onUserMessageAction,
                    onOpenReference,
                  )}
                </div>
              )
            })

            const timestampVariant =
              lastMessage && !isThoughtMessage(lastMessage) ? messageColumnVariant(lastMessage) : "standard"

            return (
              <article key={item.key} className="flex animate-fade-in-up justify-start">
                <div className="flex w-full flex-col items-start gap-2">
                  {thoughtMessages.length > 0 ? (
                    <div data-message-width="standard" className={cn(STANDARD_MESSAGE_COLUMN_CLASS, "items-start")}>
                      <ThoughtTrace messages={thoughtMessages} hasBodyContent={bodyMessages.length > 0} />
                    </div>
                  ) : null}
                  {renderedBody.length === 1 ? renderedBody[0] : renderedBody.length > 1 ? <div className="flex w-full flex-col gap-2">{renderedBody}</div> : null}
                  <div
                    data-message-width={timestampVariant}
                    className={cn(messageColumnClass(timestampVariant), "items-start px-1")}
                  >
                    <p className="mt-1 text-[11px] text-muted-foreground">
                      {formatMessageTime(lastMessage?.createdAt ?? "")}
                    </p>
                  </div>
                </div>
              </article>
            )
          })}
          {isAwaitingReply ? <WaitingMessage startedAtMs={awaitingReplyStartedAtMs} /> : null}
        </div>
      </div>
    </div>
  )
}
