import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

const { getAuthorizedSessionMock } = vi.hoisted(() => ({
  getAuthorizedSessionMock: vi.fn(),
}))

vi.mock("@/services/auth-service", () => ({
  getAuthorizedSession: getAuthorizedSessionMock,
}))

import {
  createConversation,
  getConversationDetail,
  getConversationMessages,
  listConversationEvents,
  listConversations,
  searchConversations,
  sendMessage,
} from "@/services/conversation-service"

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
    },
  })
}

describe("conversation-service", () => {
  beforeEach(() => {
    getAuthorizedSessionMock.mockResolvedValue({
      accessToken: "test-access-token",
    })
  })

  afterEach(() => {
    vi.clearAllMocks()
    vi.unstubAllGlobals()
  })

  it("lists conversations from the conversation service", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        items: [
          {
            conversation_id: "conv_restore_order_db",
            owner_user_id: "user_001",
            title: "璁㈠崟鏁版嵁搴撴仮澶?",
            status: "active",
            summary: "纭鍙敤澶囦唤鐐瑰悗锛屽啀鍐冲畾鎭㈠鏃堕棿鐐广€?",
            tags: ["restore"],
            latest_message_summary: "淇濇寔鍘熶綅缃仮澶?",
            interaction_status: "idle",
            created_at: "2026-04-21T08:30:00.000Z",
            updated_at: "2026-04-21T08:42:00.000Z",
            last_active_at: "2026-04-21T08:42:00.000Z",
            retention_policy: {},
            legal_hold: false,
          },
        ],
        page: {
          has_more: false,
          limit: 100,
          next_cursor: null,
        },
      }),
    )

    vi.stubGlobal("fetch", fetchMock)

    const conversations = await listConversations()

    expect(conversations).toHaveLength(1)
    expect(conversations[0]).toMatchObject({
      conversationId: "conv_restore_order_db",
      title: "璁㈠崟鏁版嵁搴撴仮澶?",
      displaySummary: "纭鍙敤澶囦唤鐐瑰悗锛屽啀鍐冲畾鎭㈠鏃堕棿鐐广€?",
      status: "active",
      lastActiveAt: "2026-04-21T08:42:00.000Z",
    })

    expect(fetchMock).toHaveBeenCalledTimes(1)
    const [url, init] = fetchMock.mock.calls[0] ?? []
    expect(String(url)).toContain("/api/conversation_service/v1/conversations")
    expect(String(url)).toContain("limit=100")
    expect(String(url)).toContain("sort=last_active_desc")
    expect(String(url)).toContain("archived=false")
    expect(init?.method).toBe("GET")
    expect(new Headers(init?.headers).get("Authorization")).toBe("Bearer test-access-token")
    expect(new Headers(init?.headers).get("X-Request-Id")).toBeTruthy()
  })

  it("searches conversations through the keyword query parameter", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        items: [],
        page: {
          has_more: false,
          limit: 100,
          next_cursor: null,
        },
      }),
    )

    vi.stubGlobal("fetch", fetchMock)

    await searchConversations("admin-cli")

    const [url] = fetchMock.mock.calls[0] ?? []
    expect(String(url)).toContain("keyword=admin-cli")
  })

  it("loads conversation detail and messages with response mapping", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({
          conversation_id: "conv_backup_schedule",
          owner_user_id: "user_001",
          title: "璁㈠崟搴撳浠界瓥鐣?",
          status: "paused",
          summary: "璁ㄨ姣忓ぉ鍑屾櫒 2 鐐规墽琛岋紝淇濈暀 90 澶┿€?",
          tags: ["backup"],
          latest_message_summary: "鍏堜繚鐣?90 澶?",
          interaction_status: "clarifying",
          created_at: "2026-04-21T05:20:00.000Z",
          updated_at: "2026-04-21T06:15:00.000Z",
          last_active_at: "2026-04-21T06:15:00.000Z",
          retention_policy: {},
          legal_hold: false,
          context: {
            summary: "褰撳墠鍙樊閫氱煡鍜岄噸璇曡鍒欍€?",
          },
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          items: [
            {
              message_id: "msg_001",
              conversation_id: "conv_backup_schedule",
              role: "assistant",
              content_type: "rich_content",
              content: null,
              rich_payload: {
                render_fallback: {
                  text: "鏈€杩?3 娆′换鍔＄粨鏋滆〃鏍?",
                },
              },
              status: "responded",
              created_at: "2026-04-21T06:15:00.000Z",
              updated_at: "2026-04-21T06:15:10.000Z",
            },
          ],
          page: {
            has_more: false,
            limit: 100,
            next_cursor: null,
          },
        }),
      )

    vi.stubGlobal("fetch", fetchMock)

    const detail = await getConversationDetail("conv_backup_schedule")
    const messages = await getConversationMessages("conv_backup_schedule")

    expect(detail).toMatchObject({
      conversationId: "conv_backup_schedule",
      title: "璁㈠崟搴撳浠界瓥鐣?",
      interactionState: "clarifying",
      contextSummary: "褰撳墠鍙樊閫氱煡鍜岄噸璇曡鍒欍€?",
    })
    expect(messages[0]).toMatchObject({
      messageId: "msg_001",
      content: "鏈€杩?3 娆′换鍔＄粨鏋滆〃鏍?",
      contentType: "rich_content",
      status: "responded",
    })
  })

  it("maps string ag_ui payloads into markdown rich payloads", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        items: [
          {
            message_id: "msg_markdown_001",
            conversation_id: "conv_markdown_001",
            role: "assistant",
            content_type: "rich_content",
            content: "markdown summary",
            status: "responded",
            created_at: "2026-04-28T08:00:00.000Z",
            rich_payload: {
              content_summary: "markdown summary",
              ag_ui: "1. **mysql3306_U0HYTDM3RENXS4EJ**\n\n请确认是否恢复此实例。",
            },
          },
        ],
        page: {
          has_more: false,
          limit: 100,
          next_cursor: null,
        },
      }),
    )

    vi.stubGlobal("fetch", fetchMock)

    const messages = await getConversationMessages("conv_markdown_001")

    expect(messages[0]).toMatchObject({
      messageId: "msg_markdown_001",
      content: "markdown summary",
      contentType: "rich_content",
      richPayload: {
        kind: "markdown",
        data: {
          markdown: "1. **mysql3306_U0HYTDM3RENXS4EJ**\n\n请确认是否恢复此实例。",
        },
      },
    })
  })

  it("decodes escaped ag_ui markdown strings before rendering", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        items: [
          {
            message_id: "msg_markdown_escaped_001",
            conversation_id: "conv_markdown_escaped_001",
            role: "assistant",
            content_type: "rich_content",
            content: "markdown summary",
            status: "responded",
            created_at: "2026-04-28T08:10:00.000Z",
            rich_payload: {
              content_summary: "markdown summary",
              ag_ui:
                "\"# 备份方案推荐：mysql3306_U0HYTDM3RENXS4EJ\\n\\n## 生产资源信息\\n- **资源名称**：mysql3306_U0HYTDM3RENXS4EJ\"",
            },
          },
        ],
        page: {
          has_more: false,
          limit: 100,
          next_cursor: null,
        },
      }),
    )

    vi.stubGlobal("fetch", fetchMock)

    const [message] = await getConversationMessages("conv_markdown_escaped_001")

    expect(message.richPayload).toEqual({
      kind: "markdown",
      data: {
        markdown:
          "# 备份方案推荐：mysql3306_U0HYTDM3RENXS4EJ\n\n## 生产资源信息\n- **资源名称**：mysql3306_U0HYTDM3RENXS4EJ",
      },
    })
  })

  it("maps candidate option AG-UI events into a typed rich payload", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        items: [
          {
            message_id: "msg_candidate_001",
            conversation_id: "conv_restore_001",
            role: "assistant",
            content_type: "rich_content",
            content: "已生成 2 个恢复候选方案。",
            status: "responded",
            created_at: "2026-04-22T10:00:00.000Z",
            rich_payload: {
              content_summary: "恢复候选方案",
              ag_ui: {
                version: "1.x",
                events: [
                  {
                    type: "CUSTOM",
                    timestamp: 1776660000000,
                    name: "anybackup.conversation.candidate_options.render",
                    value: {
                      reasoning_trace_id: "trace_restore_001",
                      title: "为你生成 2 个备选方案",
                      summary: "已完成恢复方案评估（待提交）",
                      actions: [
                        {
                          type: "confirm",
                          label: "确认提交方案",
                        },
                        {
                          type: "reject",
                          label: "放弃该方案",
                        },
                        {
                          type: "revise",
                          label: "补充约束",
                          input_label: "补充约束",
                          input_placeholder: "例如：先生成方案，不要立即执行。",
                          submit_label: "提交补充约束",
                        },
                      ],
                      options: [
                        {
                          option_id: "option_a",
                          title: "方案 A：异机数据库级恢复 + 表导出导入",
                          recommended: true,
                          summary: "推荐方案",
                          fields: [
                            {
                              key: "restore_scope",
                              label: "恢复粒度",
                              value: "数据库级（资产）",
                            },
                            {
                              key: "rpo_rto",
                              label: "RPO / RTO",
                              value: "< 2 分钟 / 1.5 小时",
                            },
                          ],
                          extra: {
                            title: "业务影响",
                            content: "恢复粒度为数据库级，但实际仅操作目标表。",
                          },
                        },
                      ],
                    },
                  },
                ],
              },
            },
          },
        ],
        page: {
          has_more: false,
          limit: 100,
          next_cursor: null,
        },
      }),
    )

    vi.stubGlobal("fetch", fetchMock)

    const [message] = await getConversationMessages("conv_restore_001")

    expect(message.richPayload).toEqual({
      kind: "candidate_options",
      data: {
        reasoningTraceId: "trace_restore_001",
        title: "为你生成 2 个备选方案",
        summary: "已完成恢复方案评估（待提交）",
        actions: [
          {
            type: "confirm",
            label: "确认提交方案",
          },
          {
            type: "reject",
            label: "放弃该方案",
          },
          {
            type: "revise",
            label: "补充约束",
            inputLabel: "补充约束",
            inputPlaceholder: "例如：先生成方案，不要立即执行。",
            submitLabel: "提交补充约束",
          },
        ],
        options: [
          {
            optionId: "option_a",
            title: "方案 A：异机数据库级恢复 + 表导出导入",
            recommended: true,
            summary: "推荐方案",
            fields: [
              {
                key: "restore_scope",
                label: "恢复粒度",
                value: "数据库级（资产）",
              },
              {
                key: "rpo_rto",
                label: "RPO / RTO",
                value: "< 2 分钟 / 1.5 小时",
              },
            ],
            extra: {
              title: "业务影响",
              content: "恢复粒度为数据库级，但实际仅操作目标表。",
            },
          },
        ],
      },
    })
    expect(message.content).toBe("已生成 2 个恢复候选方案。")
  })

  it("maps locked candidate option state from the AG-UI payload", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        items: [
          {
            message_id: "msg_candidate_locked_001",
            conversation_id: "conv_restore_001",
            role: "assistant",
            content_type: "rich_content",
            content: "已确认推荐恢复方案。",
            status: "responded",
            created_at: "2026-04-22T10:01:00.000Z",
            rich_payload: {
              content_summary: "已确认恢复方案",
              ag_ui: {
                version: "1.x",
                events: [
                  {
                    type: "CUSTOM",
                    timestamp: 1776660060000,
                    name: "anybackup.conversation.candidate_options.render",
                    value: {
                      reasoning_trace_id: "trace_restore_002",
                      title: "恢复候选方案",
                      summary: "推荐方案已确认。",
                      selection_locked: true,
                      selected_candidate_option_id: "candidate_option_a",
                      actions: [
                        {
                          type: "confirm",
                          label: "确认提交方案",
                        },
                      ],
                      options: [
                        {
                          candidate_option_id: "candidate_option_a",
                          title: "方案 A：按推荐恢复点恢复",
                          recommended: true,
                          fields: [
                            {
                              key: "restore_scope",
                              label: "恢复粒度",
                              value: "数据库级",
                            },
                          ],
                        },
                      ],
                    },
                  },
                ],
              },
            },
          },
        ],
        page: {
          has_more: false,
          limit: 100,
          next_cursor: null,
        },
      }),
    )

    vi.stubGlobal("fetch", fetchMock)

    const [message] = await getConversationMessages("conv_restore_001")

    expect(message.richPayload).toEqual({
      kind: "candidate_options",
      data: {
        reasoningTraceId: "trace_restore_002",
        title: "恢复候选方案",
        summary: "推荐方案已确认。",
        selectionLocked: true,
        selectedOptionId: "candidate_option_a",
        actions: [
          {
            type: "confirm",
            label: "确认提交方案",
          },
        ],
        options: [
          {
            optionId: "candidate_option_a",
            title: "方案 A：按推荐恢复点恢复",
            recommended: true,
            fields: [
              {
                key: "restore_scope",
                label: "恢复粒度",
                value: "数据库级",
              },
            ],
          },
        ],
      },
    })
  })

  it("maps clarification AG-UI events into a typed rich payload", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        items: [
          {
            message_id: "msg_clarification_001",
            conversation_id: "conv_restore_001",
            role: "assistant",
            content_type: "clarification",
            content: "请确认目标恢复时间窗口。",
            status: "responded",
            created_at: "2026-04-22T10:02:00.000Z",
            rich_payload: {
              content_summary: "恢复时间窗口澄清",
              ag_ui: {
                version: "1.x",
                events: [
                  {
                    type: "CUSTOM",
                    timestamp: 1776660120000,
                    name: "anybackup.conversation.clarification.render",
                    value: {
                      clarification_id: "restore_window",
                      prompt: "请确认目标恢复时间窗口。",
                      options: [
                        { label: "最近安全点", value: "latest_safe_point" },
                        { label: "指定时间", value: "custom_timestamp" },
                      ],
                      input_constraints: {
                        required: true,
                        allow_free_text: true,
                        free_text_label: "恢复时间",
                        free_text_placeholder: "请选择或输入恢复时间",
                      },
                    },
                  },
                ],
              },
            },
          },
        ],
        page: {
          has_more: false,
          limit: 100,
          next_cursor: null,
        },
      }),
    )

    vi.stubGlobal("fetch", fetchMock)

    const [message] = await getConversationMessages("conv_restore_001")

    expect(message.richPayload).toEqual({
      kind: "clarification",
      data: {
        clarificationId: "restore_window",
        prompt: "请确认目标恢复时间窗口。",
        options: [
          { label: "最近安全点", value: "latest_safe_point" },
          { label: "指定时间", value: "custom_timestamp" },
        ],
        inputConstraints: {
          required: true,
          allowFreeText: true,
          freeTextLabel: "恢复时间",
          freeTextPlaceholder: "请选择或输入恢复时间",
        },
      },
    })
  })

  it("maps layout-tree AG-UI snapshots into a typed rich payload", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        items: [
          {
            message_id: "msg_layout_tree_001",
            conversation_id: "conv_restore_001",
            role: "assistant",
            content_type: "rich_content",
            content: "系统生成了 3 个恢复候选方案。",
            status: "responded",
            created_at: "2026-04-24T02:00:00.000Z",
            rich_payload: {
              content_summary: "恢复候选方案对比",
              ag_ui: {
                version: "1.x",
                events: [
                  {
                    type: "ACTIVITY_SNAPSHOT",
                    timestamp: 1777000100000,
                    messageId: "act_candidate_compare_001",
                    activityType: "conversation.ui.layout-tree",
                    content: {
                      contract: "conversation.ui.layout-tree@1",
                      blockId: "candidate_compare_001",
                      ui: {
                        id: "root",
                        type: "stack",
                        children: [
                          {
                            id: "title",
                            type: "heading",
                            props: {
                              level: 2,
                              text: "已为你生成 3 个恢复候选方案",
                            },
                          },
                        ],
                      },
                      actions: [
                        {
                          id: "choose_candidate_a",
                          kind: "submit_message",
                          label: "确认方案 A",
                          payload: {
                            type: "candidate_selection",
                            candidate_option_id: "candidate_a",
                            selection: "confirm",
                          },
                        },
                      ],
                      meta: {
                        intent: "result",
                        terminal: true,
                        sourceMessageId: "msg_user_001",
                        reasoningTraceId: "rt_restore_001",
                      },
                    },
                  },
                  {
                    type: "STATE_SNAPSHOT",
                    timestamp: 1777000100200,
                    snapshot: {
                      interaction: {
                        status: "clarifying",
                      },
                      selection: {
                        required: true,
                        selectedCandidateOptionId: "candidate_a",
                        selectionLocked: false,
                      },
                      view: {
                        activeBlockIds: ["candidate_compare_001"],
                      },
                    },
                  },
                ],
              },
            },
          },
        ],
        page: {
          has_more: false,
          limit: 100,
          next_cursor: null,
        },
      }),
    )

    vi.stubGlobal("fetch", fetchMock)

    const [message] = await getConversationMessages("conv_restore_001")

    expect(message.richPayload).toEqual({
      kind: "layout_tree",
      data: {
        activity: {
          contract: "conversation.ui.layout-tree@1",
          blockId: "candidate_compare_001",
          ui: {
            id: "root",
            type: "stack",
            children: [
              {
                id: "title",
                type: "heading",
                props: {
                  level: 2,
                  text: "已为你生成 3 个恢复候选方案",
                },
              },
            ],
          },
          actions: [
            {
              id: "choose_candidate_a",
              kind: "submit_message",
              label: "确认方案 A",
              payload: {
                type: "candidate_selection",
                candidate_option_id: "candidate_a",
                selection: "confirm",
              },
            },
          ],
          meta: {
            intent: "result",
            terminal: true,
            sourceMessageId: "msg_user_001",
            reasoningTraceId: "rt_restore_001",
          },
        },
        stateSnapshot: {
          interaction: {
            status: "clarifying",
          },
          selection: {
            required: true,
            selectedCandidateOptionId: "candidate_a",
            selectionLocked: false,
          },
          view: {
            activeBlockIds: ["candidate_compare_001"],
          },
        },
      },
    })
  })

  it("maps conversation-service layout_nodes shape with props.children into layout_tree ui", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        items: [
          {
            message_id: "msg_layout_nodes_shape_001",
            conversation_id: "conv_thought_001",
            role: "assistant",
            content_type: "rich_content",
            content: "",
            status: "responded",
            created_at: "2026-05-13T10:01:00.000Z",
            rich_payload: {
              ag_ui: {
                version: "1",
                events: [
                  {
                    type: "ACTIVITY_SNAPSHOT",
                    timestamp: 1777000200000,
                    messageId: "act_text_message_001",
                    activityType: "conversation.ui.layout-tree",
                    content: {
                      contract: "conversation.ui.layout-tree@1",
                      blockId: "text-message",
                      ui: {
                        type: "stack",
                        props: {
                          gap: "sm",
                          children: [
                            {
                              type: "section",
                              props: {
                                children: [
                                  {
                                    type: "badge-row",
                                    props: {
                                      items: [{ text: "推理", tone: "info" }],
                                    },
                                  },
                                ],
                              },
                            },
                            {
                              type: "section",
                              props: {
                                children: [
                                  {
                                    type: "markdown",
                                    props: {
                                      text: "Collected the request intent and selected the next retrieval step.",
                                    },
                                  },
                                ],
                              },
                            },
                          ],
                        },
                      },
                    },
                  },
                ],
              },
            },
          },
        ],
        page: {
          has_more: false,
          limit: 100,
          next_cursor: null,
        },
      }),
    )

    vi.stubGlobal("fetch", fetchMock)

    const [message] = await getConversationMessages("conv_thought_001")

    expect(message.richPayload?.kind).toBe("layout_tree")
    if (message.richPayload?.kind !== "layout_tree") return

    const stack = message.richPayload.data.activity.ui
    expect(stack.type).toBe("stack")
    expect(stack.children?.length).toBe(2)
    expect(stack.children?.[1]?.children?.[0]?.type).toBe("markdown")
    expect(stack.children?.[1]?.children?.[0]?.props?.text).toContain("Collected the request intent")
  })

  it("replays layout-tree deltas and state deltas from official AG-UI events", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        items: [
          {
            message_id: "msg_layout_tree_delta_001",
            conversation_id: "conv_restore_001",
            role: "assistant",
            content_type: "rich_content",
            content: "系统生成了 3 个恢复候选方案。",
            status: "responded",
            created_at: "2026-04-24T02:05:00.000Z",
            rich_payload: {
              content_summary: "恢复候选方案对比",
              ag_ui: {
                version: "1.x",
                events: [
                  {
                    type: "ACTIVITY_SNAPSHOT",
                    timestamp: 1777000100000,
                    messageId: "act_candidate_compare_001",
                    activityType: "conversation.ui.layout-tree",
                    content: {
                      contract: "conversation.ui.layout-tree@1",
                      blockId: "candidate_compare_001",
                      ui: {
                        id: "root",
                        type: "stack",
                        children: [
                          {
                            id: "title",
                            type: "heading",
                            props: {
                              level: 2,
                              text: "初始标题",
                            },
                          },
                        ],
                      },
                    },
                  },
                  {
                    type: "ACTIVITY_DELTA",
                    timestamp: 1777000100100,
                    messageId: "act_candidate_compare_001",
                    patch: [
                      {
                        op: "replace",
                        path: "/ui/children/0/props/text",
                        value: "已为你生成 3 个恢复候选方案",
                      },
                      {
                        op: "add",
                        path: "/meta",
                        value: {
                          intent: "result",
                          terminal: true,
                          reasoningTraceId: "rt_restore_delta_001",
                        },
                      },
                    ],
                  },
                  {
                    type: "STATE_SNAPSHOT",
                    timestamp: 1777000100200,
                    snapshot: {
                      interaction: {
                        status: "thinking",
                      },
                      selection: {
                        required: true,
                        selectedCandidateOptionId: null,
                        selectionLocked: false,
                      },
                    },
                  },
                  {
                    type: "STATE_DELTA",
                    timestamp: 1777000100300,
                    delta: [
                      {
                        op: "replace",
                        path: "/interaction/status",
                        value: "clarifying",
                      },
                      {
                        op: "replace",
                        path: "/selection/selectedCandidateOptionId",
                        value: "candidate_b",
                      },
                    ],
                  },
                ],
              },
            },
          },
        ],
        page: {
          has_more: false,
          limit: 100,
          next_cursor: null,
        },
      }),
    )

    vi.stubGlobal("fetch", fetchMock)

    const [message] = await getConversationMessages("conv_restore_001")

    expect(message.richPayload).toEqual({
      kind: "layout_tree",
      data: {
        activity: {
          contract: "conversation.ui.layout-tree@1",
          blockId: "candidate_compare_001",
          ui: {
            id: "root",
            type: "stack",
            children: [
              {
                id: "title",
                type: "heading",
                props: {
                  level: 2,
                  text: "已为你生成 3 个恢复候选方案",
                },
              },
            ],
          },
          meta: {
            intent: "result",
            terminal: true,
            reasoningTraceId: "rt_restore_delta_001",
          },
        },
        stateSnapshot: {
          interaction: {
            status: "clarifying",
          },
          selection: {
            required: true,
            selectedCandidateOptionId: "candidate_b",
            selectionLocked: false,
          },
        },
      },
    })
  })

  it("resolves message content from official AG-UI text events when content is empty", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        items: [
          {
            message_id: "msg_text_only_001",
            conversation_id: "conv_restore_001",
            role: "assistant",
            content_type: "rich_content",
            content: null,
            status: "responded",
            created_at: "2026-04-24T02:06:00.000Z",
            rich_payload: {
              content_summary: "文本结果",
              ag_ui: {
                version: "1.x",
                events: [
                  {
                    type: "TEXT_MESSAGE_START",
                    timestamp: 1777000200000,
                    messageId: "text_restore_001",
                    role: "assistant",
                  },
                  {
                    type: "TEXT_MESSAGE_CONTENT",
                    timestamp: 1777000200100,
                    messageId: "text_restore_001",
                    delta: "This response intentionally ",
                  },
                  {
                    type: "TEXT_MESSAGE_CONTENT",
                    timestamp: 1777000200200,
                    messageId: "text_restore_001",
                    delta: "contains only AG-UI text message events.",
                  },
                  {
                    type: "TEXT_MESSAGE_END",
                    timestamp: 1777000200300,
                    messageId: "text_restore_001",
                  },
                ],
              },
            },
          },
        ],
        page: {
          has_more: false,
          limit: 100,
          next_cursor: null,
        },
      }),
    )

    vi.stubGlobal("fetch", fetchMock)

    const [message] = await getConversationMessages("conv_restore_001")

    expect(message.content).toBe("This response intentionally contains only AG-UI text message events.")
    expect(message.richPayload).toBeUndefined()
  })

  it("maps thought AG-UI events into a process rich payload", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        items: [
          {
            message_id: "msg_thought_001",
            conversation_id: "conv_restore_001",
            role: "assistant",
            content_type: "rich_content",
            content: "Analyzing restore constraints...",
            status: "responded",
            created_at: "2026-04-23T09:00:10.000Z",
            rich_payload: {
              content_summary: "Analyzing restore constraints",
              ag_ui: {
                version: "1.x",
                events: [
                  {
                    type: "CUSTOM",
                    timestamp: 1776915610000,
                    name: "anybackup.conversation.thought.render",
                    value: {
                      reasoning_trace_id: "trace_restore_001",
                      title: "Restore analysis",
                      summary: "Checking restore point freshness and risk.",
                    },
                  },
                ],
              },
            },
          },
        ],
        page: {
          has_more: false,
          limit: 100,
          next_cursor: null,
        },
      }),
    )

    vi.stubGlobal("fetch", fetchMock)

    const [message] = await getConversationMessages("conv_restore_001")

    expect(message.richPayload).toEqual({
      kind: "thought",
      data: {
        traceId: "trace_restore_001",
        title: "Restore analysis",
        summary: "Checking restore point freshness and risk.",
      },
    })
    expect(message.content).toBe("Analyzing restore constraints...")
  })

  it("resolves display content for rich messages by fallback priority", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        items: [
          {
            message_id: "msg_rich_content_first",
            conversation_id: "conv_text_loop",
            role: "assistant",
            content_type: "rich_content",
            content: "Direct text summary",
            rich_payload: {
              render_fallback: { text: "unused fallback" },
              content_summary: "unused summary",
            },
            status: "responded",
            created_at: "2026-04-23T09:00:00.000Z",
          },
          {
            message_id: "msg_rich_fallback_second",
            conversation_id: "conv_text_loop",
            role: "assistant",
            content_type: "rich_content",
            content: null,
            rich_payload: {
              render_fallback: { text: "matched render fallback" },
              content_summary: "unused summary",
            },
            status: "responded",
            created_at: "2026-04-23T09:00:01.000Z",
          },
          {
            message_id: "msg_rich_summary_third",
            conversation_id: "conv_text_loop",
            role: "assistant",
            content_type: "rich_content",
            content: null,
            rich_payload: {
              content_summary: "matched content summary",
            },
            status: "responded",
            created_at: "2026-04-23T09:00:02.000Z",
          },
          {
            message_id: "msg_rich_empty_fourth",
            conversation_id: "conv_text_loop",
            role: "assistant",
            content_type: "rich_content",
            content: null,
            rich_payload: null,
            status: "responded",
            created_at: "2026-04-23T09:00:03.000Z",
          },
        ],
        page: {
          has_more: false,
          limit: 100,
          next_cursor: null,
        },
      }),
    )

    vi.stubGlobal("fetch", fetchMock)

    const messages = await getConversationMessages("conv_text_loop")

    expect(messages.map((message) => message.content)).toEqual([
      "Direct text summary",
      "matched render fallback",
      "matched content summary",
      "[Structured content]",
    ])
  })

  it("lists conversation events with message snapshots and polling metadata", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        items: [
          {
            status_event_id: "evt_thought_001",
            conversation_id: "conv_event_loop",
            turn_id: "turn_001",
            message_id: "msg_thought_001",
            event_type: "rich_content.created",
            sequence: 2,
            interaction_status: "thinking",
            message_status: "responded",
            payload: {
              message: {
                message_id: "msg_thought_001",
                conversation_id: "conv_event_loop",
                turn_id: "turn_001",
                parent_message_id: "msg_user_001",
                role: "assistant",
                content_type: "rich_content",
                content: "姝ｅ湪鐞嗚В闂骞跺噯澶囨煡璇笂涓嬫枃銆?",
                status: "responded",
                created_at: "2026-04-23T10:00:04.000Z",
                rich_payload: {
                  content_summary: "姝ｅ湪鐞嗚В闂骞跺噯澶囨煡璇笂涓嬫枃銆?",
                  ag_ui: {
                    version: "1.x",
                    events: [
                      {
                        type: "CUSTOM",
                        name: "anybackup.conversation.thought.render",
                        value: {
                          summary: "姝ｅ湪鎻愬彇鐢ㄦ埛鐩爣鍜屼笂涓嬫枃绾跨储銆?",
                        },
                      },
                    ],
                  },
                },
              },
            },
            created_at: "2026-04-23T10:00:04.000Z",
          },
        ],
        page: {
          next_cursor: "cursor_after_2",
          has_more: false,
          limit: 50,
        },
        latest_sequence: 2,
        recommended_poll_interval_ms: 1500,
        interaction_status: "thinking",
      }),
    )

    vi.stubGlobal("fetch", fetchMock)

    const result = await listConversationEvents("conv_event_loop", {
      cursor: "cursor_after_1",
    })

    expect(result).toMatchObject({
      nextCursor: "cursor_after_2",
      hasMore: false,
      latestSequence: 2,
      recommendedPollIntervalMs: 1500,
      interactionState: "thinking",
    })
    expect(result.events[0]).toMatchObject({
      statusEventId: "evt_thought_001",
      eventType: "rich_content.created",
      turnId: "turn_001",
      sequence: 2,
      interactionState: "thinking",
    })
    expect(result.events[0]?.message).toMatchObject({
      messageId: "msg_thought_001",
      turnId: "turn_001",
      richPayload: {
        kind: "thought",
        data: {
          summary: "姝ｅ湪鎻愬彇鐢ㄦ埛鐩爣鍜屼笂涓嬫枃绾跨储銆?",
        },
      },
    })

    const [url] = fetchMock.mock.calls[0] ?? []
    expect(String(url)).toContain("/conversations/conv_event_loop/events")
    expect(String(url)).toContain("cursor=cursor_after_1")
    expect(String(url)).toContain("include_rich_payload=true")
  })

  it("uses event timestamps when event message snapshots omit created_at", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        items: [
          {
            status_event_id: "evt_without_message_created_at",
            conversation_id: "conv_event_loop",
            turn_id: "turn_001",
            message_id: "msg_assistant_001",
            event_type: "message.created",
            sequence: 2,
            interaction_status: "thinking",
            payload: {
              message: {
                message_id: "msg_assistant_001",
                conversation_id: "conv_event_loop",
                turn_id: "turn_001",
                role: "assistant",
                content_type: "text",
                content: "鎴戜細鍏堟鏌ュ彲鐢ㄦ仮澶嶇偣銆?",
                status: "responded",
              },
            },
            occurred_at: "2026-04-23T10:00:05.000Z",
          },
        ],
        page: {
          next_cursor: "cursor_after_2",
          has_more: false,
          limit: 50,
        },
        latest_sequence: 2,
        recommended_poll_interval_ms: 1500,
        interaction_status: "thinking",
      }),
    )

    vi.stubGlobal("fetch", fetchMock)

    const result = await listConversationEvents("conv_event_loop")

    expect(result.events[0]?.createdAt).toBe("2026-04-23T10:00:05.000Z")
    expect(result.events[0]?.message?.createdAt).toBe("2026-04-23T10:00:05.000Z")
  })

  it("maps event-level AG-UI rich payloads onto message snapshots with ordering metadata", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({
        items: [
          {
            status_event_id: "evt_thought_real_payload",
            conversation_id: "conv_real_payload",
            turn_id: "turn_real_001",
            message_id: "msg_thought_real_001",
            event_type: "rich_content.created",
            sequence: 4,
            interaction_status: "executing",
            message_status: "responded",
            payload: {
              message: {
                message_id: "msg_thought_real_001",
                conversation_id: "conv_real_payload",
                turn_id: "turn_real_001",
                parent_message_id: "msg_user_real_001",
                role: "assistant",
                content_type: "rich_content",
                content: "姝ｅ湪鐞嗚В闂骞跺噯澶囨煡璇笂涓嬫枃銆?",
                status: "responded",
              },
              rich_payload: {
                content_summary: "姝ｅ湪鐞嗚В闂骞跺噯澶囨煡璇笂涓嬫枃銆?",
                render_fallback: {
                  text: "姝ｅ湪鐞嗚В闂骞跺噯澶囨煡璇笂涓嬫枃銆?",
                  type: "text",
                },
                ag_ui: {
                  version: "1.x",
                  events: [
                    {
                      type: "CUSTOM",
                      name: "anybackup.conversation.thought.render",
                      value: {
                        status: "running",
                        summary: "姝ｅ湪鎻愬彇鐢ㄦ埛鐩爣鍜屼笂涓嬫枃绾跨储銆?",
                        core_agent_run_id: "mock-run-001",
                      },
                    },
                  ],
                },
              },
              ag_ui_sequence: 1,
            },
            occurred_at: "2026-04-23T12:57:37.138000Z",
          },
          {
            status_event_id: "evt_result_real_payload",
            conversation_id: "conv_real_payload",
            turn_id: "turn_real_001",
            message_id: "msg_result_real_001",
            event_type: "rich_content.created",
            sequence: 6,
            interaction_status: "completed",
            message_status: "responded",
            payload: {
              message: {
                message_id: "msg_result_real_001",
                conversation_id: "conv_real_payload",
                turn_id: "turn_real_001",
                parent_message_id: "msg_user_real_001",
                role: "assistant",
                content_type: "rich_content",
                content: "宸插畬鎴愪細璇濈殑妯℃嫙鍒嗘瀽锛岀敓鎴愮粨鏋滄壒娆?mock-940銆?",
                status: "responded",
              },
              rich_payload: {
                content_summary: "宸插畬鎴愪細璇濈殑妯℃嫙鍒嗘瀽锛岀敓鎴愮粨鏋滄壒娆?mock-940銆?",
                render_fallback: {
                  text: "宸插畬鎴愪細璇濈殑妯℃嫙鍒嗘瀽锛岀敓鎴愮粨鏋滄壒娆?mock-940銆?",
                  type: "text",
                },
                ag_ui: {
                  version: "1.x",
                  events: [
                    {
                      type: "CUSTOM",
                      name: "anybackup.conversation.result.render",
                      value: {
                        title: "妯℃嫙鍒嗘瀽缁撴灉",
                        summary: "宸插畬鎴愪細璇濈殑妯℃嫙鍒嗘瀽锛岀敓鎴愮粨鏋滄壒娆?mock-940銆?",
                        result_id: "mock-940",
                        source_message: "娴嬭瘯瀵硅瘽",
                      },
                    },
                  ],
                },
              },
              ag_ui_sequence: 2,
            },
            occurred_at: "2026-04-23T12:57:37.942000Z",
          },
          {
            status_event_id: "evt_unknown_real_payload",
            conversation_id: "conv_real_payload",
            turn_id: "turn_real_001",
            message_id: "msg_unknown_real_001",
            event_type: "rich_content.created",
            sequence: 7,
            interaction_status: "completed",
            message_status: "responded",
            payload: {
              message: {
                message_id: "msg_unknown_real_001",
                conversation_id: "conv_real_payload",
                turn_id: "turn_real_001",
                parent_message_id: "msg_user_real_001",
                role: "assistant",
                content_type: "rich_content",
                content: "宸茬敓鎴愪竴浠藉彲瑙嗗寲鍒嗘瀽銆?",
                status: "responded",
              },
              rich_payload: {
                content_summary: "宸茬敓鎴愪竴浠藉彲瑙嗗寲鍒嗘瀽銆?",
                ag_ui: {
                  version: "1.x",
                  events: [
                    {
                      type: "CUSTOM",
                      name: "anybackup.conversation.chart.render",
                      value: {
                        title: "瓒嬪娍鍥?",
                        summary: "宸茬敓鎴愪竴浠藉彲瑙嗗寲鍒嗘瀽銆?",
                      },
                    },
                  ],
                },
              },
              ag_ui_sequence: 3,
            },
            occurred_at: "2026-04-23T12:57:38.000000Z",
          },
        ],
        page: {
          next_cursor: null,
          has_more: false,
          limit: 50,
        },
        latest_sequence: 7,
        recommended_poll_interval_ms: 5000,
        interaction_status: "completed",
      }),
    )

    vi.stubGlobal("fetch", fetchMock)

    const result = await listConversationEvents("conv_real_payload")

    expect(result.events[0]?.message).toMatchObject({
      messageId: "msg_thought_real_001",
      parentMessageId: "msg_user_real_001",
      agUiSequence: 1,
      agUiEventName: "anybackup.conversation.thought.render",
      richPayload: {
        kind: "thought",
        data: {
          status: "running",
          summary: "姝ｅ湪鎻愬彇鐢ㄦ埛鐩爣鍜屼笂涓嬫枃绾跨储銆?",
        },
      },
    })
    expect(result.events[1]?.message).toMatchObject({
      messageId: "msg_result_real_001",
      agUiSequence: 2,
      agUiEventName: "anybackup.conversation.result.render",
      richPayload: {
        kind: "result",
        data: {
          title: "妯℃嫙鍒嗘瀽缁撴灉",
          summary: "宸插畬鎴愪細璇濈殑妯℃嫙鍒嗘瀽锛岀敓鎴愮粨鏋滄壒娆?mock-940銆?",
          resultId: "mock-940",
          sourceMessage: "娴嬭瘯瀵硅瘽",
        },
      },
    })
    expect(result.events[2]?.message).toMatchObject({
      messageId: "msg_unknown_real_001",
      agUiSequence: 3,
      agUiEventName: "anybackup.conversation.chart.render",
      richPayload: {
        kind: "ag_ui",
        data: {
          eventName: "anybackup.conversation.chart.render",
          title: "瓒嬪娍鍥?",
          summary: "宸茬敓鎴愪竴浠藉彲瑙嗗寲鍒嗘瀽銆?",
        },
      },
    })
  })

  it("creates a conversation and sends follow-up messages through the new contract", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse(
          {
            conversation: {
              conversation_id: "conv_new_001",
              owner_user_id: "user_001",
              title: "璁㈠崟鏁版嵁搴撴仮澶?",
              status: "created",
              summary: "鐢ㄦ埛鍒氬彂璧锋仮澶嶉渶姹傘€?",
              tags: ["restore"],
              latest_message_summary: "甯垜鎭㈠璁㈠崟鏁版嵁搴?",
              interaction_status: "thinking",
              active_turn_id: "turn_001",
              created_at: "2026-04-21T09:00:00.000Z",
              updated_at: "2026-04-21T09:00:00.000Z",
              last_active_at: "2026-04-21T09:00:00.000Z",
              retention_policy: {},
              legal_hold: false,
            },
            message: {
              message_id: "msg_user_001",
              conversation_id: "conv_new_001",
              turn_id: "turn_001",
              client_message_id: "client_msg_001",
              role: "user",
              content_type: "text",
              content: "甯垜鎭㈠璁㈠崟鏁版嵁搴?",
              status: "persisted",
              created_at: "2026-04-21T09:00:00.000Z",
            },
            status_event: {
              status_event_id: "evt_status_001",
              conversation_id: "conv_new_001",
              turn_id: "turn_001",
              message_id: "msg_user_001",
              event_type: "message.created",
              sequence: 1,
              interaction_status: "thinking",
              message_status: "persisted",
              payload: {
                message: {
                  message_id: "msg_user_001",
                  conversation_id: "conv_new_001",
                  turn_id: "turn_001",
                  role: "user",
                  content_type: "text",
                  content: "甯垜鎭㈠璁㈠崟鏁版嵁搴?",
                  status: "persisted",
                  created_at: "2026-04-21T09:00:00.000Z",
                },
              },
              created_at: "2026-04-21T09:00:00.000Z",
            },
            next_poll_after_ms: 1000,
          },
          201,
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          {
            conversation: {
              conversation_id: "conv_new_001",
              owner_user_id: "user_001",
              title: "璁㈠崟鏁版嵁搴撴仮澶?",
              status: "active",
              summary: "缁х画琛ュ厖鎭㈠鏃堕棿鐐广€?",
              tags: ["restore"],
              latest_message_summary: "鎭㈠鍒?2026-04-19",
              interaction_status: "thinking",
              active_turn_id: "turn_002",
              created_at: "2026-04-21T09:00:00.000Z",
              updated_at: "2026-04-21T09:01:00.000Z",
              last_active_at: "2026-04-21T09:01:00.000Z",
              retention_policy: {},
              legal_hold: false,
            },
            message: {
              message_id: "msg_user_002",
              conversation_id: "conv_new_001",
              turn_id: "turn_002",
              role: "user",
              content_type: "text",
              content: "鎭㈠鍒?2026-04-19",
              status: "persisted",
              created_at: "2026-04-21T09:01:00.000Z",
            },
            status_event: {
              status_event_id: "evt_status_002",
              conversation_id: "conv_new_001",
              turn_id: "turn_002",
              message_id: "msg_user_002",
              event_type: "message.created",
              sequence: 2,
              interaction_status: "thinking",
              message_status: "persisted",
              payload: {
                message: {
                  message_id: "msg_user_002",
                  conversation_id: "conv_new_001",
                  turn_id: "turn_002",
                  role: "user",
                  content_type: "text",
                  content: "鎭㈠鍒?2026-04-19",
                  status: "persisted",
                  created_at: "2026-04-21T09:01:00.000Z",
                },
              },
              created_at: "2026-04-21T09:01:00.000Z",
            },
            next_poll_after_ms: 1500,
          },
          202,
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          {
            conversation: {
              conversation_id: "conv_new_001",
              owner_user_id: "user_001",
              title: "璁㈠崟鏁版嵁搴撴仮澶?",
              status: "active",
              summary: "宸茬‘璁ゆ帹鑽愭柟妗堛€?",
              tags: ["restore"],
              latest_message_summary: "纭鎺ㄨ崘鏂规锛氭仮澶嶅埌 2026-04-19 14:45",
              interaction_status: "thinking",
              active_turn_id: "turn_003",
              created_at: "2026-04-21T09:00:00.000Z",
              updated_at: "2026-04-21T09:02:00.000Z",
              last_active_at: "2026-04-21T09:02:00.000Z",
              retention_policy: {},
              legal_hold: false,
            },
            message: {
              message_id: "msg_user_selection_001",
              conversation_id: "conv_new_001",
              turn_id: "turn_003",
              role: "user",
              content_type: "text",
              content: "纭鎺ㄨ崘鏂规锛氭仮澶嶅埌 2026-04-19 14:45",
              status: "persisted",
              created_at: "2026-04-21T09:02:00.000Z",
            },
            status_event: {
              status_event_id: "evt_status_003",
              conversation_id: "conv_new_001",
              turn_id: "turn_003",
              message_id: "msg_user_selection_001",
              event_type: "message.created",
              sequence: 3,
              interaction_status: "thinking",
              message_status: "persisted",
              payload: {
                message: {
                  message_id: "msg_user_selection_001",
                  conversation_id: "conv_new_001",
                  turn_id: "turn_003",
                  role: "user",
                  content_type: "text",
                  content: "纭鎺ㄨ崘鏂规锛氭仮澶嶅埌 2026-04-19 14:45",
                  status: "persisted",
                  created_at: "2026-04-21T09:02:00.000Z",
                },
              },
              created_at: "2026-04-21T09:02:00.000Z",
            },
            next_poll_after_ms: 1200,
          },
          202,
        ),
      )
      .mockResolvedValueOnce(
        jsonResponse(
          {
            conversation: {
              conversation_id: "conv_new_001",
              owner_user_id: "user_001",
              title: "澄清恢复时间窗口",
              status: "active",
              summary: "已确认最近安全点。",
              tags: ["restore"],
              latest_message_summary: "确认恢复窗口：最近安全点",
              interaction_status: "thinking",
              active_turn_id: "turn_004",
              created_at: "2026-04-21T09:00:00.000Z",
              updated_at: "2026-04-21T09:03:00.000Z",
              last_active_at: "2026-04-21T09:03:00.000Z",
              retention_policy: {},
              legal_hold: false,
            },
            message: {
              message_id: "msg_clarification_001",
              conversation_id: "conv_new_001",
              turn_id: "turn_004",
              role: "user",
              content_type: "text",
              content: "确认恢复窗口：最近安全点",
              status: "persisted",
              created_at: "2026-04-21T09:03:00.000Z",
            },
            status_event: {
              status_event_id: "evt_status_004",
              conversation_id: "conv_new_001",
              turn_id: "turn_004",
              message_id: "msg_clarification_001",
              event_type: "message.created",
              sequence: 4,
              interaction_status: "thinking",
              message_status: "persisted",
              payload: {
                message: {
                  message_id: "msg_clarification_001",
                  conversation_id: "conv_new_001",
                  turn_id: "turn_004",
                  role: "user",
                  content_type: "text",
                  content: "确认恢复窗口：最近安全点",
                  status: "persisted",
                  created_at: "2026-04-21T09:03:00.000Z",
                },
              },
              created_at: "2026-04-21T09:03:00.000Z",
            },
            next_poll_after_ms: 900,
          },
          202,
        ),
      )

    vi.stubGlobal("fetch", fetchMock)

    const created = await createConversation({
      initialMessage: {
        type: "user_message",
        content: "甯垜鎭㈠璁㈠崟鏁版嵁搴?",
        clientMessageId: "client_msg_001",
      },
      title: "璁㈠崟鏁版嵁搴撴仮澶?",
      tags: ["restore"],
    })

    expect(created.conversation.conversationId).toBe("conv_new_001")
    expect(created.conversation.activeTurnId).toBe("turn_001")
    expect(created.message.turnId).toBe("turn_001")
    expect(created.message.clientMessageId).toBe("client_msg_001")
    expect(created.statusEvent).toMatchObject({
      statusEventId: "evt_status_001",
      conversationId: "conv_new_001",
      turnId: "turn_001",
      eventType: "message.created",
      sequence: 1,
      interactionState: "thinking",
      messageStatus: "persisted",
    })
    expect(created.statusEvent.message).toMatchObject({
      messageId: "msg_user_001",
      turnId: "turn_001",
      content: "甯垜鎭㈠璁㈠崟鏁版嵁搴?",
    })
    expect(created.nextPollAfterMs).toBe(1000)

    const [, createInit] = fetchMock.mock.calls[0] ?? []
    const createHeaders = new Headers(createInit?.headers)
    expect(createInit?.method).toBe("POST")
    expect(createHeaders.get("Content-Type")).toBe("application/json")
    expect(createHeaders.get("Idempotency-Key")).toBeTruthy()

    const createBody = JSON.parse(String(createInit?.body))
    expect(createBody.initial_message.type).toBe("user_message")
    expect(createBody.source).toBe("web")

    const sent = await sendMessage("conv_new_001", {
      type: "user_message",
      content: "鎭㈠鍒?2026-04-19",
    })

    expect(sent.message.content).toBe("鎭㈠鍒?2026-04-19")
    const [sendUrl, sendInit] = fetchMock.mock.calls[1] ?? []
    expect(String(sendUrl)).toContain("/conversations/conv_new_001/messages")
    expect(sendInit?.method).toBe("POST")
    expect(new Headers(sendInit?.headers).get("Idempotency-Key")).toBeTruthy()

    await sendMessage("conv_new_001", {
      type: "candidate_selection",
      messageId: "msg_candidate_001",
      reasoningTraceId: "trace_restore_001",
      candidateOptionId: "option_a",
      selection: "confirm",
      additionalConstraints: "鍏堢敓鎴愭柟妗堬紝涓嶈绔嬪嵆鎵ц",
    })

    const [, selectionInit] = fetchMock.mock.calls[2] ?? []
    const selectionBody = JSON.parse(String(selectionInit?.body))
    expect(selectionBody).toMatchObject({
      type: "candidate_selection",
      message_id: "msg_candidate_001",
      reasoning_trace_id: "trace_restore_001",
      candidate_option_id: "option_a",
      selection: "confirm",
      additional_constraints: "鍏堢敓鎴愭柟妗堬紝涓嶈绔嬪嵆鎵ц",
    })

    await sendMessage("conv_new_001", {
      type: "clarification_response",
      messageId: "msg_clarification_prompt_001",
      clarificationId: "restore_window",
      selectedValue: "latest_safe_point",
      freeText: "最近安全点",
    })

    const [, clarificationInit] = fetchMock.mock.calls[3] ?? []
    const clarificationBody = JSON.parse(String(clarificationInit?.body))
    expect(clarificationBody).toMatchObject({
      type: "clarification_response",
      message_id: "msg_clarification_prompt_001",
      clarification_id: "restore_window",
      selected_value: "latest_safe_point",
      free_text: "最近安全点",
    })
  })
})
