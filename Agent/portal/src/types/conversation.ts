export type ConversationStatus = "created" | "active" | "paused" | "archived" | "expired"

export type InteractionState = "idle" | "thinking" | "clarifying" | "executing" | "completed" | "error"

export type ConversationMessageRole = "user" | "assistant" | "system" | "status"

export type ConversationMessageContentType = "text" | "status" | "clarification" | "rich_content"

export type ConversationMessageStatus =
  | "received"
  | "persisted"
  | "published"
  | "processing"
  | "streaming"
  | "responded"
  | "failed"

export type ConversationStatusEventType =
  | "message.created"
  | "message.updated"
  | "interaction.status_changed"
  | "context.updated"
  | "reasoning_trace.created"
  | "rich_content.created"
  | "conversation.archived"
  | "conversation.restored"
  | "conversation.expired"
  | "error"

export type LayoutTreeNodeType =
  | "stack"
  | "grid"
  | "tabs"
  | "section"
  | "card"
  | "heading"
  | "paragraph"
  | "markdown"
  | "badge-row"
  | "kv-list"
  | "metric-list"
  | "data-table"
  | "chart"
  | "attachment-list"
  | "callout"
  | "divider"
  | "action-row"

export type LayoutTreeActionKind = "submit_message" | "open_ref" | "copy_text" | "open_url"

export type LayoutTreeActionStyle = "primary" | "secondary" | "danger" | "link"

export interface LayoutTreeNode {
  id?: string
  type: LayoutTreeNodeType
  props?: Record<string, unknown>
  children?: LayoutTreeNode[]
}

export interface LayoutTreeAction {
  id: string
  kind: LayoutTreeActionKind
  label: string
  style?: LayoutTreeActionStyle
  payload?: Record<string, unknown>
  confirmText?: string
}

export interface LayoutTreeContentMeta {
  intent?: "thought" | "tool_call" | "progress" | "clarification" | "result" | "error"
  terminal?: boolean
  sourceMessageId?: string
  reasoningTraceId?: string
  replaceStrategy?: "append" | "replace"
}

export interface LayoutTreeContent {
  contract: "conversation.ui.layout-tree@1"
  blockId: string
  ui: LayoutTreeNode
  actions?: LayoutTreeAction[]
  meta?: LayoutTreeContentMeta
}

export interface LayoutTreeStateSnapshot {
  interaction?: {
    status?: "idle" | "thinking" | "clarifying" | "executing" | "completed" | "error"
  }
  selection?: {
    required?: boolean
    selectedCandidateOptionId?: string | null
    selectionLocked?: boolean
  }
  view?: {
    activeBlockIds?: string[]
  }
}

export type CandidateOptionActionType = "confirm" | "reject" | "revise"

export interface CandidateOptionField {
  key: string
  label: string
  value: string
}

export interface CandidateOptionExtra {
  title?: string
  content: string
}

export interface CandidateOptionAction {
  type: CandidateOptionActionType
  label: string
  inputLabel?: string
  inputPlaceholder?: string
  submitLabel?: string
}

export interface CandidateOption {
  optionId: string
  title: string
  recommended?: boolean
  summary?: string
  fields: CandidateOptionField[]
  extra?: CandidateOptionExtra
}

export interface CandidateOptionsRichPayload {
  reasoningTraceId: string
  title: string
  summary?: string
  selectedOptionId?: string
  selectionLocked?: boolean
  options: CandidateOption[]
  actions: CandidateOptionAction[]
}

export interface ClarificationOption {
  label: string
  value: string
}

export interface ClarificationInputConstraints {
  required?: boolean
  allowFreeText?: boolean
  freeTextLabel?: string
  freeTextPlaceholder?: string
}

export interface ConversationClarificationRichPayload {
  clarificationId?: string
  prompt: string
  options: ClarificationOption[]
  inputConstraints?: ClarificationInputConstraints
  selectedValue?: string
  freeTextValue?: string
  responseLocked?: boolean
}

export interface ConversationThoughtRichPayload {
  traceId?: string
  title?: string
  status?: string
  summary: string
}

export interface ConversationResultRichPayload {
  title?: string
  summary: string
  resultId?: string
  sourceMessage?: string
}

export interface ConversationGenericAgUiRichPayload {
  eventName: string
  title?: string
  summary: string
  data?: Record<string, unknown>
}

export interface ConversationMarkdownRichPayload {
  markdown: string
}

export interface ConversationLayoutTreeRichPayload {
  activity: LayoutTreeContent
  stateSnapshot?: LayoutTreeStateSnapshot
}

export type ConversationRichPayload =
  | {
      kind: "markdown"
      data: ConversationMarkdownRichPayload
    }
  | {
      kind: "layout_tree"
      data: ConversationLayoutTreeRichPayload
    }
  | {
      kind: "candidate_options"
      data: CandidateOptionsRichPayload
    }
  | {
      kind: "clarification"
      data: ConversationClarificationRichPayload
    }
  | {
      kind: "thought"
      data: ConversationThoughtRichPayload
    }
  | {
      kind: "result"
      data: ConversationResultRichPayload
    }
  | {
      kind: "ag_ui"
      data: ConversationGenericAgUiRichPayload
    }

export interface ConversationSummary {
  conversationId: string
  title: string
  displaySummary?: string
  updatedAt: string
  lastActiveAt?: string
  latestMessageSummary?: string
  tags?: string[]
  status?: ConversationStatus
  unreadAgentUpdateCount?: number
  attentionFlag?: boolean
  archivedAt?: string
  expiresAt?: string
}

export interface ConversationDetail extends ConversationSummary {
  createdAt: string
  interactionState?: InteractionState
  activeTurnId?: string
  contextSummary?: string
}

export interface ConversationMessageSummary {
  messageId: string
  conversationId: string
  turnId?: string
  role: ConversationMessageRole
  contentType: ConversationMessageContentType
  content: string
  richPayload?: ConversationRichPayload
  createdAt: string
  updatedAt?: string
  status?: ConversationMessageStatus
  agUiSequence?: number
  agUiEventName?: string
  parentMessageId?: string
  clientMessageId?: string
  errorCode?: string
  errorMessage?: string
  traceId?: string
  correlationId?: string
}

export interface ConversationStatusEvent {
  statusEventId: string
  conversationId: string
  turnId?: string
  messageId?: string
  eventType: ConversationStatusEventType | string
  sequence: number
  interactionState?: InteractionState
  messageStatus?: ConversationMessageStatus
  message?: ConversationMessageSummary
  /** 会话服务落库的 AG-UI 线协议事件（payload 即 wire event，无嵌套 message） */
  agUiWireEvent?: Record<string, unknown>
  activeTurnId?: string | null
  completedTurnId?: string
  createdAt: string
}

export interface ConversationEventListResult {
  events: ConversationStatusEvent[]
  nextCursor?: string | null
  hasMore: boolean
  latestSequence: number
  recommendedPollIntervalMs: number
  interactionState?: InteractionState
}

export interface ConversationRunMessageInput {
  role: "user" | "assistant"
  content: string
}

export interface ConversationRunInput {
  threadId: string
  runId: string
  messages: ConversationRunMessageInput[]
  state?: Record<string, unknown>
  tools?: unknown[]
  context?: unknown[]
  forwardedProps?: Record<string, unknown>
}

export interface ConversationScenarioBinding {
  scenarioId?: string
  scenarioName?: string
  taskType?: string
}

export interface InitialConversationContext {
  summary?: string
  keyVariables?: Record<string, string>
}

export interface CreateConversationInput {
  initialMessage: UserMessageInput
  title?: string
  tags?: string[]
  scenarioBinding?: ConversationScenarioBinding
  initialContext?: InitialConversationContext
  idempotencyKey?: string
}

export interface UserMessageInput {
  type: "user_message"
  content: string
  clientMessageId?: string
  parentMessageId?: string
  idempotencyKey?: string
}

export interface CandidateSelectionInput {
  type: "candidate_selection"
  messageId?: string
  reasoningTraceId: string
  candidateOptionId: string
  selection: "confirm" | "reject" | "revise"
  additionalConstraints?: string
  clientMessageId?: string
  idempotencyKey?: string
}

export interface ClarificationResponseInput {
  type: "clarification_response"
  messageId?: string
  clarificationId?: string
  selectedValue?: string
  freeText?: string
  clientMessageId?: string
  idempotencyKey?: string
}

export type CreateConversationMessageInput = UserMessageInput | CandidateSelectionInput | ClarificationResponseInput

export interface CopyConversationConfigInput {
  title?: string
  copyTags?: boolean
  copyScenarioBinding?: boolean
  additionalTags?: string[]
}

export interface MessageAcceptedResult {
  conversation: ConversationDetail
  message: ConversationMessageSummary
  statusEvent: ConversationStatusEvent
  nextPollAfterMs: number
}

export interface LocalDraftWorkspace {
  localDraftId: string
  title: string
  draft: string
  createdAt: string
  updatedAt: string
}

export type ConversationWorkspaceSelection =
  | {
      kind: "conversation"
      conversationId: string
    }
  | {
      kind: "localDraft"
      localDraftId: string
    }

export interface ConversationWorkspaceState {
  selectedWorkspace: ConversationWorkspaceSelection | null
  localDraftWorkspace: LocalDraftWorkspace | null
}
