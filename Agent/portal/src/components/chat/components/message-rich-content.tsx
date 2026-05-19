import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { AgUiLayoutTreeRenderer } from "@/components/chat/components/ag-ui-layout-tree-renderer"
import { CandidateOptionsCard } from "@/components/chat/components/candidate-options-card"
import { ClarificationCard } from "@/components/chat/components/clarification-card"
import type {
  CandidateSelectionInput,
  ClarificationResponseInput,
  ConversationMessageSummary,
  ConversationRichPayload,
  UserMessageInput,
} from "@/types/conversation"

interface MessageRichContentProps {
  message: ConversationMessageSummary
  submitting: boolean
  onCandidateSelection: (input: CandidateSelectionInput) => void
  onClarificationResponse?: (input: ClarificationResponseInput) => void
  onUserMessageAction?: (input: UserMessageInput) => void
  onOpenReference?: (refId: string) => void
}

type RenderableRichPayload = Extract<
  ConversationRichPayload,
  { kind: "markdown" | "layout_tree" | "candidate_options" | "clarification" }
>

type RenderableRichMessage = ConversationMessageSummary & {
  richPayload: RenderableRichPayload
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined
}

function candidateSelectionFromPayload(
  messageId: string,
  payload: Record<string, unknown>,
  fallbackReasoningTraceId?: string,
): CandidateSelectionInput | undefined {
  const candidateOptionId = asString(payload.candidate_option_id) ?? asString(payload.candidateOptionId)
  const reasoningTraceId =
    asString(payload.reasoning_trace_id) ?? asString(payload.reasoningTraceId) ?? fallbackReasoningTraceId
  const selection =
    payload.selection === "confirm" || payload.selection === "reject" || payload.selection === "revise"
      ? payload.selection
      : payload.action === "confirm" || payload.action === "reject" || payload.action === "revise"
        ? payload.action
        : undefined

  if (!candidateOptionId || !reasoningTraceId || !selection) return undefined

  return {
    type: "candidate_selection",
    messageId,
    reasoningTraceId,
    candidateOptionId,
    selection,
    additionalConstraints: asString(payload.additional_constraints),
  }
}

function clarificationResponseFromPayload(
  messageId: string,
  payload: Record<string, unknown>,
): ClarificationResponseInput | undefined {
  const type = asString(payload.type)
  if (type !== "clarification_response") return undefined

  return {
    type: "clarification_response",
    messageId,
    clarificationId: asString(payload.clarification_id) ?? asString(payload.clarificationId),
    selectedValue: asString(payload.selected_value) ?? asString(payload.selectedValue),
    freeText: asString(payload.free_text) ?? asString(payload.freeText),
  }
}

function fallbackUserMessageFromPayload(payload: Record<string, unknown>, fallbackLabel: string): UserMessageInput | undefined {
  const content = asString(payload.content) ?? asString(payload.text) ?? fallbackLabel.trim()
  if (!content) return undefined

  return {
    type: "user_message",
    content,
  }
}

export function canRenderRichContent(message: ConversationMessageSummary): message is RenderableRichMessage {
  return (
    message.richPayload?.kind === "markdown" ||
    message.richPayload?.kind === "layout_tree" ||
    message.richPayload?.kind === "candidate_options" ||
    message.richPayload?.kind === "clarification"
  )
}

function MarkdownContent({ text }: { text: string }) {
  return (
    <div className="markdown-rich-content overflow-x-auto rounded-xl border border-border/60 bg-background/80 px-4 py-3">
      <div className="markdown-body">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          skipHtml
          components={{
            a: ({ children, href }) => (
              <a href={href} target="_blank" rel="noreferrer">
                {children}
              </a>
            ),
          }}
        >
          {text}
        </ReactMarkdown>
      </div>
    </div>
  )
}

export function MessageRichContent({
  message,
  submitting,
  onCandidateSelection,
  onClarificationResponse,
  onUserMessageAction,
  onOpenReference,
}: MessageRichContentProps) {
  if (!canRenderRichContent(message)) {
    return <p className="whitespace-pre-wrap break-words">{message.content}</p>
  }

  const { richPayload } = message

  if (richPayload.kind === "markdown") {
    return <MarkdownContent text={richPayload.data.markdown} />
  }

  if (richPayload.kind === "candidate_options") {
    return (
      <CandidateOptionsCard
        payload={richPayload.data}
        submitting={submitting}
        onSelect={(selection) =>
          onCandidateSelection({
            type: "candidate_selection",
            messageId: message.messageId,
            reasoningTraceId: selection.reasoningTraceId,
            candidateOptionId: selection.candidateOptionId,
            selection: selection.selection,
            additionalConstraints: selection.additionalConstraints,
          })
        }
      />
    )
  }

  if (richPayload.kind === "clarification") {
    return (
      <ClarificationCard
        payload={richPayload.data}
        submitting={submitting}
        onSubmit={(response) =>
          onClarificationResponse?.({
            type: "clarification_response",
            messageId: message.messageId,
            clarificationId: response.clarificationId,
            selectedValue: response.selectedValue,
            freeText: response.freeText,
          })
        }
      />
    )
  }

  return (
    <AgUiLayoutTreeRenderer
      activity={richPayload.data.activity}
      stateSnapshot={richPayload.data.stateSnapshot}
      showMeta={false}
      onSubmitMessage={(actionPayload, actionEvent) => {
        const candidateSelection = candidateSelectionFromPayload(
          message.messageId,
          actionPayload,
          richPayload.data.activity.meta?.reasoningTraceId,
        )
        if (candidateSelection) {
          onCandidateSelection(candidateSelection)
          return
        }

        const clarificationResponse = clarificationResponseFromPayload(message.messageId, actionPayload)
        if (clarificationResponse) {
          onClarificationResponse?.(clarificationResponse)
          return
        }

        const fallbackMessage = fallbackUserMessageFromPayload(actionPayload, actionEvent.label)
        if (fallbackMessage) {
          onUserMessageAction?.(fallbackMessage)
        }
      }}
      onAction={(event) => {
        if (event.kind !== "open_ref") return

        const refId = asString(event.payload?.ref_id) ?? asString(event.payload?.refId)
        if (!refId) return
        onOpenReference?.(refId)
      }}
    />
  )
}
