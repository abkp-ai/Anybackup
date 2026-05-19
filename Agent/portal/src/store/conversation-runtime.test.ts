import { describe, expect, it } from "vitest"
import {
  buildChatTimeline,
  derivePendingTurnState,
  mergeConversationStatusEvent,
} from "@/store/conversation-runtime"
import type {
  ConversationDetail,
  ConversationMessageSummary,
  ConversationStatusEvent,
} from "@/types/conversation"

describe("conversation-runtime", () => {
  it("groups messages by turn and keeps assistant AG-UI messages in sequence order", () => {
    const messages: ConversationMessageSummary[] = [
      {
        messageId: "msg_user_001",
        conversationId: "conv_001",
        turnId: "turn_001",
        role: "user",
        contentType: "text",
        content: "Show the restore candidates.",
        createdAt: "2026-05-12T08:00:00.000Z",
        status: "published",
      },
      {
        messageId: "msg_assistant_002",
        conversationId: "conv_001",
        turnId: "turn_001",
        role: "assistant",
        contentType: "rich_content",
        content: "Second visual update",
        createdAt: "2026-05-12T08:00:06.000Z",
        status: "responded",
        agUiSequence: 2,
      },
      {
        messageId: "msg_assistant_001",
        conversationId: "conv_001",
        turnId: "turn_001",
        role: "assistant",
        contentType: "rich_content",
        content: "First visual update",
        createdAt: "2026-05-12T08:00:05.000Z",
        status: "responded",
        agUiSequence: 1,
      },
    ]

    const timeline = buildChatTimeline(messages)

    expect(timeline).toHaveLength(2)
    expect(timeline[0]).toMatchObject({
      type: "user",
      message: {
        messageId: "msg_user_001",
      },
    })
    expect(timeline[1]).toMatchObject({
      type: "assistant",
      messages: [
        { messageId: "msg_assistant_001" },
        { messageId: "msg_assistant_002" },
      ],
    })
  })

  it("merges persisted status events into the current message list and keeps the run pending", () => {
    const detail: ConversationDetail = {
      conversationId: "conv_001",
      title: "Restore review",
      createdAt: "2026-05-12T08:00:00.000Z",
      updatedAt: "2026-05-12T08:00:00.000Z",
      interactionState: "idle",
      activeTurnId: "turn_001",
    }

    const messages: ConversationMessageSummary[] = []
    const event: ConversationStatusEvent = {
      statusEventId: "evt_001",
      conversationId: "conv_001",
      turnId: "turn_001",
      messageId: "msg_001",
      eventType: "rich_content.created",
      sequence: 1,
      interactionState: "thinking",
      messageStatus: "responded",
      createdAt: "2026-05-12T08:00:02.000Z",
      message: {
        messageId: "msg_001",
        conversationId: "conv_001",
        turnId: "turn_001",
        role: "assistant",
        contentType: "rich_content",
        content: "Looking up restore points.",
        createdAt: "2026-05-12T08:00:02.000Z",
        status: "responded",
      },
    }

    const mergedMessages = mergeConversationStatusEvent(messages, event)
    const pendingTurn = derivePendingTurnState(detail, mergedMessages, event.interactionState)

    expect(mergedMessages).toEqual([
      expect.objectContaining({
        messageId: "msg_001",
        content: "Looking up restore points.",
      }),
    ])
    expect(pendingTurn).toEqual({
      state: "thinking",
      turnId: "turn_001",
    })
  })
})
