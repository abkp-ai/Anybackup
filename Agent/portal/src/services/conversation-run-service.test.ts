import { beforeEach, describe, expect, it, vi } from "vitest"
import { of } from "rxjs"

const {
  getAuthorizedSessionMock,
  runHttpRequestMock,
  parseSseStreamMock,
} = vi.hoisted(() => ({
  getAuthorizedSessionMock: vi.fn(),
  runHttpRequestMock: vi.fn(),
  parseSseStreamMock: vi.fn(),
}))

vi.mock("@/services/auth-service", () => ({
  getAuthorizedSession: getAuthorizedSessionMock,
}))

vi.mock("@ag-ui/client", () => ({
  runHttpRequest: runHttpRequestMock,
  parseSSEStream: parseSseStreamMock,
}))

vi.mock("@/i18n/messages", () => ({
  translate: (key: string) => key,
}))

import { startConversationRun } from "@/services/conversation-run-service"

describe("startConversationRun", () => {
  beforeEach(() => {
    getAuthorizedSessionMock.mockReset()
    runHttpRequestMock.mockReset()
    parseSseStreamMock.mockReset()

    getAuthorizedSessionMock.mockResolvedValue({
      accessToken: "access-token",
    })
    runHttpRequestMock.mockReturnValue({})
    parseSseStreamMock.mockReturnValue(of())
  })

  it("creates an authorized /runs request and streams the AG-UI response", async () => {
    await startConversationRun(
      {
        threadId: "conv_001",
        runId: "turn_001",
        messages: [
          { role: "user", content: "restore the latest backup" },
          { role: "assistant", content: "which backup set do you mean?" },
        ],
        state: {
          interaction: {
            status: "clarifying",
          },
        },
        tools: [{ name: "tool-a" }],
        context: [{ source: "history" }],
        forwardedProps: {
          locale: "en",
        },
      },
      { onEvent: vi.fn() },
    )

    expect(runHttpRequestMock).toHaveBeenCalledWith(
      "/api/conversation_service/v1/runs",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({
          Authorization: "Bearer access-token",
          "Content-Type": "application/json",
          Accept: "text/event-stream",
          "X-Request-Id": expect.any(String),
        }),
        signal: expect.any(AbortSignal),
        body: expect.any(String),
      }),
    )

    const [, requestInit] = runHttpRequestMock.mock.calls[0] as [string, RequestInit]
    const requestBody = JSON.parse(String(requestInit.body))

    expect(requestBody).toEqual({
      threadId: "conv_001",
      runId: "turn_001",
      messages: [
        {
          id: expect.any(String),
          role: "user",
          content: "restore the latest backup",
        },
        {
          id: expect.any(String),
          role: "assistant",
          content: "which backup set do you mean?",
        },
      ],
      state: {
        interaction: {
          status: "clarifying",
        },
      },
      tools: [{ name: "tool-a" }],
      context: [{ source: "history" }],
      forwardedProps: {
        locale: "en",
      },
    })
  })

  it("forwards raw AG-UI events emitted by the SSE stream", async () => {
    parseSseStreamMock.mockReturnValue(
      of(
        { type: "RUN_STARTED", threadId: "conv_001", runId: "turn_001" },
        { type: "TEXT_MESSAGE_CONTENT", messageId: "msg_001", delta: "hello" },
        { type: "RUN_FINISHED", threadId: "conv_001", runId: "turn_001", reason: "completed" },
      ),
    )

    const receivedEvents: unknown[] = []

    await startConversationRun(
      {
        threadId: "conv_001",
        runId: "turn_001",
        messages: [{ role: "user", content: "restore the latest backup" }],
      },
      {
        onEvent: (event) => {
          receivedEvents.push(event)
        },
      },
    )

    expect(receivedEvents).toEqual([
      { type: "RUN_STARTED", threadId: "conv_001", runId: "turn_001" },
      { type: "TEXT_MESSAGE_CONTENT", messageId: "msg_001", delta: "hello" },
      { type: "RUN_FINISHED", threadId: "conv_001", runId: "turn_001", reason: "completed" },
    ])
  })

  it("unwraps persisted status-event envelopes that carry ag_ui events", async () => {
    parseSseStreamMock.mockReturnValue(
      of({
        status_event_id: "evt_001",
        event_type: "rich_content.created",
        payload: {
          rich_payload: {
            ag_ui: {
              events: [
                { type: "RUN_STARTED", threadId: "conv_001", runId: "turn_001" },
                {
                  type: "ACTIVITY_SNAPSHOT",
                  messageId: "act_001",
                  activityType: "conversation.ui.layout-tree",
                  content: {
                    contract: "conversation.ui.layout-tree@1",
                    ui: {
                      type: "stack",
                      children: [],
                    },
                  },
                },
                { type: "RUN_FINISHED", threadId: "conv_001", runId: "turn_001", reason: "completed" },
              ],
            },
          },
        },
      }),
    )

    const receivedEvents: unknown[] = []

    await startConversationRun(
      {
        threadId: "conv_001",
        runId: "turn_001",
        messages: [{ role: "user", content: "restore the latest backup" }],
      },
      {
        onEvent: (event) => {
          receivedEvents.push(event)
        },
      },
    )

    expect(receivedEvents).toEqual([
      { type: "RUN_STARTED", threadId: "conv_001", runId: "turn_001" },
      {
        type: "ACTIVITY_SNAPSHOT",
        messageId: "act_001",
        activityType: "conversation.ui.layout-tree",
        content: {
          contract: "conversation.ui.layout-tree@1",
          ui: {
            type: "stack",
            children: [],
          },
        },
        replace: true,
      },
      { type: "RUN_FINISHED", threadId: "conv_001", runId: "turn_001", reason: "completed" },
    ])
  })
})
