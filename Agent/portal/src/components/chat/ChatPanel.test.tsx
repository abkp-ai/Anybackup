import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"

const {
  createConversationMock,
  getConversationDetailMock,
  getConversationMessagesMock,
  listConversationEventsMock,
  listConversationsMock,
  searchConversationsMock,
  sendMessageMock,
  startConversationRunMock,
} = vi.hoisted(() => ({
  createConversationMock: vi.fn(),
  getConversationDetailMock: vi.fn(),
  getConversationMessagesMock: vi.fn(),
  listConversationEventsMock: vi.fn(),
  listConversationsMock: vi.fn(),
  searchConversationsMock: vi.fn(),
  sendMessageMock: vi.fn(),
  startConversationRunMock: vi.fn(),
}))

vi.mock("@/services/conversation-service", () => ({
  createConversation: createConversationMock,
  getConversationDetail: getConversationDetailMock,
  getConversationMessages: getConversationMessagesMock,
  listConversationEvents: listConversationEventsMock,
  listConversations: listConversationsMock,
  searchConversations: searchConversationsMock,
  sendMessage: sendMessageMock,
}))

vi.mock("@/services/conversation-run-service", () => ({
  startConversationRun: startConversationRunMock,
}))

import { ChatPanel } from "@/components/chat/ChatPanel"
import { useConversationStore } from "@/store/useConversationStore"

function resetConversationStore(): void {
  useConversationStore.setState({
    bootstrapped: false,
    listLoading: false,
    conversationLoading: false,
    query: "",
    error: null,
    conversations: [],
    selectedWorkspace: null,
    localDraftWorkspace: null,
    detailsByConversationId: {},
    messagesByConversationId: {},
    draftsByKey: {},
    pendingTurnByConversationId: {},
    pendingTurnStartedAtMsByConversationId: {},
    nextPollAfterMsByConversationId: {},
    eventCursorByConversationId: {},
    latestEventSequenceByConversationId: {},
    appliedStatusEventIdsByConversationId: {},
    submittingWorkspaceKey: null,
  })
}

async function flushConversationRefresh(): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, 0))
}

function getComposerElements(container: HTMLElement): {
  input: HTMLTextAreaElement
  submitButton: HTMLButtonElement
} {
  const input = screen.getByRole("textbox")
  const submitButton = container.querySelector("button[aria-label]") as HTMLButtonElement | null

  if (!(input instanceof HTMLTextAreaElement) || !submitButton) {
    throw new Error("Expected the chat composer to be available.")
  }

  return { input, submitButton }
}

function messageCreatedStatusEvent(
  conversationId: string,
  turnId: string,
  messageId: string,
  sequence = 1,
) {
  return {
    statusEventId: `evt_${messageId}`,
    conversationId,
    turnId,
    messageId,
    eventType: "message.created" as const,
    sequence,
    interactionState: "thinking" as const,
    messageStatus: "published" as const,
    createdAt: "2026-04-23T09:00:00.000Z",
  }
}

function emitTextRun(
  handlers: { onEvent: (event: Record<string, unknown>) => void },
  input: {
    conversationId: string
    turnId: string
    messageId: string
    content: string
    startedAt: number
  },
): void {
  handlers.onEvent({
    type: "RUN_STARTED",
    threadId: input.conversationId,
    runId: input.turnId,
    timestamp: input.startedAt,
  })
  handlers.onEvent({
    type: "TEXT_MESSAGE_START",
    messageId: input.messageId,
    role: "assistant",
    timestamp: input.startedAt + 1_000,
  })
  handlers.onEvent({
    type: "TEXT_MESSAGE_CONTENT",
    messageId: input.messageId,
    delta: input.content,
    timestamp: input.startedAt + 2_000,
  })
  handlers.onEvent({
    type: "TEXT_MESSAGE_END",
    messageId: input.messageId,
    timestamp: input.startedAt + 3_000,
  })
  handlers.onEvent({
    type: "RUN_FINISHED",
    threadId: input.conversationId,
    runId: input.turnId,
    reason: "completed",
    timestamp: input.startedAt + 4_000,
  })
}

function emitCandidateLayoutRun(
  handlers: { onEvent: (event: Record<string, unknown>) => void },
  input: {
    conversationId: string
    turnId: string
    messageId: string
    startedAt: number
  },
): void {
  handlers.onEvent({
    type: "RUN_STARTED",
    threadId: input.conversationId,
    runId: input.turnId,
    timestamp: input.startedAt,
  })
  handlers.onEvent({
    type: "ACTIVITY_SNAPSHOT",
    messageId: input.messageId,
    activityType: "conversation.ui.layout-tree",
    timestamp: input.startedAt + 1_000,
    content: {
      contract: "conversation.ui.layout-tree@1",
      blockId: "restore_options",
      ui: {
        id: "restore_options_root",
        type: "stack",
        props: { gap: "lg" },
        children: [
          {
            id: "restore_options_heading",
            type: "heading",
            props: {
              level: 2,
              text: "Restore options",
            },
          },
          {
            id: "option_a",
            type: "card",
            props: {
              title: "Option A: Restore by exporting the target table",
            },
            children: [
              {
                id: "option_a_summary",
                type: "paragraph",
                props: {
                  text: "Recommended option.",
                },
              },
              {
                id: "option_a_scope",
                type: "kv-list",
                props: {
                  items: [
                    { label: "Restore scope", value: "Database-level" },
                    { label: "RPO / RTO", value: "< 2 min / 1.5 h" },
                  ],
                },
              },
              {
                id: "option_a_actions",
                type: "action-row",
                props: {
                  actionIds: ["confirm_option_a"],
                },
              },
            ],
          },
        ],
      },
      actions: [
        {
          id: "confirm_option_a",
          kind: "submit_message",
          label: "Confirm restore plan",
          style: "primary",
          payload: {
            type: "candidate_selection",
            candidate_option_id: "option_a",
            selection: "confirm",
          },
        },
      ],
      meta: {
        intent: "clarification",
        reasoningTraceId: "trace_restore_001",
      },
    },
  })
  handlers.onEvent({
    type: "STATE_SNAPSHOT",
    timestamp: input.startedAt + 2_000,
    state: {
      interaction: {
        status: "clarifying",
      },
      selection: {
        required: true,
      },
    },
  })
}

describe("ChatPanel", () => {
  beforeEach(() => {
    localStorage.clear()
    resetConversationStore()

    listConversationsMock.mockResolvedValue([])
    searchConversationsMock.mockResolvedValue([])
    listConversationEventsMock.mockResolvedValue({
      events: [],
      nextCursor: null,
      hasMore: false,
      latestSequence: 0,
      recommendedPollIntervalMs: 1000,
      interactionState: "completed",
    })
    startConversationRunMock.mockReset()
    startConversationRunMock.mockResolvedValue(undefined)
  })

  afterEach(async () => {
    await flushConversationRefresh()
    vi.clearAllMocks()
    localStorage.clear()
    resetConversationStore()
  })

  it("hides the conversation detail title area while keeping the message body visible", () => {
    useConversationStore.setState({
      bootstrapped: true,
      selectedWorkspace: {
        kind: "conversation",
        conversationId: "conv_hidden_header",
      },
      detailsByConversationId: {
        conv_hidden_header: {
          conversationId: "conv_hidden_header",
          title: "Hidden conversation title",
          displaySummary: "Hidden conversation summary",
          createdAt: "2026-04-23T09:00:00.000Z",
          updatedAt: "2026-04-23T09:00:00.000Z",
          status: "active",
        },
      },
      messagesByConversationId: {
        conv_hidden_header: [
          {
            messageId: "msg_visible_body",
            conversationId: "conv_hidden_header",
            role: "assistant",
            contentType: "text",
            content: "Visible assistant body.",
            createdAt: "2026-04-23T09:00:20.000Z",
            status: "responded",
          },
        ],
      },
    })

    render(<ChatPanel fillHeight />)

    const contentSection = screen.getByText("Visible assistant body.").closest("section")

    expect(contentSection).not.toHaveClass("bg-background")
    expect(screen.getByText("Visible assistant body.")).toBeInTheDocument()
    expect(screen.queryByText("Hidden conversation title")).not.toBeInTheDocument()
    expect(screen.queryByText("Hidden conversation summary")).not.toBeInTheDocument()
  })

  it("continues the same conversation after confirming a candidate option", async () => {
    const user = userEvent.setup()

    createConversationMock.mockResolvedValue({
      conversation: {
        conversationId: "conv_restore_001",
        title: "Restore order database",
        createdAt: "2026-04-22T10:00:00.000Z",
        updatedAt: "2026-04-22T10:00:00.000Z",
        interactionState: "thinking",
        activeTurnId: "turn_restore_001",
      },
      message: {
        messageId: "msg_user_001",
        conversationId: "conv_restore_001",
        turnId: "turn_restore_001",
        role: "user",
        contentType: "text",
        content: "Help me restore the order database.",
        createdAt: "2026-04-22T10:00:00.000Z",
        status: "published",
      },
      statusEvent: messageCreatedStatusEvent("conv_restore_001", "turn_restore_001", "msg_user_001"),
      nextPollAfterMs: 0,
    })

    startConversationRunMock.mockImplementation(async (input, handlers) => {
      if (input.runId === "turn_restore_001") {
        emitCandidateLayoutRun(handlers, {
          conversationId: "conv_restore_001",
          turnId: "turn_restore_001",
          messageId: "msg_candidate_001",
          startedAt: Date.parse("2026-04-22T10:00:20.000Z"),
        })
        return
      }

      if (input.runId === "turn_selection_001") {
        emitTextRun(handlers, {
          conversationId: "conv_restore_001",
          turnId: "turn_selection_001",
          messageId: "msg_assistant_002",
          content: "Confirmed. Generating the final restore plan.",
          startedAt: Date.parse("2026-04-22T10:00:40.000Z"),
        })
      }
    })

    sendMessageMock.mockResolvedValue({
      conversation: {
        conversationId: "conv_restore_001",
        title: "Restore order database",
        createdAt: "2026-04-22T10:00:00.000Z",
        updatedAt: "2026-04-22T10:00:30.000Z",
        interactionState: "thinking",
        activeTurnId: "turn_selection_001",
      },
      message: {
        messageId: "msg_user_selection_001",
        conversationId: "conv_restore_001",
        turnId: "turn_selection_001",
        role: "user",
        contentType: "text",
        content: "Confirm the recommended restore option.",
        createdAt: "2026-04-22T10:00:30.000Z",
        status: "published",
      },
      statusEvent: messageCreatedStatusEvent(
        "conv_restore_001",
        "turn_selection_001",
        "msg_user_selection_001",
        3,
      ),
      nextPollAfterMs: 0,
    })

    await useConversationStore.getState().hydrate()

    const { container } = render(<ChatPanel fillHeight />)
    const { input, submitButton } = getComposerElements(container)

    await user.type(input, "Help me restore the order database.")
    await user.click(submitButton)

    expect(createConversationMock).toHaveBeenCalledTimes(1)

    await flushConversationRefresh()

    expect(await screen.findByText("Restore options")).toBeInTheDocument()

    await user.click(screen.getByRole("button", { name: "Confirm restore plan" }))

    expect(sendMessageMock).toHaveBeenLastCalledWith(
      "conv_restore_001",
      expect.objectContaining({
        type: "candidate_selection",
        candidateOptionId: "option_a",
        selection: "confirm",
      }),
    )

    await flushConversationRefresh()

    expect(await screen.findByText("Confirmed. Generating the final restore plan.")).toBeInTheDocument()
  })

  it("completes a plain-text two-turn loop in the same conversation", async () => {
    const user = userEvent.setup()

    createConversationMock.mockResolvedValue({
      conversation: {
        conversationId: "conv_text_loop",
        title: "Text loop",
        createdAt: "2026-04-23T09:00:00.000Z",
        updatedAt: "2026-04-23T09:00:00.000Z",
        interactionState: "thinking",
        activeTurnId: "turn_text_001",
      },
      message: {
        messageId: "msg_user_001",
        conversationId: "conv_text_loop",
        turnId: "turn_text_001",
        role: "user",
        contentType: "text",
        content: "Help me restore the order database.",
        createdAt: "2026-04-23T09:00:00.000Z",
        status: "published",
      },
      statusEvent: messageCreatedStatusEvent("conv_text_loop", "turn_text_001", "msg_user_001"),
      nextPollAfterMs: 0,
    })

    startConversationRunMock.mockImplementation(async (input, handlers) => {
      if (input.runId === "turn_text_001") {
        emitTextRun(handlers, {
          conversationId: "conv_text_loop",
          turnId: "turn_text_001",
          messageId: "msg_assistant_001",
          content: "I will inspect the latest restore points first.",
          startedAt: Date.parse("2026-04-23T09:00:20.000Z"),
        })
        return
      }

      if (input.runId === "turn_text_002") {
        emitTextRun(handlers, {
          conversationId: "conv_text_loop",
          turnId: "turn_text_002",
          messageId: "msg_assistant_002",
          content: "I will compare the restore points from yesterday afternoon.",
          startedAt: Date.parse("2026-04-23T09:01:20.000Z"),
        })
      }
    })

    sendMessageMock.mockResolvedValue({
      conversation: {
        conversationId: "conv_text_loop",
        title: "Text loop",
        createdAt: "2026-04-23T09:00:00.000Z",
        updatedAt: "2026-04-23T09:01:00.000Z",
        interactionState: "thinking",
        activeTurnId: "turn_text_002",
      },
      message: {
        messageId: "msg_user_002",
        conversationId: "conv_text_loop",
        turnId: "turn_text_002",
        role: "user",
        contentType: "text",
        content: "Restore to yesterday afternoon.",
        createdAt: "2026-04-23T09:01:00.000Z",
        status: "published",
      },
      statusEvent: messageCreatedStatusEvent("conv_text_loop", "turn_text_002", "msg_user_002", 4),
      nextPollAfterMs: 0,
    })

    await useConversationStore.getState().hydrate()

    const { container } = render(<ChatPanel fillHeight />)
    const { input, submitButton } = getComposerElements(container)

    await user.type(input, "Help me restore the order database.")
    await user.click(submitButton)

    expect(createConversationMock).toHaveBeenCalledTimes(1)

    await flushConversationRefresh()

    expect(await screen.findByText("I will inspect the latest restore points first.")).toBeInTheDocument()

    const refreshedComposer = getComposerElements(container)

    await user.type(refreshedComposer.input, "Restore to yesterday afternoon.")
    await user.click(refreshedComposer.submitButton)

    expect(sendMessageMock).toHaveBeenLastCalledWith(
      "conv_text_loop",
      expect.objectContaining({
        type: "user_message",
        content: "Restore to yesterday afternoon.",
      }),
    )

    await flushConversationRefresh()

    expect(await screen.findByText("I will compare the restore points from yesterday afternoon.")).toBeInTheDocument()
  })

  it("submits fallback retry messages from layout-tree error cards and surfaces missing refs", async () => {
    const user = userEvent.setup()

    sendMessageMock.mockResolvedValue({
      conversation: {
        conversationId: "conv_visible_error",
        title: "Visible error",
        createdAt: "2026-04-24T09:31:45.732Z",
        updatedAt: "2026-04-24T09:31:46.867Z",
        interactionState: "thinking",
        activeTurnId: "turn_visible_error_retry",
      },
      message: {
        messageId: "msg_user_retry_001",
        conversationId: "conv_visible_error",
        turnId: "turn_visible_error_retry",
        role: "user",
        contentType: "text",
        content: "Retry with wider window",
        createdAt: "2026-04-24T09:32:10.000Z",
        status: "published",
      },
      statusEvent: messageCreatedStatusEvent(
        "conv_visible_error",
        "turn_visible_error_retry",
        "msg_user_retry_001",
      ),
      nextPollAfterMs: 0,
    })

    useConversationStore.setState({
      bootstrapped: true,
      selectedWorkspace: {
        kind: "conversation",
        conversationId: "conv_visible_error",
      },
      detailsByConversationId: {
        conv_visible_error: {
          conversationId: "conv_visible_error",
          title: "Visible error",
          createdAt: "2026-04-24T09:31:45.732Z",
          updatedAt: "2026-04-24T09:31:46.867Z",
          interactionState: "error",
        },
      },
      messagesByConversationId: {
        conv_visible_error: [
          {
            messageId: "msg_error_layout_001",
            conversationId: "conv_visible_error",
            turnId: "turn_visible_error_001",
            role: "assistant",
            contentType: "rich_content",
            content: "The requested operation cannot continue without a valid restore point.",
            createdAt: "2026-04-24T09:31:46.867Z",
            status: "responded",
            richPayload: {
              kind: "layout_tree",
              data: {
                activity: {
                  contract: "conversation.ui.layout-tree@1",
                  blockId: "visible_error_954",
                  ui: {
                    id: "visible_error_root",
                    type: "stack",
                    props: {
                      gap: "lg",
                    },
                    children: [
                      {
                        type: "callout",
                        props: {
                          title: "Restore point unavailable",
                          text: "The requested operation cannot continue without a valid restore point.",
                          tone: "error",
                        },
                      },
                      {
                        type: "action-row",
                        props: {
                          actionIds: ["retry_restore_search", "open_restore_runbook"],
                        },
                      },
                    ],
                  },
                  actions: [
                    {
                      id: "retry_restore_search",
                      kind: "submit_message",
                      label: "Retry with wider window",
                      style: "primary",
                      payload: {
                        action: "retry_restore_search",
                      },
                    },
                    {
                      id: "open_restore_runbook",
                      kind: "open_ref",
                      label: "Open troubleshooting runbook",
                      payload: {
                        ref_id: "restore-runbook-visible-error",
                      },
                    },
                  ],
                  meta: {
                    intent: "error",
                    terminal: true,
                  },
                },
                stateSnapshot: {
                  interaction: {
                    status: "error",
                  },
                },
              },
            },
          },
        ],
      },
    })

    render(<ChatPanel fillHeight />)

    await user.click(screen.getByRole("button", { name: "Retry with wider window" }))

    expect(sendMessageMock).toHaveBeenCalledWith(
      "conv_visible_error",
      expect.objectContaining({
        type: "user_message",
        content: "Retry with wider window",
      }),
    )

    await user.click(screen.getByRole("button", { name: "Open troubleshooting runbook" }))

    expect(
      await screen.findByText(
        "Referenced content was not returned with the message and cannot be opened yet: restore-runbook-visible-error",
      ),
    ).toBeInTheDocument()
  })
})
