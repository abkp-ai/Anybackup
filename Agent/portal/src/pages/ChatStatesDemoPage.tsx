import { useMemo, useState } from "react"
import { CheckCircle2, CircleHelp, Clock3, MessagesSquare } from "lucide-react"
import {
  AgUiLayoutTreeRenderer,
  type LayoutTreeActionEvent,
  type LayoutTreeContent,
  type LayoutTreeStateSnapshot,
} from "@/components/chat/components/ag-ui-layout-tree-renderer"
import { ChatMessageList } from "@/components/chat/components/chat-message-list"
import { routes } from "@/config/routes"
import { useI18n } from "@/i18n"
import { cn } from "@/lib/cn"
import { buildChatStatesDemoData } from "@/pages/chat-states-demo-data"
import type { CandidateSelectionInput, ClarificationResponseInput, ConversationMessageSummary } from "@/types/conversation"

const now = "2026-04-22T16:00:00+08:00"

const clarificationMessages: ConversationMessageSummary[] = [
  {
    messageId: "demo-user-004",
    conversationId: "demo-clarification",
    role: "user",
    contentType: "text",
    content: "Please clarify the restore window for the demo task.",
    createdAt: now,
    status: "responded",
  },
  {
    messageId: "demo-assistant-004",
    conversationId: "demo-clarification",
    role: "assistant",
    contentType: "clarification",
    content: "Please confirm the restore window.",
    createdAt: "2026-04-22T16:01:10+08:00",
    status: "responded",
    richPayload: {
      kind: "clarification",
      data: {
        clarificationId: "restore_window",
        prompt: "Please confirm the restore window.",
        options: [
          { label: "Latest safe point", value: "latest_safe_point" },
          { label: "Custom timestamp", value: "custom_timestamp" },
        ],
        inputConstraints: {
          required: true,
          allowFreeText: true,
          freeTextLabel: "Restore time",
          freeTextPlaceholder: "For example: 2026-04-23 21:30:00",
        },
      },
    },
  },
]

const layoutTreeNodeGalleryActivity: LayoutTreeContent = {
  contract: "conversation.ui.layout-tree@1",
  blockId: "node_gallery_001",
  ui: {
    id: "gallery_root",
    type: "stack",
    props: { gap: "lg" },
    children: [
      {
        id: "gallery_header",
        type: "section",
        props: { gap: "sm" },
        children: [
          {
            type: "heading",
            props: {
              level: 2,
              text: "Node Gallery",
            },
          },
          {
            type: "paragraph",
            props: {
              text: "This block focuses on the remaining protocol nodes: tabs, markdown, data-table, chart, attachment-list, divider, and all action kinds.",
            },
          },
        ],
      },
      {
        id: "gallery_tabs",
        type: "tabs",
        props: {
          defaultTabId: "overview",
          items: [
            { id: "overview", label: "Overview" },
            { id: "data", label: "Data & Refs" },
            { id: "actions", label: "Actions" },
          ],
        },
        children: [
          {
            id: "overview",
            type: "stack",
            props: { gap: "md", tabLabel: "Overview" },
            children: [
              {
                type: "card",
                props: { gap: "md" },
                children: [
                  {
                    type: "heading",
                    props: {
                      level: 3,
                      text: "Markdown + Divider + Chart",
                    },
                  },
                  {
                    type: "markdown",
                    props: {
                      text: "## Recovery checklist\n- Verify snapshot integrity\n- Confirm restore target\n- Export validation report",
                    },
                  },
                  {
                    type: "divider",
                  },
                  {
                    type: "chart",
                    props: {
                      title: "Recovery score by candidate",
                      items: [
                        { label: "Candidate A", value: 92, tone: "info" },
                        { label: "Candidate B", value: 75, tone: "warning" },
                        { label: "Candidate C", value: 61, tone: "danger" },
                      ],
                    },
                  },
                ],
              },
            ],
          },
          {
            id: "data",
            type: "stack",
            props: { gap: "md", tabLabel: "Data & Refs" },
            children: [
              {
                type: "card",
                props: { gap: "md" },
                children: [
                  {
                    type: "heading",
                    props: {
                      level: 3,
                      text: "Structured data table",
                    },
                  },
                  {
                    type: "data-table",
                    props: {
                      columns: [
                        { key: "name", label: "Object" },
                        { key: "impact", label: "Impact" },
                        { key: "owner", label: "Owner" },
                      ],
                      rows: [
                        { name: "order_details", impact: "High", owner: "Order Team" },
                        { name: "order_items", impact: "Medium", owner: "Order Team" },
                        { name: "refund_queue", impact: "Low", owner: "Ops" },
                      ],
                    },
                  },
                  {
                    type: "attachment-list",
                    props: {
                      items: [
                        {
                          title: "Recovery assessment report",
                          summary: "Contains the scoring model, risk notes, and operator checklist.",
                        },
                        {
                          title: "Snapshot validation log",
                          summary: "Checksum and consistency audit generated before restore planning.",
                        },
                      ],
                    },
                  },
                ],
              },
            ],
          },
          {
            id: "actions",
            type: "stack",
            props: { gap: "md", tabLabel: "Actions" },
            children: [
              {
                type: "callout",
                props: {
                  tone: "info",
                  title: "Action kinds",
                  text: "This tab shows the four whitelisted action kinds in the protocol. Only submit_message changes local selection state; the others are handled as controlled side effects.",
                },
              },
              {
                type: "action-row",
                props: {
                  actionIds: ["gallery_copy_text", "gallery_open_ref", "gallery_open_url", "gallery_submit_message"],
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
      id: "gallery_copy_text",
      kind: "copy_text",
      label: "Copy report id",
      style: "secondary",
      payload: {
        text: "report_restore_20260424_001",
      },
    },
    {
      id: "gallery_open_ref",
      kind: "open_ref",
      label: "Open internal reference",
      style: "secondary",
      payload: {
        ref_id: "report_restore_20260424_001",
      },
    },
    {
      id: "gallery_open_url",
      kind: "open_url",
      label: "Open external report",
      style: "link",
      payload: {
        url: "https://example.com/recovery-report",
      },
    },
    {
      id: "gallery_submit_message",
      kind: "submit_message",
      label: "Send follow-up message",
      style: "primary",
      payload: {
        type: "user_message",
        content: "Please continue with the selected recovery plan.",
      },
    },
  ],
  meta: {
    intent: "result",
    terminal: true,
    reasoningTraceId: "trace_layout_tree_gallery_001",
  },
}

const layoutTreeNodeGalleryState: LayoutTreeStateSnapshot = {
  interaction: {
    status: "executing",
  },
}

interface DemoSectionProps {
  icon: typeof MessagesSquare
  title: string
  description: string
  contentClassName?: string
  children: React.ReactNode
  testId?: string
}

function DemoSection({ icon: Icon, title, description, contentClassName, children, testId }: DemoSectionProps) {
  return (
    <section data-testid={testId} className="overflow-hidden rounded-xl border border-border/70 bg-card shadow-card">
      <header className="border-b border-border/60 bg-white/80 px-5 py-4 backdrop-blur-sm">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-ai/10 text-ai">
            <Icon className="h-5 w-5" />
          </div>
          <div className="space-y-1">
            <h2 className="text-base font-semibold text-foreground">{title}</h2>
            <p className="text-sm leading-6 text-muted-foreground">{description}</p>
          </div>
        </div>
      </header>
      <div className={cn("h-[30rem] min-h-0 bg-gradient-hero", contentClassName)}>{children}</div>
    </section>
  )
}

export function ChatStatesDemoPage() {
  const { t, locale } = useI18n()
  const demo = useMemo(() => buildChatStatesDemoData(t), [t, locale])

  const [lastSelection, setLastSelection] = useState<CandidateSelectionInput | null>(null)
  const [lastClarificationResponse, setLastClarificationResponse] = useState<ClarificationResponseInput | null>(null)
  const [lastLayoutTreeAction, setLastLayoutTreeAction] = useState<Record<string, unknown> | null>(null)
  const [lastNodeGalleryAction, setLastNodeGalleryAction] = useState<LayoutTreeActionEvent | null>(null)

  const selectionSummary = useMemo(() => {
    if (!lastSelection) return t("demo.selection.none")

    if (lastSelection.selection === "confirm") {
      return `${t("demo.selection.confirm")}${lastSelection.candidateOptionId}`
    }

    if (lastSelection.selection === "reject") {
      return `${t("demo.selection.reject")}${lastSelection.candidateOptionId}`
    }

    return `${t("demo.selection.revise")}${lastSelection.additionalConstraints ?? t("demo.selection.reviseEmpty")}`
  }, [lastSelection, t])

  const clarificationSummary = useMemo(() => {
    if (!lastClarificationResponse) return "No clarification has been submitted yet."

    const parts = [
      lastClarificationResponse.selectedValue ? `selected=${lastClarificationResponse.selectedValue}` : null,
      lastClarificationResponse.freeText ? `input=${lastClarificationResponse.freeText}` : null,
    ].filter(Boolean)

    return parts.length > 0 ? `Last clarification response: ${parts.join(", ")}` : "Last clarification response submitted."
  }, [lastClarificationResponse])

  const layoutTreeSummary = useMemo(() => {
    if (!lastLayoutTreeAction) return t("demo.layout.none")

    const payloadType = typeof lastLayoutTreeAction.type === "string" ? lastLayoutTreeAction.type : "unknown"
    const candidateId =
      typeof lastLayoutTreeAction.candidate_option_id === "string" ? lastLayoutTreeAction.candidate_option_id : null

    return candidateId
      ? `${t("demo.layout.last")}${payloadType} -> ${candidateId}`
      : `${t("demo.layout.last")}${payloadType}`
  }, [lastLayoutTreeAction, t])

  const nodeGallerySummary = useMemo(() => {
    if (!lastNodeGalleryAction) return "No node-gallery action has fired yet."

    const payloadType =
      lastNodeGalleryAction.payload && typeof lastNodeGalleryAction.payload.type === "string"
        ? lastNodeGalleryAction.payload.type
        : null

    return payloadType
      ? `Last action: ${lastNodeGalleryAction.kind} -> ${payloadType}`
      : `Last action: ${lastNodeGalleryAction.kind} -> ${lastNodeGalleryAction.label}`
  }, [lastNodeGalleryAction])

  return (
    <div className="h-full min-h-0 flex-1 overflow-auto bg-gradient-hero px-4 pb-6 pt-4 md:px-8">
      <div className="mx-auto max-w-6xl space-y-6">
        <header className="rounded-xl border border-border/70 bg-card/95 px-6 py-5 shadow-card backdrop-blur-sm">
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-ai">Chat Demo</p>
          <div className="mt-2 flex flex-wrap items-center justify-between gap-4">
            <div className="space-y-2">
              <h1 className="text-h2 font-semibold text-foreground">{t("demo.pageTitle")}</h1>
              <p className="max-w-3xl text-sm leading-6 text-muted-foreground">{t("demo.pageSubtitle")}</p>
            </div>
            <div className="rounded-lg border border-border/70 bg-background/80 px-4 py-3 text-xs text-muted-foreground">
              {t("demo.visitPath")} <span className="font-semibold text-foreground">{routes.chatDemo}</span>
            </div>
          </div>
        </header>

        <DemoSection
          icon={CheckCircle2}
          title={t("demo.sectionLayoutTitle")}
          description={t("demo.sectionLayoutTreeDesc")}
          contentClassName="h-auto"
          testId="chat-demo-layout-tree-section"
        >
          <div className="flex min-h-0 flex-col">
            <div className="border-b border-border/60 bg-white/70 px-5 py-3 text-sm text-muted-foreground">
              <span className="font-medium text-foreground">{t("demo.protocolActionFeedback")}</span> {layoutTreeSummary}
            </div>
            <div className="p-5" data-testid="chat-demo-layout-tree-panel">
              <AgUiLayoutTreeRenderer
                activity={demo.layoutTreeDemoActivity}
                stateSnapshot={demo.layoutTreeDemoState}
                onSubmitMessage={setLastLayoutTreeAction}
                testId="chat-demo-layout-tree-renderer"
              />
            </div>
          </div>
        </DemoSection>

        <DemoSection
          icon={MessagesSquare}
          title="AG-UI Node Gallery"
          description={t("demo.sectionNodeGalleryDesc")}
          contentClassName="h-auto"
        >
          <div className="flex min-h-0 flex-col">
            <div className="border-b border-border/60 bg-white/70 px-5 py-3 text-sm text-muted-foreground">
              <span className="font-medium text-foreground">Node gallery feedback:</span> {nodeGallerySummary}
            </div>
            <div className="p-5">
              <AgUiLayoutTreeRenderer
                activity={layoutTreeNodeGalleryActivity}
                stateSnapshot={layoutTreeNodeGalleryState}
                onAction={setLastNodeGalleryAction}
              />
            </div>
          </div>
        </DemoSection>

        <DemoSection
          icon={CheckCircle2}
          title={t("demo.sectionCandidateTitle")}
          description={t("demo.sectionCandidateDesc")}
          contentClassName="h-auto"
        >
          <div className="flex min-h-0 flex-col">
            <div className="border-b border-border/60 bg-white/70 px-5 py-3 text-sm text-muted-foreground">
              <span className="font-medium text-foreground">{t("demo.lastInteraction")}</span> {selectionSummary}
            </div>
            <div className="min-h-0">
              <ChatMessageList
                title={t("demo.listTitleRestore")}
                summary={t("demo.listSummaryCandidate")}
                messages={demo.candidateMessages}
                submittingSelectionMessageId={undefined}
                expandToContent
                onCandidateSelection={setLastSelection}
              />
            </div>
          </div>
        </DemoSection>

        <DemoSection
          icon={CircleHelp}
          title="Clarification Card Demo"
          description="A structured clarification card for user confirmation and follow-up input."
          contentClassName="h-auto"
        >
          <div className="flex min-h-0 flex-col">
            <div className="border-b border-border/60 bg-white/70 px-5 py-3 text-sm text-muted-foreground">
              <span className="font-medium text-foreground">Latest clarification:</span> {clarificationSummary}
            </div>
            <div className="min-h-0">
              <ChatMessageList
                title="Clarification demo"
                summary="Clarification rich content rendering"
                messages={clarificationMessages}
                expandToContent
                onCandidateSelection={() => undefined}
                onClarificationResponse={setLastClarificationResponse}
              />
            </div>
          </div>
        </DemoSection>

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
          <DemoSection icon={MessagesSquare} title={t("demo.sectionTextTitle")} description={t("demo.sectionTextDesc")}>
            <ChatMessageList
              title={t("demo.listTitleBackupQuery")}
              summary={t("demo.listSummaryPlain")}
              messages={demo.textMessages}
              onCandidateSelection={() => undefined}
            />
          </DemoSection>

          <DemoSection
            icon={Clock3}
            title={t("demo.sectionWaitingTitle")}
            description={t("demo.sectionWaitingDesc")}
          >
            <ChatMessageList
              title={t("demo.listTitleGenerating")}
              summary={t("demo.listSummaryWaiting")}
              messages={demo.waitingMessages}
              isAwaitingReply
              onCandidateSelection={() => undefined}
            />
          </DemoSection>
        </div>
      </div>
    </div>
  )
}
