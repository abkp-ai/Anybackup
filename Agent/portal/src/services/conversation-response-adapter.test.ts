import { describe, expect, it } from "vitest"
import {
  mapConversationDetailRecord,
  mapConversationMessageRecord,
  type ConversationApiModel,
  type ConversationMessageApiModel,
} from "@/services/conversation-response-adapter"

describe("conversation-response-adapter", () => {
  it("applies activity deltas to produce the final layout-tree payload", () => {
    const messageRecord: ConversationMessageApiModel = {
      message_id: "msg_layout_delta_001",
      conversation_id: "conv_layout_delta_001",
      turn_id: "turn_layout_delta_001",
      role: "assistant",
      content_type: "rich_content",
      content: "Updated restore options are ready.",
      status: "responded",
      created_at: "2026-05-12T08:00:00.000Z",
      rich_payload: {
        content_summary: "Updated restore options are ready.",
        ag_ui: {
          version: "1.x",
          events: [
            {
              type: "RUN_STARTED",
              threadId: "conv_layout_delta_001",
              runId: "turn_layout_delta_001",
            },
            {
              type: "ACTIVITY_SNAPSHOT",
              messageId: "act_restore_options_001",
              activityType: "conversation.ui.layout-tree",
              content: {
                contract: "conversation.ui.layout-tree@1",
                blockId: "restore_options",
                ui: {
                  type: "stack",
                  children: [
                    {
                      id: "title",
                      type: "heading",
                      props: {
                        level: 2,
                        text: "Restore options",
                      },
                    },
                  ],
                },
                meta: {
                  intent: "result",
                  terminal: false,
                },
              },
            },
            {
              type: "ACTIVITY_DELTA",
              messageId: "act_restore_options_001",
              patch: [
                {
                  op: "add",
                  path: "/ui/children/1",
                  value: {
                    id: "summary",
                    type: "paragraph",
                    props: {
                      text: "Option A keeps the production database isolated.",
                    },
                  },
                },
              ],
            },
            {
              type: "STATE_SNAPSHOT",
              state: {
                interaction: {
                  status: "clarifying",
                },
              },
            },
            {
              type: "STATE_DELTA",
              operation: "merge",
              delta: {
                selection: {
                  required: true,
                  selectedCandidateOptionId: "option_a",
                },
              },
            },
            {
              type: "RUN_FINISHED",
              threadId: "conv_layout_delta_001",
              runId: "turn_layout_delta_001",
              reason: "completed",
            },
          ],
        },
      },
    }

    const message = mapConversationMessageRecord(messageRecord)

    expect(message.richPayload).toEqual({
      kind: "layout_tree",
      data: {
        activity: {
          contract: "conversation.ui.layout-tree@1",
          blockId: "restore_options",
          ui: {
            type: "stack",
            children: [
              {
                id: "title",
                type: "heading",
                props: {
                  level: 2,
                  text: "Restore options",
                },
              },
              {
                id: "summary",
                type: "paragraph",
                props: {
                  text: "Option A keeps the production database isolated.",
                },
              },
            ],
          },
          meta: {
            intent: "result",
            terminal: false,
          },
        },
        stateSnapshot: {
          interaction: {
            status: "clarifying",
          },
          selection: {
            required: true,
            selectedCandidateOptionId: "option_a",
          },
        },
      },
    })
    expect(message.agUiEventName).toBe("RUN_FINISHED")
  })

  it("prefers AG-UI state over stale conversation detail interaction state", () => {
    const detailRecord: ConversationApiModel = {
      conversation_id: "conv_runtime_001",
      title: "Restore plan review",
      status: "active",
      interaction_status: "idle",
      active_turn_id: "turn_runtime_001",
      created_at: "2026-05-12T07:55:00.000Z",
      updated_at: "2026-05-12T08:00:00.000Z",
      last_active_at: "2026-05-12T08:00:00.000Z",
    }

    const messageRecord: ConversationMessageApiModel = {
      message_id: "msg_runtime_001",
      conversation_id: "conv_runtime_001",
      turn_id: "turn_runtime_001",
      role: "assistant",
      content_type: "rich_content",
      content: "Please confirm the restore option.",
      status: "responded",
      created_at: "2026-05-12T08:00:00.000Z",
      rich_payload: {
        ag_ui: {
          version: "1.x",
          events: [
            {
              type: "ACTIVITY_SNAPSHOT",
              messageId: "act_runtime_001",
              activityType: "conversation.ui.layout-tree",
              content: {
                contract: "conversation.ui.layout-tree@1",
                blockId: "clarification",
                ui: {
                  type: "stack",
                  children: [],
                },
              },
            },
            {
              type: "STATE_SNAPSHOT",
              state: {
                interaction: {
                  status: "clarifying",
                },
              },
            },
          ],
        },
      },
    }

    const detail = mapConversationDetailRecord(detailRecord, [mapConversationMessageRecord(messageRecord)])

    expect(detail.interactionState).toBe("clarifying")
    expect(detail.activeTurnId).toBe("turn_runtime_001")
  })

  it("maps active_run_id responses into an active thinking turn when interaction_status is omitted", () => {
    const detailRecord: ConversationApiModel = {
      conversation_id: "conv_active_run_001",
      title: "Restore run",
      status: "active",
      active_run_id: "turn_active_run_001",
      has_active_run: true,
      created_at: "2026-05-13T09:13:48.011Z",
      updated_at: "2026-05-13T09:13:48.011Z",
      last_active_at: "2026-05-13T09:13:48.011Z",
    }

    const detail = mapConversationDetailRecord(detailRecord)

    expect(detail.activeTurnId).toBe("turn_active_run_001")
    expect(detail.interactionState).toBe("thinking")
  })
})
