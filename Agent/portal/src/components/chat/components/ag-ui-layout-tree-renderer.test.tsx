import { fireEvent, render, screen } from "@testing-library/react"
import { describe, expect, it, vi } from "vitest"
import { AgUiLayoutTreeRenderer } from "@/components/chat/components/ag-ui-layout-tree-renderer"
import type { LayoutTreeContent, LayoutTreeStateSnapshot } from "@/types/conversation"

const activity: LayoutTreeContent = {
  contract: "conversation.ui.layout-tree@1",
  blockId: "candidate_compare_001",
  ui: {
    id: "root",
    type: "stack",
    children: [
      {
        id: "candidate_grid",
        type: "grid",
        props: {
          columns: 3,
          gap: "md",
        },
        children: [
          {
            id: "candidate_option_a",
            type: "card",
            props: {
              title: "Plan A: alternate-host database restore",
            },
            children: [
              {
                type: "paragraph",
                props: {
                  text: "Recommended because it limits production impact and preserves table scope.",
                },
              },
              {
                type: "badge-row",
                props: {
                  items: [
                    {
                      label: "Recommendation",
                      value: "recommended",
                    },
                    {
                      label: "Risk",
                      value: "medium",
                    },
                  ],
                },
              },
            ],
          },
        ],
      },
    ],
  },
}

const stateSnapshot: LayoutTreeStateSnapshot = {
  interaction: {
    status: "completed",
  },
  selection: {
    required: true,
    selectedCandidateOptionId: "candidate_option_a",
    selectionLocked: false,
  },
}

const candidateVisualStateSnapshot: LayoutTreeStateSnapshot = {
  interaction: {
    status: "completed",
  },
  selection: {
    required: true,
    selectedCandidateOptionId: "candidate_a",
    selectionLocked: false,
  },
}

const candidateVisualUnselectedStateSnapshot: LayoutTreeStateSnapshot = {
  interaction: {
    status: "completed",
  },
  selection: {
    required: true,
    selectedCandidateOptionId: null,
    selectionLocked: false,
  },
}

const errorActivity: LayoutTreeContent = {
  contract: "conversation.ui.layout-tree@1",
  blockId: "visible_error_954",
  ui: {
    id: "error_root",
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
          actionIds: ["retry_restore_search"],
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
  ],
  meta: {
    intent: "error",
    terminal: true,
  },
}

const errorStateSnapshot: LayoutTreeStateSnapshot = {
  interaction: {
    status: "error",
  },
}

const convergenceActivity: LayoutTreeContent = {
  contract: "conversation.ui.layout-tree@1",
  blockId: "convergence_001",
  ui: {
    id: "convergence_root",
    type: "grid",
    props: {
      columns: 3,
      gap: "md",
    },
    children: [
      {
        id: "candidate_option_long",
        type: "card",
        props: {
          title: "Restore directly on production host with an unusually long fallback plan title",
        },
        children: [
          {
            type: "paragraph",
            props: {
              text: "This card keeps long action labels and metric values from distorting the layout.",
            },
          },
          {
            type: "metric-list",
            props: {
              items: [
                {
                  label: "Window",
                  value: "requires longer write freeze and additional reconciliation review before execution can continue",
                },
                {
                  label: "",
                  value: "",
                },
              ],
            },
          },
          {
            type: "kv-list",
            props: {
              items: [
                {
                  label: "Target",
                  value: "Production database host",
                },
                {
                  label: "",
                  value: "",
                },
              ],
            },
          },
          {
            type: "badge-row",
            props: {
              items: [
                {
                  text: "",
                },
                {
                  text: "high risk",
                  tone: "danger",
                },
              ],
            },
          },
          {
            type: "paragraph",
            props: {
              text: "",
            },
          },
          {
            type: "action-row",
            props: {
              actionIds: ["long_primary_action", "long_secondary_action"],
            },
          },
        ],
      },
    ],
  },
  actions: [
    {
      id: "long_primary_action",
      kind: "submit_message",
      label:
        "Choose Restore directly on production host with a very long operation label that should wrap cleanly inside the card",
      style: "primary",
      payload: {
        action: "choose_long_candidate",
      },
    },
    {
      id: "long_secondary_action",
      kind: "open_ref",
      label:
        "Open details for Restore directly on production host with a very long operation label that should wrap cleanly inside the card",
      payload: {
        ref_id: "candidate-long-detail",
      },
    },
  ],
}

const candidateVisualActivity: LayoutTreeContent = {
  contract: "conversation.ui.layout-tree@1",
  blockId: "candidate_visual_001",
  ui: {
    id: "candidate_visual_root",
    type: "grid",
    props: {
      columns: 3,
      gap: "md",
    },
    children: [
      {
        id: "candidate_a",
        type: "card",
        children: [
          {
            type: "heading",
            props: {
              text: "Plan A: Restore by exporting the target table",
              level: 3,
            },
          },
          {
            type: "badge-row",
            props: {
              items: [
                {
                  text: "recommended",
                  tone: "positive",
                },
                {
                  text: "medium",
                  tone: "warning",
                },
              ],
            },
          },
          {
            type: "paragraph",
            props: {
              text: "Recommended path with controlled production impact.",
            },
          },
          {
            type: "kv-list",
            props: {
              items: [
                {
                  label: "Restore scope",
                  value: "Database-level",
                },
                {
                  label: "RPO / RTO",
                  value: "< 2 min / 1.5 h",
                },
              ],
            },
          },
          {
            type: "callout",
            props: {
              title: "Business impact",
              text: "This path keeps the production database isolated while recovering the target table.",
              tone: "info",
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
    ],
  },
  actions: [
    {
      id: "choose_candidate_a",
      kind: "submit_message",
      label: "Confirm restore plan",
      style: "primary",
      payload: {
        action: "confirm",
        reasoningTraceId: "trace-001",
        candidateOptionId: "candidate_a",
      },
    },
    {
      id: "view_candidate_a_detail",
      kind: "open_ref",
      label: "Open detailed explanation for the selected restore candidate with validation notes",
      payload: {
        ref_id: "candidate_a_detail",
      },
    },
  ],
}

const clarificationInputActivity: LayoutTreeContent = {
  contract: "conversation.ui.layout-tree@1",
  blockId: "clarification_input_001",
  ui: {
    id: "clarification_input_root",
    type: "stack",
    children: [
      {
        type: "action-row",
        props: {
          actionIds: ["submit_latest_safe_point", "submit_specific_timestamp"],
        },
      },
    ],
  },
  actions: [
    {
      id: "submit_latest_safe_point",
      kind: "submit_message",
      label: "Use latest safe point",
      style: "primary",
      payload: {
        type: "clarification_response",
        selectedValue: "latest_safe_point",
        clarificationId: "recovery_window",
      },
    },
    {
      id: "submit_specific_timestamp",
      kind: "submit_message",
      label: "Provide specific timestamp",
      payload: {
        type: "clarification_response",
        freeText: "2026-04-24T15:30:00+08:00",
        clarificationId: "recovery_window",
      },
    },
  ],
}

const markdownActivity: LayoutTreeContent = {
  contract: "conversation.ui.layout-tree@1",
  blockId: "markdown_001",
  ui: {
    id: "markdown_root",
    type: "stack",
    children: [
      {
        type: "markdown",
        props: {
          text: "1. **mysql3306_U0HYTDM3RENXS4EJ**\n\n请确认是否恢复此 MySQL 实例的最新备份时间点。",
        },
      },
    ],
  },
}

describe("AgUiLayoutTreeRenderer", () => {
  it("renders docs-style card titles and label/value badges", () => {
    render(<AgUiLayoutTreeRenderer activity={activity} stateSnapshot={stateSnapshot} showMeta={false} />)

    expect(screen.getByText("Plan A: alternate-host database restore")).toBeInTheDocument()
    expect(screen.getByText("Recommendation: recommended")).toBeInTheDocument()
    expect(screen.getByText("Risk: medium")).toBeInTheDocument()
  })

  it("renders error callouts while keeping recovery actions on their own button variant", () => {
    render(<AgUiLayoutTreeRenderer activity={errorActivity} stateSnapshot={errorStateSnapshot} showMeta={false} />)

    const callout = screen.getByText("The requested operation cannot continue without a valid restore point.").closest("div")
    const retryButton = screen.getByRole("button", { name: "Retry with wider window" })

    expect(callout).toHaveClass("border-[hsl(var(--destructive)/0.28)]")
    expect(callout).toHaveClass("bg-[hsl(var(--destructive-surface))]")
    expect(retryButton).toHaveClass("bg-gradient-ai")
  })

  it("filters empty content and keeps generic actions adaptive instead of forcing full-width slots", () => {
    render(<AgUiLayoutTreeRenderer activity={convergenceActivity} stateSnapshot={stateSnapshot} showMeta={false} />)

    const card = screen
      .getByText("Restore directly on production host with an unusually long fallback plan title")
      .closest("section")
    const primaryAction = screen.getByRole("button", {
      name: "Choose Restore directly on production host with a very long operation label that should wrap cleanly inside the card",
    })
    const secondaryAction = screen.getByRole("button", {
      name: "Open details for Restore directly on production host with a very long operation label that should wrap cleanly inside the card",
    })

    expect(card).toHaveClass("h-full")
    expect(primaryAction).toHaveClass("h-auto")
    expect(primaryAction).toHaveClass("max-w-full")
    expect(primaryAction).toHaveClass("!whitespace-normal")
    expect(primaryAction).toHaveClass("[overflow-wrap:anywhere]")
    expect(primaryAction).not.toHaveClass("!w-full")
    expect(secondaryAction).toHaveClass("max-w-full")
    expect(secondaryAction).not.toHaveClass("!w-full")

    expect(screen.getAllByText("Target")).toHaveLength(1)
    expect(screen.getAllByText("Window")).toHaveLength(1)
    expect(screen.getAllByText("high risk")).toHaveLength(1)
  })

  it("styles selectable candidate cards closer to the candidate-options visual baseline", () => {
    render(
      <AgUiLayoutTreeRenderer activity={candidateVisualActivity} stateSnapshot={candidateVisualStateSnapshot} showMeta={false} />,
    )

    const card = screen.getByText("Plan A: Restore by exporting the target table").closest("section")
    const primaryAction = screen.getByRole("button", { name: "Confirm restore plan" })
    const secondaryAction = screen.getByRole("button", {
      name: "Open detailed explanation for the selected restore candidate with validation notes",
    })
    const callout = screen.getByText("Business impact").closest("div")

    expect(card).toHaveClass("overflow-hidden")
    expect(card).toHaveClass("bg-background/80")
    expect(primaryAction).toHaveClass("min-h-9")
    expect(primaryAction).toHaveClass("w-full")
    expect(primaryAction).toHaveClass("text-center")
    expect(primaryAction).toHaveClass("overflow-hidden")
    expect(primaryAction).toHaveAttribute("title", "Confirm restore plan")
    expect(primaryAction).toHaveClass("text-sm")
    expect(secondaryAction).toHaveClass("min-h-9")
    expect(secondaryAction).toHaveClass("w-full")
    expect(secondaryAction).toHaveClass("justify-center")
    expect(secondaryAction).toHaveClass("overflow-hidden")
    expect(secondaryAction).toHaveAttribute(
      "title",
      "Open detailed explanation for the selected restore candidate with validation notes",
    )
    expect(callout).toHaveClass("border-ai/15")
    expect(callout).toHaveClass("bg-ai/5")
  })

  it("selects the candidate card before firing card actions from inside the action row", () => {
    const onAction = vi.fn()

    render(
      <AgUiLayoutTreeRenderer
        activity={candidateVisualActivity}
        stateSnapshot={candidateVisualUnselectedStateSnapshot}
        showMeta={false}
        onAction={onAction}
      />,
    )

    const card = screen.getByText("Plan A: Restore by exporting the target table").closest("section")
    const secondaryAction = screen.getByRole("button", {
      name: "Open detailed explanation for the selected restore candidate with validation notes",
    })

    expect(card).toHaveClass("border-border/70")
    expect(card).not.toHaveClass("border-ai/60")

    fireEvent.click(secondaryAction)

    expect(card).toHaveClass("border-ai/60")
    expect(onAction).toHaveBeenCalledWith(
      expect.objectContaining({
        actionId: "view_candidate_a_detail",
        kind: "open_ref",
      }),
    )
  })

  it("renders clarification free-text actions as editable inputs and submits the edited value", () => {
    const onSubmitMessage = vi.fn()

    render(<AgUiLayoutTreeRenderer activity={clarificationInputActivity} showMeta={false} onSubmitMessage={onSubmitMessage} />)

    const latestButton = screen.getByRole("button", { name: "Use latest safe point" })
    expect(latestButton).toBeInTheDocument()

    expect(screen.queryByRole("button", { name: "Provide specific timestamp" })).not.toBeInTheDocument()

    const input = screen.getByLabelText("Provide specific timestamp")
    const inputGroup = input.closest("[data-clarification-free-text-action]")
    const submitButton = screen.getByRole("button", { name: "Submit" })
    expect(input).toHaveValue("2026-04-24T15:30:00+08:00")
    expect(inputGroup).toHaveClass("h-9")
    expect(inputGroup).toHaveClass("w-fit")
    expect(inputGroup).not.toHaveClass("flex-1")
    expect(latestButton).toHaveClass("h-9")
    expect(input).toHaveClass("h-9")
    expect(submitButton).toHaveClass("h-9")

    fireEvent.change(input, { target: { value: "12:00" } })
    fireEvent.click(submitButton)

    expect(onSubmitMessage).toHaveBeenCalledWith(
      expect.objectContaining({
        type: "clarification_response",
        clarificationId: "recovery_window",
        freeText: "12:00",
      }),
      expect.objectContaining({
        actionId: "submit_specific_timestamp",
      }),
    )
  })

  it("renders markdown nodes as formatted content instead of plain preformatted text", () => {
    render(<AgUiLayoutTreeRenderer activity={markdownActivity} showMeta={false} />)

    expect(screen.getByRole("list")).toBeInTheDocument()
    expect(screen.getByText("mysql3306_U0HYTDM3RENXS4EJ", { selector: "strong" })).toBeInTheDocument()
    expect(screen.queryByText("**mysql3306_U0HYTDM3RENXS4EJ**")).not.toBeInTheDocument()
  })
})
