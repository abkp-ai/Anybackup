import type { LayoutTreeContent, LayoutTreeStateSnapshot } from "@/components/chat/components/ag-ui-layout-tree-renderer"
import type { MessageKey } from "@/i18n/messages"
import type { ConversationMessageSummary } from "@/types/conversation"

const now = "2026-04-22T16:00:00+08:00"

type T = (key: MessageKey) => string

export function buildChatStatesDemoData(t: T) {
  const textMessages: ConversationMessageSummary[] = [
    {
      messageId: "demo-user-001",
      conversationId: "demo-text",
      role: "user",
      contentType: "text",
      content: t("demo.text.user.backupStatus"),
      createdAt: now,
      status: "responded",
    },
    {
      messageId: "demo-assistant-001",
      conversationId: "demo-text",
      role: "assistant",
      contentType: "text",
      content: t("demo.text.assistant.backupStatus"),
      createdAt: "2026-04-22T16:00:12+08:00",
      status: "responded",
    },
  ]

  const waitingMessages: ConversationMessageSummary[] = [
    {
      messageId: "demo-user-002",
      conversationId: "demo-waiting",
      role: "user",
      contentType: "text",
      content: t("demo.waiting.user.restorePlan"),
      createdAt: now,
      status: "persisted",
    },
  ]

  const candidateMessages: ConversationMessageSummary[] = [
    {
      messageId: "demo-user-003",
      conversationId: "demo-candidate",
      role: "user",
      contentType: "text",
      content: t("demo.candidate.user.message"),
      createdAt: now,
      status: "responded",
    },
    {
      messageId: "demo-assistant-003",
      conversationId: "demo-candidate",
      role: "assistant",
      contentType: "rich_content",
      content: t("demo.candidate.assistant.lead"),
      createdAt: "2026-04-22T16:00:20+08:00",
      status: "responded",
      richPayload: {
        kind: "candidate_options",
        data: {
          reasoningTraceId: "trace_restore_demo_001",
          title: t("demo.candidate.cardTitle"),
          summary: t("demo.candidate.cardSummary"),
          actions: [
            { type: "confirm", label: t("demo.candidate.actionConfirm") },
            { type: "reject", label: t("demo.candidate.actionReject") },
            {
              type: "revise",
              label: t("demo.candidate.actionRevise"),
              inputLabel: t("demo.candidate.reviseInputLabel"),
              inputPlaceholder: t("demo.candidate.revisePlaceholder"),
              submitLabel: t("demo.candidate.reviseSubmit"),
            },
          ],
          options: [
            {
              optionId: "option_a",
              title: t("demo.optionA.title"),
              recommended: true,
              summary: t("demo.optionA.summary"),
              fields: [
                { key: "restore_scope", label: t("demo.field.restoreScope"), value: t("demo.value.dbAsset") },
                { key: "rpo_rto", label: t("demo.field.rpoRto"), value: t("demo.value.rpoRtoA") },
                { key: "target", label: t("demo.field.target"), value: t("demo.value.targetMysql") },
                { key: "coverage", label: t("demo.field.coverage"), value: t("demo.value.coverageTable") },
              ],
              extra: {
                title: t("demo.optionA.extraTitle"),
                content: t("demo.optionA.extraBody"),
              },
            },
            {
              optionId: "option_b",
              title: t("demo.optionB.title"),
              summary: t("demo.optionB.summary"),
              fields: [
                { key: "restore_scope", label: t("demo.field.restoreScope"), value: t("demo.value.dbAsset") },
                { key: "rpo_rto", label: t("demo.field.rpoRto"), value: t("demo.value.rpoRtoB") },
                { key: "target", label: t("demo.field.target"), value: t("demo.value.targetProd") },
                { key: "coverage", label: t("demo.field.coverage"), value: t("demo.value.coverageFullDb") },
              ],
              extra: {
                title: t("demo.optionB.extraTitle"),
                content: t("demo.optionB.extraBody"),
              },
            },
            {
              optionId: "option_c",
              title: t("demo.optionC.title"),
              summary: t("demo.optionC.summary"),
              fields: [
                { key: "restore_scope", label: t("demo.field.restoreScope"), value: t("demo.value.dbAsset") },
                { key: "rpo_rto", label: t("demo.field.rpoRto"), value: t("demo.value.rpoRtoC") },
                { key: "target", label: t("demo.field.target"), value: t("demo.value.targetIso") },
                { key: "coverage", label: t("demo.field.coverage"), value: t("demo.value.coverageValidate") },
              ],
              extra: {
                title: t("demo.optionC.extraTitle"),
                content: t("demo.optionC.extraBody"),
              },
            },
          ],
        },
      },
    },
  ]

  const layoutTreeDemoActivity: LayoutTreeContent = {
    contract: "conversation.ui.layout-tree@1",
    blockId: "candidate_compare_001",
    ui: {
      id: "root",
      type: "stack",
      props: { gap: "lg" },
      children: [
        {
          id: "page_header",
          type: "section",
          props: { gap: "sm" },
          children: [
            {
              type: "heading",
              props: {
                level: 2,
                text: t("demo.layout.heading"),
              },
            },
            {
              type: "paragraph",
              props: {
                text: t("demo.layout.intro"),
              },
            },
          ],
        },
        {
          id: "candidate_grid",
          type: "grid",
          props: {
            columns: 3,
            gap: "md",
          },
          children: [
            {
              id: "candidate_a",
              type: "card",
              props: {
                tone: "highlight",
                gap: "md",
              },
              children: [
                {
                  type: "heading",
                  props: {
                    level: 3,
                    text: t("demo.optionA.title"),
                  },
                },
                {
                  type: "badge-row",
                  props: {
                    items: [
                      { tone: "positive", text: t("demo.layout.badgeRecommended") },
                      { tone: "warning", text: t("demo.layout.badgeMediumRisk") },
                    ],
                  },
                },
                {
                  type: "paragraph",
                  props: {
                    text: t("demo.layout.paraA"),
                  },
                },
                {
                  type: "metric-list",
                  props: {
                    items: [
                      { label: t("demo.metric.rpo"), value: t("demo.metric.valueRpo") },
                      { label: t("demo.metric.rto"), value: t("demo.metric.valueRto") },
                      { label: t("demo.metric.success"), value: t("demo.metric.valueHigh") },
                    ],
                  },
                },
                {
                  type: "kv-list",
                  props: {
                    items: [
                      { label: t("demo.field.restoreScope"), value: t("demo.value.dbAsset") },
                      { label: t("demo.field.coverage"), value: t("demo.value.coverageTable") },
                      { label: t("demo.field.target"), value: t("demo.value.targetMysql") },
                    ],
                  },
                },
                {
                  type: "callout",
                  props: {
                    tone: "info",
                    title: t("demo.layout.calloutBizTitle"),
                    text: t("demo.layout.calloutBizText"),
                  },
                },
                {
                  type: "action-row",
                  props: {
                    actionIds: ["choose_candidate_a", "view_candidate_a_detail"],
                  },
                },
              ],
            },
            {
              id: "candidate_b",
              type: "card",
              props: { gap: "md" },
              children: [
                {
                  type: "heading",
                  props: {
                    level: 3,
                    text: t("demo.layout.titleB"),
                  },
                },
                {
                  type: "badge-row",
                  props: {
                    items: [{ tone: "warning", text: t("demo.layout.badgeHighResource") }],
                  },
                },
                {
                  type: "paragraph",
                  props: {
                    text: t("demo.layout.paraB"),
                  },
                },
                {
                  type: "kv-list",
                  props: {
                    items: [
                      { label: t("demo.field.restoreScope"), value: t("demo.layout.kvFullDb") },
                      { label: t("demo.layout.resourceUsageLabel"), value: t("demo.layout.kvResourceHigh") },
                      { label: t("demo.layout.execComplexityLabel"), value: t("demo.layout.kvComplexityMid") },
                    ],
                  },
                },
                {
                  type: "action-row",
                  props: {
                    actionIds: ["choose_candidate_b"],
                  },
                },
              ],
            },
            {
              id: "candidate_c",
              type: "card",
              props: { gap: "md" },
              children: [
                {
                  type: "heading",
                  props: {
                    level: 3,
                    text: t("demo.layout.titleC"),
                  },
                },
                {
                  type: "badge-row",
                  props: {
                    items: [{ tone: "danger", text: t("demo.layout.badgeConsistency") }],
                  },
                },
                {
                  type: "paragraph",
                  props: {
                    text: t("demo.layout.paraC"),
                  },
                },
                {
                  type: "callout",
                  props: {
                    tone: "warning",
                    title: t("demo.layout.riskTitle"),
                    text: t("demo.layout.riskBody"),
                  },
                },
                {
                  type: "action-row",
                  props: {
                    actionIds: ["choose_candidate_c"],
                  },
                },
              ],
            },
          ],
        },
      ],
    },
    actions: [
      {
        id: "choose_candidate_a",
        kind: "submit_message",
        label: t("demo.action.confirmA"),
        style: "primary",
        payload: {
          type: "candidate_selection",
          candidate_option_id: "candidate_a",
          selection: "confirm",
        },
      },
      {
        id: "view_candidate_a_detail",
        kind: "open_ref",
        label: t("demo.action.viewDetail"),
        style: "link",
        payload: {
          ref_id: "candidate_detail_a",
        },
      },
      {
        id: "choose_candidate_b",
        kind: "submit_message",
        label: t("demo.action.confirmB"),
        style: "secondary",
        payload: {
          type: "candidate_selection",
          candidate_option_id: "candidate_b",
          selection: "confirm",
        },
      },
      {
        id: "choose_candidate_c",
        kind: "submit_message",
        label: t("demo.action.confirmC"),
        style: "secondary",
        payload: {
          type: "candidate_selection",
          candidate_option_id: "candidate_c",
          selection: "confirm",
        },
      },
    ],
    meta: {
      intent: "result",
      terminal: true,
      reasoningTraceId: "trace_layout_tree_demo_001",
    },
  }

  const layoutTreeDemoState: LayoutTreeStateSnapshot = {
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
  }

  return {
    textMessages,
    waitingMessages,
    candidateMessages,
    layoutTreeDemoActivity,
    layoutTreeDemoState,
  }
}
