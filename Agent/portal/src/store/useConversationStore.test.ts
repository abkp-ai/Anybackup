import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

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

import { conversationDraftKeyForConversation } from "@/lib/conversation-draft"
import { mapConversationStatusEventRecord } from "@/services/conversation-response-adapter"
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

async function flushMicrotasks(): Promise<void> {
  await Promise.resolve()
  await new Promise((resolve) => setTimeout(resolve, 0))
}

function acceptedStatusEvent(conversationId: string, turnId: string, messageId: string) {
  return {
    statusEventId: `evt_${messageId}`,
    conversationId,
    turnId,
    messageId,
    eventType: "message.created" as const,
    sequence: 1,
    interactionState: "thinking" as const,
    messageStatus: "published" as const,
    createdAt: "2026-05-13T10:00:00.000Z",
  }
}

describe("useConversationStore", () => {
  beforeEach(() => {
    localStorage.clear()
    resetConversationStore()

    createConversationMock.mockReset()
    getConversationDetailMock.mockReset()
    getConversationMessagesMock.mockReset()
    listConversationEventsMock.mockReset()
    listConversationsMock.mockReset()
    searchConversationsMock.mockReset()
    sendMessageMock.mockReset()
    startConversationRunMock.mockReset()

    listConversationsMock.mockResolvedValue([])
    searchConversationsMock.mockResolvedValue([])
    getConversationDetailMock.mockResolvedValue({
      conversationId: "conv_restore_001",
      title: "Restore",
      createdAt: "2026-05-13T10:00:00.000Z",
      updatedAt: "2026-05-13T10:00:00.000Z",
      interactionState: "idle",
    })
    getConversationMessagesMock.mockResolvedValue([])
    listConversationEventsMock.mockResolvedValue({
      events: [],
      nextCursor: null,
      hasMore: false,
      latestSequence: 0,
      recommendedPollIntervalMs: 1000,
      interactionState: "completed",
    })
    startConversationRunMock.mockResolvedValue(undefined)
  })

  afterEach(async () => {
    localStorage.clear()
    resetConversationStore()
    vi.clearAllMocks()
  })

  it("creates a formal conversation and starts the run stream on first send", async () => {
    startConversationRunMock.mockImplementation(() => new Promise(() => undefined))

    createConversationMock.mockResolvedValue({
      conversation: {
        conversationId: "conv_restore_001",
        title: "Restore",
        createdAt: "2026-05-13T10:00:00.000Z",
        updatedAt: "2026-05-13T10:00:00.000Z",
        interactionState: "thinking",
        activeTurnId: "turn_001",
      },
      message: {
        messageId: "msg_user_001",
        conversationId: "conv_restore_001",
        turnId: "turn_001",
        role: "user",
        contentType: "text",
        content: "help me restore the order database",
        createdAt: "2026-05-13T10:00:00.000Z",
        status: "published",
      },
      statusEvent: acceptedStatusEvent("conv_restore_001", "turn_001", "msg_user_001"),
      nextPollAfterMs: 0,
    })

    await useConversationStore.getState().hydrate()
    useConversationStore.getState().setDraft("help me restore the order database")

    await useConversationStore.getState().submitComposerMessage()
    await flushMicrotasks()

    expect(createConversationMock).toHaveBeenCalledTimes(1)
    expect(startConversationRunMock).toHaveBeenCalledWith(
      expect.objectContaining({
        threadId: "conv_restore_001",
        runId: "turn_001",
        messages: [{ role: "user", content: "help me restore the order database" }],
      }),
      expect.any(Object),
      expect.any(AbortSignal),
    )

    const state = useConversationStore.getState()
    expect(state.selectedWorkspace).toEqual({
      kind: "conversation",
      conversationId: "conv_restore_001",
    })
    expect(state.pendingTurnByConversationId.conv_restore_001).toEqual({
      state: "thinking",
      turnId: "turn_001",
    })
  })

  it("still starts the run stream when create conversation only returns turnId without thinking flags", async () => {
    startConversationRunMock.mockImplementation(() => new Promise(() => undefined))

    createConversationMock.mockResolvedValue({
      conversation: {
        conversationId: "conv_restore_implicit_001",
        title: "Restore",
        createdAt: "2026-05-13T10:00:00.000Z",
        updatedAt: "2026-05-13T10:00:00.000Z",
      },
      message: {
        messageId: "msg_user_implicit_001",
        conversationId: "conv_restore_implicit_001",
        turnId: "turn_implicit_001",
        role: "user",
        contentType: "text",
        content: "help me restore the order database",
        createdAt: "2026-05-13T10:00:00.000Z",
        status: "published",
      },
      statusEvent: {
        statusEventId: "evt_msg_user_implicit_001",
        conversationId: "conv_restore_implicit_001",
        turnId: "turn_implicit_001",
        messageId: "msg_user_implicit_001",
        eventType: "message.created" as const,
        sequence: 1,
        messageStatus: "published" as const,
        createdAt: "2026-05-13T10:00:00.000Z",
      },
      nextPollAfterMs: 0,
    })

    await useConversationStore.getState().hydrate()
    useConversationStore.getState().setDraft("help me restore the order database")

    await useConversationStore.getState().submitComposerMessage()
    await flushMicrotasks()

    expect(startConversationRunMock).toHaveBeenCalledWith(
      expect.objectContaining({
        threadId: "conv_restore_implicit_001",
        runId: "turn_implicit_001",
        messages: [{ role: "user", content: "help me restore the order database" }],
      }),
      expect.any(Object),
      expect.any(AbortSignal),
    )

    const state = useConversationStore.getState()
    expect(state.detailsByConversationId.conv_restore_implicit_001).toEqual(
      expect.objectContaining({
        interactionState: "thinking",
        activeTurnId: "turn_implicit_001",
      }),
    )
    expect(state.pendingTurnByConversationId.conv_restore_implicit_001).toEqual({
      state: "thinking",
      turnId: "turn_implicit_001",
    })
  })

  it("does not show a pending turn for a stale user-only historical conversation", async () => {
    const staleTime = new Date(Date.now() - 10 * 60 * 1000).toISOString()
    getConversationDetailMock.mockResolvedValueOnce({
      conversationId: "conv_stale_user_001",
      title: "Stale user only",
      createdAt: staleTime,
      updatedAt: staleTime,
      interactionState: "executing",
      activeTurnId: "turn_stale_user_001",
    })
    getConversationMessagesMock.mockResolvedValueOnce([
      {
        messageId: "msg_user_stale_001",
        conversationId: "conv_stale_user_001",
        turnId: "turn_stale_user_001",
        role: "user",
        contentType: "text",
        content: "restore order database",
        createdAt: staleTime,
        status: "published",
      },
    ])

    await useConversationStore.getState().selectConversation("conv_stale_user_001")
    await flushMicrotasks()

    expect(startConversationRunMock).not.toHaveBeenCalled()
    const state = useConversationStore.getState()
    expect(state.pendingTurnByConversationId.conv_stale_user_001).toEqual({ state: "idle" })
    expect(state.pendingTurnStartedAtMsByConversationId.conv_stale_user_001).toBeUndefined()
  })

  it("does not start a run stream for a settled historical conversation with stale executing state", async () => {
    getConversationDetailMock.mockResolvedValueOnce({
      conversationId: "conv_hist_001",
      title: "Historical",
      createdAt: "2026-05-13T10:00:00.000Z",
      updatedAt: "2026-05-13T10:05:00.000Z",
      interactionState: "executing",
      activeTurnId: "turn_hist_001",
    })
    getConversationMessagesMock.mockResolvedValueOnce([
      {
        messageId: "msg_user_hist_001",
        conversationId: "conv_hist_001",
        turnId: "turn_hist_001",
        role: "user",
        contentType: "text",
        content: "show restore status",
        createdAt: "2026-05-13T10:00:00.000Z",
        status: "published",
      },
      {
        messageId: "msg_assistant_hist_001",
        conversationId: "conv_hist_001",
        turnId: "turn_hist_001",
        role: "assistant",
        contentType: "layout_tree",
        content: "",
        createdAt: "2026-05-13T10:05:00.000Z",
        status: "responded",
        richPayload: {
          kind: "layout_tree",
          data: {
            activity: {
              blockId: "restore_status_001",
            },
            stateSnapshot: {
              interaction: {
                status: "executing",
              },
            },
          },
        },
      },
    ])

    await useConversationStore.getState().selectConversation("conv_hist_001")
    await flushMicrotasks()

    expect(startConversationRunMock).not.toHaveBeenCalled()
    expect(listConversationEventsMock).toHaveBeenCalledWith("conv_hist_001", {
      cursor: null,
      limit: 100,
    })

    const state = useConversationStore.getState()
    expect(state.pendingTurnByConversationId.conv_hist_001).toEqual({ state: "idle" })
    expect(state.detailsByConversationId.conv_hist_001).toEqual(
      expect.objectContaining({
        interactionState: "completed",
        activeTurnId: undefined,
      }),
    )
  })

  it("materializes assistant content from AG-UI wire events stored in status event payload", async () => {
    getConversationDetailMock.mockResolvedValueOnce({
      conversationId: "conv_wire_001",
      title: "Wire events",
      createdAt: "2026-05-13T10:00:00.000Z",
      updatedAt: "2026-05-13T10:05:00.000Z",
      interactionState: "completed",
    })
    getConversationMessagesMock.mockResolvedValueOnce([
      {
        messageId: "msg_user_wire_001",
        conversationId: "conv_wire_001",
        turnId: "turn_wire_001",
        role: "user",
        contentType: "text",
        content: "show thought about recovery",
        createdAt: "2026-05-13T10:00:00.000Z",
        status: "published",
      },
    ])
    const wireApiEvents = [
      {
        status_event_id: "evt_wire_text_start",
        conversation_id: "conv_wire_001",
        turn_id: "turn_wire_001",
        message_id: "msg_user_wire_001",
        event_type: "TEXT_MESSAGE_START",
        sequence: 2,
        occurred_at: "2026-05-13T10:01:00.000Z",
        payload: {
          type: "TEXT_MESSAGE_START",
          messageId: "msg_assistant_wire_001",
          role: "assistant",
          timestamp: Date.parse("2026-05-13T10:01:00.000Z"),
        },
      },
      {
        status_event_id: "evt_wire_text_content",
        conversation_id: "conv_wire_001",
        turn_id: "turn_wire_001",
        message_id: "msg_user_wire_001",
        event_type: "TEXT_MESSAGE_CONTENT",
        sequence: 3,
        occurred_at: "2026-05-13T10:01:01.000Z",
        payload: {
          type: "TEXT_MESSAGE_CONTENT",
          messageId: "msg_assistant_wire_001",
          delta: "Visible reasoning summary for recovery.",
          timestamp: Date.parse("2026-05-13T10:01:01.000Z"),
        },
      },
      {
        status_event_id: "evt_wire_text_end",
        conversation_id: "conv_wire_001",
        turn_id: "turn_wire_001",
        message_id: "msg_user_wire_001",
        event_type: "TEXT_MESSAGE_END",
        sequence: 4,
        occurred_at: "2026-05-13T10:01:02.000Z",
        payload: {
          type: "TEXT_MESSAGE_END",
          messageId: "msg_assistant_wire_001",
          timestamp: Date.parse("2026-05-13T10:01:02.000Z"),
        },
      },
      {
        status_event_id: "evt_wire_run_finished",
        conversation_id: "conv_wire_001",
        turn_id: "turn_wire_001",
        message_id: "msg_user_wire_001",
        event_type: "RUN_FINISHED",
        sequence: 5,
        occurred_at: "2026-05-13T10:01:03.000Z",
        payload: {
          type: "RUN_FINISHED",
          threadId: "conv_wire_001",
          runId: "turn_wire_001",
          reason: "completed",
          timestamp: Date.parse("2026-05-13T10:01:03.000Z"),
        },
      },
    ] as const

    listConversationEventsMock.mockResolvedValueOnce({
      events: wireApiEvents.map((event) => mapConversationStatusEventRecord(event)),
      nextCursor: null,
      hasMore: false,
      latestSequence: 5,
      recommendedPollIntervalMs: 1000,
      interactionState: "completed",
    })

    await useConversationStore.getState().selectConversation("conv_wire_001")
    await flushMicrotasks()

    expect(startConversationRunMock).not.toHaveBeenCalled()

    const assistantMessage = useConversationStore
      .getState()
      .messagesByConversationId.conv_wire_001?.find((message) => message.role === "assistant")

    expect(assistantMessage?.content).toBe("Visible reasoning summary for recovery.")
    expect(assistantMessage?.status).toBe("responded")
  })

  it("paginates historical events until hasMore is false", async () => {
    getConversationDetailMock.mockResolvedValueOnce({
      conversationId: "conv_events_page_001",
      title: "Paged events",
      createdAt: "2026-05-13T10:00:00.000Z",
      updatedAt: "2026-05-13T10:05:00.000Z",
      interactionState: "completed",
    })
    getConversationMessagesMock.mockResolvedValueOnce([
      {
        messageId: "msg_user_page_001",
        conversationId: "conv_events_page_001",
        turnId: "turn_page_001",
        role: "user",
        contentType: "text",
        content: "show restore status",
        createdAt: "2026-05-13T10:00:00.000Z",
        status: "published",
      },
    ])
    listConversationEventsMock
      .mockResolvedValueOnce({
        events: [],
        nextCursor: "cursor_page_2",
        hasMore: true,
        latestSequence: 1,
        recommendedPollIntervalMs: 1000,
        interactionState: "completed",
      })
      .mockResolvedValueOnce({
        events: [
          {
            statusEventId: "evt_assistant_page_001",
            conversationId: "conv_events_page_001",
            turnId: "turn_page_001",
            messageId: "msg_assistant_page_001",
            eventType: "message.updated",
            sequence: 2,
            interactionState: "completed",
            messageStatus: "responded",
            createdAt: "2026-05-13T10:05:00.000Z",
            message: {
              messageId: "msg_assistant_page_001",
              conversationId: "conv_events_page_001",
              turnId: "turn_page_001",
              role: "assistant",
              contentType: "text",
              content: "Restore point is ready.",
              createdAt: "2026-05-13T10:05:00.000Z",
              status: "responded",
            },
          },
        ],
        nextCursor: null,
        hasMore: false,
        latestSequence: 2,
        recommendedPollIntervalMs: 1000,
        interactionState: "completed",
      })

    await useConversationStore.getState().selectConversation("conv_events_page_001")
    await flushMicrotasks()

    expect(listConversationEventsMock).toHaveBeenNthCalledWith(1, "conv_events_page_001", {
      cursor: null,
      limit: 100,
    })
    expect(listConversationEventsMock).toHaveBeenNthCalledWith(2, "conv_events_page_001", {
      cursor: "cursor_page_2",
      limit: 100,
    })
    expect(startConversationRunMock).not.toHaveBeenCalled()

    const assistantMessage = useConversationStore
      .getState()
      .messagesByConversationId.conv_events_page_001?.find((message) => message.role === "assistant")
    expect(assistantMessage?.content).toBe("Restore point is ready.")
  })

  it("replays a historical run when assistant content is missing but the turn is not live", async () => {
    getConversationDetailMock.mockResolvedValueOnce({
      conversationId: "conv_replay_001",
      title: "Replay",
      createdAt: "2026-05-13T10:00:00.000Z",
      updatedAt: "2026-05-13T10:01:00.000Z",
      interactionState: "clarifying",
      activeTurnId: "turn_replay_001",
    })
    getConversationMessagesMock.mockResolvedValueOnce([
      {
        messageId: "msg_user_replay_001",
        conversationId: "conv_replay_001",
        turnId: "turn_replay_001",
        role: "user",
        contentType: "text",
        content: "show thought chain",
        createdAt: "2026-05-13T10:00:00.000Z",
        status: "published",
      },
      {
        messageId: "msg_assistant_replay_001",
        conversationId: "conv_replay_001",
        turnId: "turn_replay_001",
        role: "assistant",
        contentType: "layout_tree",
        content: "",
        createdAt: "2026-05-13T10:01:00.000Z",
        status: "published",
      },
    ])
    listConversationEventsMock.mockResolvedValue({
      events: [],
      nextCursor: null,
      hasMore: false,
      latestSequence: 0,
      recommendedPollIntervalMs: 1000,
      interactionState: "clarifying",
    })

    startConversationRunMock.mockImplementation(async (_input, handlers) => {
      handlers.onEvent({
        type: "TEXT_MESSAGE_START",
        messageId: "msg_assistant_replay_001",
        role: "assistant",
        timestamp: Date.parse("2026-05-13T10:01:01.000Z"),
      })
      handlers.onEvent({
        type: "TEXT_MESSAGE_CONTENT",
        messageId: "msg_assistant_replay_001",
        delta: "Recovered assistant reply.",
        timestamp: Date.parse("2026-05-13T10:01:02.000Z"),
      })
      handlers.onEvent({
        type: "TEXT_MESSAGE_END",
        messageId: "msg_assistant_replay_001",
        timestamp: Date.parse("2026-05-13T10:01:03.000Z"),
      })
      handlers.onEvent({
        type: "RUN_FINISHED",
        threadId: "conv_replay_001",
        runId: "turn_replay_001",
        reason: "completed",
        timestamp: Date.parse("2026-05-13T10:01:04.000Z"),
      })
    })

    await useConversationStore.getState().selectConversation("conv_replay_001")
    await flushMicrotasks()

    expect(startConversationRunMock).toHaveBeenCalledWith(
      expect.objectContaining({
        threadId: "conv_replay_001",
        runId: "turn_replay_001",
      }),
      expect.any(Object),
      expect.any(AbortSignal),
    )

    const state = useConversationStore.getState()
    expect(state.pendingTurnByConversationId.conv_replay_001).toEqual({ state: "idle" })
    expect(state.messagesByConversationId.conv_replay_001?.map((message) => message.content)).toContain(
      "Recovered assistant reply.",
    )
  })

  it("starts a run stream when opening a conversation with an active turn", async () => {
    const now = new Date().toISOString()
    getConversationDetailMock.mockResolvedValueOnce({
      conversationId: "conv_active_001",
      title: "Active conversation",
      createdAt: now,
      updatedAt: now,
      interactionState: "executing",
      activeTurnId: "turn_active_001",
    })
    getConversationMessagesMock.mockResolvedValueOnce([
      {
        messageId: "msg_user_active_001",
        conversationId: "conv_active_001",
        turnId: "turn_active_001",
        role: "user",
        contentType: "text",
        content: "show active recovery status",
        createdAt: now,
        status: "published",
      },
    ])
    listConversationEventsMock.mockResolvedValueOnce({
      events: [],
      nextCursor: null,
      hasMore: false,
      latestSequence: 0,
      recommendedPollIntervalMs: 1000,
      interactionState: "executing",
    })

    await useConversationStore.getState().selectConversation("conv_active_001")
    await flushMicrotasks()

    expect(startConversationRunMock).toHaveBeenCalledWith(
      expect.objectContaining({
        threadId: "conv_active_001",
        runId: "turn_active_001",
        messages: [{ role: "user", content: "show active recovery status" }],
      }),
      expect.any(Object),
      expect.any(AbortSignal),
    )
  })

  it("updates the conversation with streamed text events and clears pending state on RUN_FINISHED", async () => {
    sendMessageMock.mockResolvedValue({
      conversation: {
        conversationId: "conv_stream_001",
        title: "Stream",
        createdAt: "2026-05-13T10:00:00.000Z",
        updatedAt: "2026-05-13T10:00:00.000Z",
        interactionState: "thinking",
        activeTurnId: "turn_stream_001",
      },
      message: {
        messageId: "msg_user_stream_001",
        conversationId: "conv_stream_001",
        turnId: "turn_stream_001",
        role: "user",
        contentType: "text",
        content: "check the latest restore point",
        createdAt: "2026-05-13T10:00:00.000Z",
        status: "published",
      },
      statusEvent: acceptedStatusEvent("conv_stream_001", "turn_stream_001", "msg_user_stream_001"),
      nextPollAfterMs: 0,
    })

    startConversationRunMock.mockImplementation(async (_input, handlers) => {
      handlers.onEvent({
        type: "RUN_STARTED",
        threadId: "conv_stream_001",
        runId: "turn_stream_001",
        timestamp: Date.parse("2026-05-13T10:00:01.000Z"),
      })
      handlers.onEvent({
        type: "TEXT_MESSAGE_START",
        messageId: "msg_assistant_stream_001",
        role: "assistant",
        timestamp: Date.parse("2026-05-13T10:00:02.000Z"),
      })
      handlers.onEvent({
        type: "TEXT_MESSAGE_CONTENT",
        messageId: "msg_assistant_stream_001",
        delta: "I found the latest safe restore point.",
        timestamp: Date.parse("2026-05-13T10:00:03.000Z"),
      })
      handlers.onEvent({
        type: "TEXT_MESSAGE_END",
        messageId: "msg_assistant_stream_001",
        timestamp: Date.parse("2026-05-13T10:00:04.000Z"),
      })
      handlers.onEvent({
        type: "RUN_FINISHED",
        threadId: "conv_stream_001",
        runId: "turn_stream_001",
        reason: "completed",
        timestamp: Date.parse("2026-05-13T10:00:05.000Z"),
      })
    })

    useConversationStore.setState({
      bootstrapped: true,
      selectedWorkspace: {
        kind: "conversation",
        conversationId: "conv_stream_001",
      },
      detailsByConversationId: {
        conv_stream_001: {
          conversationId: "conv_stream_001",
          title: "Stream",
          createdAt: "2026-05-13T10:00:00.000Z",
          updatedAt: "2026-05-13T10:00:00.000Z",
          interactionState: "idle",
        },
      },
      messagesByConversationId: {
        conv_stream_001: [],
      },
      draftsByKey: {
        [conversationDraftKeyForConversation("conv_stream_001")]: "check the latest restore point",
      },
    })

    await useConversationStore.getState().submitComposerMessage()
    await flushMicrotasks()

    const state = useConversationStore.getState()
    expect(state.messagesByConversationId.conv_stream_001?.map((message) => message.content)).toEqual([
      "check the latest restore point",
      "I found the latest safe restore point.",
    ])
    expect(state.pendingTurnByConversationId.conv_stream_001).toEqual({ state: "idle" })
    expect(state.detailsByConversationId.conv_stream_001?.interactionState).toBe("completed")
    expect(state.detailsByConversationId.conv_stream_001?.activeTurnId).toBeUndefined()
  })

  it("maps streamed layout-tree events into rich content messages", async () => {
    sendMessageMock.mockResolvedValue({
      conversation: {
        conversationId: "conv_layout_001",
        title: "Layout",
        createdAt: "2026-05-13T10:00:00.000Z",
        updatedAt: "2026-05-13T10:00:00.000Z",
        interactionState: "thinking",
        activeTurnId: "turn_layout_001",
      },
      message: {
        messageId: "msg_user_layout_001",
        conversationId: "conv_layout_001",
        turnId: "turn_layout_001",
        role: "user",
        contentType: "text",
        content: "compare candidate plans",
        createdAt: "2026-05-13T10:00:00.000Z",
        status: "published",
      },
      statusEvent: acceptedStatusEvent("conv_layout_001", "turn_layout_001", "msg_user_layout_001"),
      nextPollAfterMs: 0,
    })

    startConversationRunMock.mockImplementation(async (_input, handlers) => {
      handlers.onEvent({
        type: "ACTIVITY_SNAPSHOT",
        messageId: "msg_layout_001",
        activityType: "conversation.ui.layout-tree",
        timestamp: Date.parse("2026-05-13T10:00:02.000Z"),
        content: {
          contract: "conversation.ui.layout-tree@1",
          blockId: "candidate_compare_001",
          ui: {
            id: "root",
            type: "stack",
            children: [
              {
                id: "heading",
                type: "heading",
                props: {
                  text: "Candidate comparison",
                  level: 2,
                },
              },
            ],
          },
        },
      })
      handlers.onEvent({
        type: "STATE_SNAPSHOT",
        timestamp: Date.parse("2026-05-13T10:00:03.000Z"),
        state: {
          interaction: {
            status: "clarifying",
          },
        },
      })
      return new Promise(() => undefined)
    })

    useConversationStore.setState({
      bootstrapped: true,
      selectedWorkspace: {
        kind: "conversation",
        conversationId: "conv_layout_001",
      },
      detailsByConversationId: {
        conv_layout_001: {
          conversationId: "conv_layout_001",
          title: "Layout",
          createdAt: "2026-05-13T10:00:00.000Z",
          updatedAt: "2026-05-13T10:00:00.000Z",
          interactionState: "idle",
        },
      },
      messagesByConversationId: {
        conv_layout_001: [],
      },
      draftsByKey: {
        [conversationDraftKeyForConversation("conv_layout_001")]: "compare candidate plans",
      },
    })

    await useConversationStore.getState().submitComposerMessage()
    await flushMicrotasks()

    const layoutMessage = useConversationStore
      .getState()
      .messagesByConversationId.conv_layout_001?.find((message) => message.messageId === "msg_layout_001")

    expect(layoutMessage?.richPayload?.kind).toBe("layout_tree")
    if (layoutMessage?.richPayload?.kind === "layout_tree") {
      expect(layoutMessage.richPayload.data.activity.blockId).toBe("candidate_compare_001")
      expect(layoutMessage.richPayload.data.stateSnapshot?.interaction?.status).toBe("clarifying")
    }
    expect(useConversationStore.getState().pendingTurnByConversationId.conv_layout_001).toEqual({
      state: "clarifying",
      turnId: "turn_layout_001",
    })
  })
})
