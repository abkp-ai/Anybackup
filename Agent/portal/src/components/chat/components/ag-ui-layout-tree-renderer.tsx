import { useEffect, useMemo, useState } from "react"
import { Check, CheckCircle2, Circle, Copy, ExternalLink, Link2, Sparkles } from "lucide-react"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { Button } from "@/components/ui/button"
import { translate } from "@/i18n/messages"
import { cn } from "@/lib/cn"
import type {
  LayoutTreeAction,
  LayoutTreeActionKind as ActionKind,
  LayoutTreeActionStyle as ActionStyle,
  LayoutTreeContent,
  LayoutTreeNode,
  LayoutTreeStateSnapshot,
} from "@/types/conversation"

export type { LayoutTreeAction, LayoutTreeContent, LayoutTreeNode, LayoutTreeStateSnapshot } from "@/types/conversation"

interface AgUiLayoutTreeRendererProps {
  activity: LayoutTreeContent
  stateSnapshot?: LayoutTreeStateSnapshot
  onSubmitMessage?: (payload: Record<string, unknown>, event: LayoutTreeActionEvent) => void
  onAction?: (event: LayoutTreeActionEvent) => void
  showMeta?: boolean
  testId?: string
}

export interface LayoutTreeActionEvent {
  actionId: string
  kind: ActionKind
  label: string
  payload?: Record<string, unknown>
}

interface RenderContext {
  actionsById: Map<string, LayoutTreeAction>
  selectionState: NonNullable<LayoutTreeStateSnapshot["selection"]>
  onSelectCandidate: (candidateId: string) => void
  onAction: (action: LayoutTreeAction) => void
}

function asRecord(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : undefined
}

function asArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? (value as T[]) : []
}

function asString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value.trim() : undefined
}

function asNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined
}

function badgeItemText(item: Record<string, unknown>): string {
  const directText = asString(item.text)
  if (directText) return directText

  const label = asString(item.label)
  const value = asString(item.value)

  if (label && value) return `${label}: ${value}`
  return label ?? value ?? ""
}

function badgeItemTone(item: Record<string, unknown>): string | undefined {
  const directTone = asString(item.tone)
  if (directTone) return directTone

  const value = (asString(item.value) ?? "").toLowerCase()

  if (value.includes("recommended") || value.includes("推荐") || value.includes("low")) return "positive"
  if (value.includes("medium") || value.includes("中") || value.includes("risk")) return "warning"
  if (value.includes("high") || value.includes("高")) return "danger"
  if (value.includes("alternative") || value.includes("备选")) return "info"

  return undefined
}

function buttonVariant(style?: ActionStyle): "ai" | "outline" | "destructive" | "link" {
  switch (style) {
    case "primary":
      return "ai"
    case "danger":
      return "destructive"
    case "link":
      return "link"
    case "secondary":
    default:
      return "outline"
  }
}

function gapClass(gap?: string): string {
  switch (gap) {
    case "xs":
      return "gap-1"
    case "sm":
      return "gap-2"
    case "md":
      return "gap-3"
    case "lg":
      return "gap-4"
    case "xl":
      return "gap-6"
    default:
      return "gap-3"
  }
}

function toneClasses(tone?: string): string {
  switch (tone) {
    case "highlight":
      return "border-border/70 bg-card"
    case "positive":
      return "border-success/40 bg-success/5"
    case "warning":
      return "border-warning/40 bg-warning/5"
    case "danger":
      return "border-destructive/40 bg-destructive/5"
    default:
      return "border-border/70 bg-card"
  }
}

function badgeToneClasses(tone?: string): string {
  switch (tone) {
    case "positive":
      return "bg-success/12 text-success"
    case "warning":
      return "bg-warning/14 text-warning"
    case "danger":
      return "bg-destructive/12 text-destructive"
    case "info":
      return "bg-ai/12 text-ai"
    default:
      return "bg-muted text-muted-foreground"
  }
}

function calloutToneClasses(tone?: string): string {
  switch (tone) {
    case "warning":
      return "border-[hsl(var(--warning)/0.28)] bg-[hsl(var(--warning-surface))]"
    case "error":
    case "danger":
      return "border-[hsl(var(--destructive)/0.28)] bg-[hsl(var(--destructive-surface))]"
    case "success":
      return "border-[hsl(var(--success)/0.28)] bg-[hsl(var(--success-surface))]"
    case "info":
    default:
      return "border-[hsl(var(--ai)/0.28)] bg-[hsl(var(--ai-surface))]"
  }
}

function chartBarToneClasses(tone?: string): string {
  switch (tone) {
    case "warning":
      return "bg-warning"
    case "danger":
      return "bg-destructive"
    case "success":
      return "bg-success"
    case "info":
    default:
      return "bg-ai"
  }
}

function renderMarkdownContent(text: string) {
  return (
    <div className="min-w-0 text-sm leading-6 text-foreground [overflow-wrap:anywhere]">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        skipHtml
        components={{
          p: ({ children }) => (
            <p className="mb-3 min-w-0 whitespace-pre-wrap break-words last:mb-0 [overflow-wrap:anywhere]">
              {children}
            </p>
          ),
          ol: ({ children }) => <ol className="mb-3 list-decimal space-y-1.5 pl-5 last:mb-0">{children}</ol>,
          ul: ({ children }) => <ul className="mb-3 list-disc space-y-1.5 pl-5 last:mb-0">{children}</ul>,
          li: ({ children }) => <li className="min-w-0 break-words [overflow-wrap:anywhere]">{children}</li>,
          strong: ({ children }) => <strong className="font-semibold text-foreground">{children}</strong>,
          em: ({ children }) => <em className="italic text-foreground">{children}</em>,
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noreferrer noopener"
              className="font-medium text-ai underline underline-offset-4"
            >
              {children}
            </a>
          ),
          code: ({ children }) => (
            <code className="rounded-md bg-muted px-1.5 py-0.5 font-mono text-[13px] text-foreground">{children}</code>
          ),
          pre: ({ children }) => (
            <pre className="mb-3 overflow-x-auto rounded-xl border border-border/50 bg-muted/40 p-3 text-[13px] leading-6 last:mb-0">
              {children}
            </pre>
          ),
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  )
}

function collectActionIds(node: LayoutTreeNode): string[] {
  const ownIds = node.type === "action-row" ? asArray<string>(node.props?.actionIds) : []
  const childIds = node.children?.flatMap((child) => collectActionIds(child)) ?? []
  return [...ownIds, ...childIds]
}

function candidateSelectionDetails(payload: Record<string, unknown> | undefined): {
  candidateOptionId?: string
  selection?: "confirm" | "reject" | "revise"
} {
  const candidateOptionId =
    (typeof payload?.candidate_option_id === "string" ? payload.candidate_option_id : undefined) ??
    (typeof payload?.candidateOptionId === "string" ? payload.candidateOptionId : undefined)

  const selection =
    payload?.selection === "confirm" || payload?.selection === "reject" || payload?.selection === "revise"
      ? payload.selection
      : payload?.action === "confirm" || payload?.action === "reject" || payload?.action === "revise"
        ? payload.action
        : undefined

  return { candidateOptionId, selection }
}

function isCandidateSelectionAction(action: LayoutTreeAction | undefined, candidateId?: string): boolean {
  const payload = asRecord(action?.payload)
  const { candidateOptionId, selection } = candidateSelectionDetails(payload)
  return (
    action?.kind === "submit_message" &&
    ((asString(payload?.type) === "candidate_selection" && candidateOptionId === candidateId) ||
      (candidateOptionId === candidateId && Boolean(selection)))
  )
}

function clarificationFreeTextValue(payload: Record<string, unknown> | undefined): string | undefined {
  if (asString(payload?.type) !== "clarification_response") return undefined

  const selectedValue = asString(payload?.selected_value) ?? asString(payload?.selectedValue)
  if (selectedValue) return undefined

  return asString(payload?.free_text) ?? asString(payload?.freeText)
}

function isClarificationFreeTextAction(action: LayoutTreeAction): boolean {
  return action.kind === "submit_message" && Boolean(clarificationFreeTextValue(asRecord(action.payload)))
}

function FreeTextClarificationAction({
  action,
  ctx,
  candidateOwnerId,
}: {
  action: LayoutTreeAction
  ctx: RenderContext
  candidateOwnerId?: string
}) {
  const payload = asRecord(action.payload)
  const initialValue = clarificationFreeTextValue(payload) ?? ""
  const [value, setValue] = useState(initialValue)
  const isDisabled = value.trim().length === 0

  return (
    <div
      data-clarification-free-text-action=""
      className="flex h-9 w-fit min-w-0 max-w-full items-center gap-2"
    >
      <input
        aria-label={action.label}
        title={action.label}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onClick={(event) => event.stopPropagation()}
        className="h-9 w-72 min-w-0 max-w-full rounded-md border border-input bg-background px-3 text-sm text-foreground shadow-inner-soft transition-fast placeholder:text-muted-foreground focus:border-ai focus:outline-none focus:ring-2 focus:ring-ai/15"
      />
      <Button
        type="button"
        variant={buttonVariant(action.style)}
        size="sm"
        disabled={isDisabled}
        title={action.label}
        className="h-9 shrink-0 px-3 text-xs"
        onClick={(event) => {
          event.stopPropagation()
          if (candidateOwnerId && !ctx.selectionState.selectionLocked) {
            ctx.onSelectCandidate(candidateOwnerId)
          }
          ctx.onAction({
            ...action,
            payload: {
              ...(payload ?? {}),
              free_text: value,
              freeText: value,
            },
          })
        }}
      >
        Submit
      </Button>
    </div>
  )
}

function isCandidateSelectionPayload(payload: Record<string, unknown> | undefined): boolean {
  const { candidateOptionId, selection } = candidateSelectionDetails(payload)
  return (
    (asString(payload?.type) === "candidate_selection" && Boolean(candidateOptionId)) ||
    (Boolean(candidateOptionId) && Boolean(selection))
  )
}

function partitionCandidateCardChildren(children: LayoutTreeNode[] | undefined): {
  headerNodes: LayoutTreeNode[]
  bodyNodes: LayoutTreeNode[]
  footerNodes: LayoutTreeNode[]
} {
  const nodes = children ?? []
  const footerNodes = nodes.filter((child) => child.type === "action-row")
  const nonFooterNodes = nodes.filter((child) => child.type !== "action-row")
  const headerNodes: LayoutTreeNode[] = []

  for (const child of nonFooterNodes) {
    if (child.type === "heading" || child.type === "badge-row" || child.type === "paragraph") {
      headerNodes.push(child)
      continue
    }

    break
  }

  return {
    headerNodes,
    bodyNodes: nonFooterNodes.slice(headerNodes.length),
    footerNodes,
  }
}

function renderChildren(children: LayoutTreeNode[] | undefined, ctx: RenderContext, candidateOwnerId?: string) {
  return (
    children?.flatMap((child, index) => {
      const rendered = renderNode(child, ctx, child.id ?? `${child.type}-${index}`, candidateOwnerId)
      return rendered == null ? [] : [rendered]
    }) ?? []
  )
}

function TabsNode({ node, ctx, nodeKey }: { node: LayoutTreeNode; ctx: RenderContext; nodeKey: string }) {
  const items = asArray<Record<string, unknown>>(node.props?.items)
  const children = node.children ?? []
  const resolvedTabs =
    items.length > 0
      ? items.map((item, index) => ({
          id: asString(item.id) ?? children[index]?.id ?? `tab-${index}`,
          label: asString(item.label) ?? `Tab ${index + 1}`,
        }))
      : children.map((child, index) => ({
          id: child.id ?? `tab-${index}`,
          label: asString(child.props?.tabLabel) ?? `Tab ${index + 1}`,
        }))

  const initialTabId = asString(node.props?.defaultTabId) ?? resolvedTabs[0]?.id ?? null
  const [activeTabId, setActiveTabId] = useState<string | null>(initialTabId)

  useEffect(() => {
    setActiveTabId(initialTabId)
  }, [initialTabId, node.id])

  const activeIndex = Math.max(
    0,
    resolvedTabs.findIndex((item) => item.id === activeTabId),
  )
  const activeChild = children[activeIndex] ?? children[0]

  return (
    <div key={nodeKey} className="rounded-2xl border border-border/70 bg-background/80 p-3 shadow-sm">
      <div className="flex flex-wrap gap-2 border-b border-border/60 pb-3">
        {resolvedTabs.map((item) => {
          const isActiveTab = item.id === (resolvedTabs[activeIndex]?.id ?? null)

          return (
            <button
              key={item.id}
              type="button"
              className={cn(
                "rounded-lg px-3 py-1.5 text-sm font-medium transition-all duration-200",
                isActiveTab ? "bg-ai text-primary-foreground shadow-sm" : "bg-muted/70 text-muted-foreground hover:text-foreground",
              )}
              onClick={() => setActiveTabId(item.id)}
            >
              {item.label}
            </button>
          )
        })}
      </div>
      <div className="mt-4">{activeChild ? renderNode(activeChild, ctx, `${nodeKey}-${activeTabId ?? "default"}`) : null}</div>
    </div>
  )
}

function renderNode(node: LayoutTreeNode, ctx: RenderContext, key: string, candidateOwnerId?: string) {
  const props = node.props ?? {}
  const children = node.children
  const isSelected = Boolean(node.id && ctx.selectionState.selectedCandidateOptionId === node.id)
  const isLocked = ctx.selectionState.selectionLocked === true

  switch (node.type) {
    case "stack":
    case "section": {
      const renderedChildren = renderChildren(children, ctx, candidateOwnerId)
      if (renderedChildren.length === 0) return null

      return (
        <div key={key} className={cn("flex min-w-0 flex-col", gapClass(asString(props.gap)))}>
          {renderedChildren}
        </div>
      )
    }

    case "grid": {
      const renderedChildren = renderChildren(children, ctx, candidateOwnerId)
      if (renderedChildren.length === 0) return null

      const columns = Math.max(1, asNumber(props.columns) ?? 1)
      const minWidth = columns >= 3 ? "15rem" : "18rem"
      return (
        <div
          key={key}
          className={cn("grid auto-rows-fr", gapClass(asString(props.gap)))}
          style={{ gridTemplateColumns: `repeat(auto-fit, minmax(min(100%, ${minWidth}), 1fr))` }}
        >
          {renderedChildren}
        </div>
      )
    }

    case "card": {
      const cardCandidateId = node.id
      const cardActionIds = collectActionIds(node)
      const isSelectableCard = Boolean(
        cardCandidateId && cardActionIds.some((actionId) => isCandidateSelectionAction(ctx.actionsById.get(actionId), cardCandidateId)),
      )
      const renderedChildren = renderChildren(children, ctx)
      const title = asString(props.title)
      if (!title && renderedChildren.length === 0) return null

      if (isSelectableCard) {
        const { headerNodes, bodyNodes, footerNodes } = partitionCandidateCardChildren(children)
        const renderedHeaderNodes = renderChildren(headerNodes, ctx, cardCandidateId)
        const renderedBodyNodes = renderChildren(bodyNodes, ctx, cardCandidateId)
        const renderedFooterNodes = renderChildren(footerNodes, ctx, cardCandidateId)

        return (
          <section
            key={key}
            role="button"
            tabIndex={0}
            className={cn(
              "relative flex h-full min-w-0 flex-col overflow-hidden rounded-2xl border bg-background/80 shadow-sm transition-all duration-200 ease-smooth",
              isSelected ? "border-ai/60 shadow-[0_12px_32px_-24px_rgba(10,132,255,0.55)] ring-1 ring-ai/25" : "border-border/70",
              isLocked && !isSelected ? "opacity-70" : "hover:border-ai/25 hover:bg-ai/5",
            )}
            onClick={() => {
              if (!isLocked && cardCandidateId) ctx.onSelectCandidate(cardCandidateId)
            }}
            onKeyDown={(event) => {
              if (isLocked || !cardCandidateId) return
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault()
                ctx.onSelectCandidate(cardCandidateId)
              }
            }}
          >
            <div className="flex h-full min-w-0 flex-col text-left">
              <div className="flex items-start gap-2.5 border-b border-border/60 px-3.5 py-3">
                <div className="pt-0.5 text-ai">
                  {isSelected ? (
                    <CheckCircle2 className="h-[18px] w-[18px]" aria-hidden="true" />
                  ) : (
                    <Circle className="h-[18px] w-[18px] text-muted-foreground/60" aria-hidden="true" />
                  )}
                </div>
                <div className="min-w-0 flex-1 space-y-1">
                  {title ? (
                    <h3 className="min-w-0 text-sm font-semibold leading-5 text-foreground [overflow-wrap:anywhere] sm:text-[15px]">
                      {title}
                    </h3>
                  ) : null}
                  {renderedHeaderNodes}
                </div>
              </div>

              <div className="flex min-w-0 flex-1 flex-col space-y-3 px-3.5 py-3">{renderedBodyNodes}</div>

              {renderedFooterNodes.length > 0 ? (
                <div className="border-t border-border/60 px-3.5 pb-3.5 pt-3">{renderedFooterNodes}</div>
              ) : null}
            </div>
          </section>
        )
      }

      return (
        <section
          key={key}
          role={isSelectableCard ? "button" : undefined}
          tabIndex={isSelectableCard ? 0 : undefined}
          className={cn(
            "relative flex h-full min-w-0 flex-col rounded-2xl border p-4 shadow-sm transition-all duration-200",
            toneClasses(asString(props.tone)),
            isSelected
              ? "border-ai/55 bg-ai/5 shadow-[0_14px_32px_-24px_rgba(10,132,255,0.45)] ring-1 ring-ai/25"
              : undefined,
            isSelectableCard ? "cursor-pointer hover:-translate-y-[1px]" : undefined,
          )}
          onClick={
            isSelectableCard && cardCandidateId
              ? () => {
                  if (!isLocked) ctx.onSelectCandidate(cardCandidateId)
                }
              : undefined
          }
          onKeyDown={
            isSelectableCard && cardCandidateId
              ? (event) => {
                  if (isLocked) return
                  if (event.key === "Enter" || event.key === " ") {
                    event.preventDefault()
                    ctx.onSelectCandidate(cardCandidateId)
                  }
                }
              : undefined
          }
        >
          {isSelected && isLocked ? (
            <span className="absolute right-4 top-4 inline-flex items-center gap-1 rounded-full bg-ai/10 px-2 py-0.5 text-[10px] font-medium text-ai">
              <CheckCircle2 className="h-3.5 w-3.5" />
              {translate("candidate.confirmed")}
            </span>
          ) : null}
          <div className={cn("flex min-w-0 flex-1 flex-col", gapClass(asString(props.gap) ?? "md"))}>
            {title ? (
              <h3 className="min-w-0 text-sm font-semibold leading-6 text-foreground [overflow-wrap:anywhere]">{title}</h3>
            ) : null}
            {renderedChildren}
          </div>
        </section>
      )
    }

    case "heading": {
      const level = Math.min(Math.max(asNumber(props.level) ?? 3, 1), 4)
      const text = asString(props.text) ?? ""
      if (!text) return null
      const className =
        level === 1
          ? "text-xl font-semibold text-foreground"
          : level === 2
            ? "text-lg font-semibold text-foreground"
            : level === 3
            ? "text-sm font-semibold leading-6 text-foreground"
            : "text-sm font-medium text-foreground"

      if (level === 1) {
        return (
          <h1 key={key} className={className}>
            {text}
          </h1>
        )
      }

      if (level === 2) {
        return (
          <h2 key={key} className={className}>
            {text}
          </h2>
        )
      }

      if (level === 3) {
        return (
          <h3 key={key} className={className}>
            {text}
          </h3>
        )
      }

      return (
        <h4 key={key} className={className}>
          {text}
        </h4>
      )
    }

    case "paragraph": {
      const text = asString(props.text)
      if (!text) return null
      return (
        <p key={key} className="min-w-0 whitespace-pre-wrap break-words text-sm leading-6 text-muted-foreground [overflow-wrap:anywhere]">
          {text}
        </p>
      )
    }

    case "markdown": {
      const text = asString(props.text)
      if (!text) return null
      return (
        <div key={key} className="rounded-xl border border-border/60 bg-background/80 px-4 py-3">
          {renderMarkdownContent(text)}
        </div>
      )
    }

    case "badge-row": {
      const items = asArray<Record<string, unknown>>(props.items).filter((item) => Boolean(badgeItemText(item)))
      if (items.length === 0) return null

      return (
        <div key={key} className="flex flex-wrap gap-2">
          {items.map((item, index) => (
            <span
              key={`${key}-badge-${index}`}
              className={cn(
                "min-w-0 rounded-full px-2 py-0.5 text-[10px] font-medium leading-4 [overflow-wrap:anywhere]",
                badgeToneClasses(badgeItemTone(item)),
              )}
            >
              {badgeItemText(item)}
            </span>
          ))}
        </div>
      )
    }

    case "kv-list": {
      const items = asArray<Record<string, unknown>>(props.items).filter(
        (item) => Boolean(asString(item.label) ?? asString(item.value)),
      )
      if (items.length === 0) return null

      return (
        <div key={key} className="grid auto-rows-fr gap-2 sm:grid-cols-2">
          {items.map((item, index) => (
            <div
              key={`${key}-kv-${index}`}
              className="flex h-full min-w-0 flex-col rounded-xl border border-border/50 bg-muted/30 px-3 py-2.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.4)]"
            >
              {asString(item.label) ? (
                <p className="text-[11px] font-medium leading-4 text-muted-foreground">{asString(item.label)}</p>
              ) : null}
              {asString(item.value) ? (
                <p className="mt-1 break-words text-sm font-medium leading-5 text-foreground [overflow-wrap:anywhere]">
                  {asString(item.value)}
                </p>
              ) : null}
            </div>
          ))}
        </div>
      )
    }

    case "metric-list": {
      const items = asArray<Record<string, unknown>>(props.items).filter(
        (item) => Boolean(asString(item.label) ?? asString(item.value)),
      )
      if (items.length === 0) return null

      return (
        <div key={key} className="grid auto-rows-fr gap-2 sm:grid-cols-2">
          {items.map((item, index) => (
            <div
              key={`${key}-metric-${index}`}
              className="flex h-full min-w-0 flex-col rounded-xl border border-border/50 bg-muted/30 px-3 py-2.5 shadow-[inset_0_1px_0_rgba(255,255,255,0.4)]"
            >
              {asString(item.label) ? (
                <p className="text-[11px] font-medium leading-4 text-muted-foreground">
                  {asString(item.label)}
                </p>
              ) : null}
              {asString(item.value) ? (
                <p className="mt-1 text-sm font-medium leading-5 text-foreground [overflow-wrap:anywhere]">
                  {asString(item.value)}
                </p>
              ) : null}
            </div>
          ))}
        </div>
      )
    }

    case "data-table": {
      const columns = asArray<Record<string, unknown>>(props.columns).filter(
        (column) => Boolean(asString(column.label) ?? asString(column.key)),
      )
      const rows = asArray<Record<string, unknown>>(props.rows)
      if (columns.length === 0 || rows.length === 0) return null

      return (
        <div key={key} className="overflow-hidden rounded-xl border border-border/70">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-border text-sm">
              <thead className="bg-muted/35">
                <tr>
                  {columns.map((column, index) => (
                    <th key={`${key}-head-${index}`} className="px-3 py-2 text-left font-medium text-foreground">
                      {asString(column.label) ?? asString(column.key) ?? ""}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-border/60 bg-card">
                {rows.map((row, rowIndex) => (
                  <tr key={`${key}-row-${rowIndex}`}>
                    {columns.map((column, colIndex) => (
                      <td
                        key={`${key}-cell-${rowIndex}-${colIndex}`}
                        className="px-3 py-2 text-muted-foreground [overflow-wrap:anywhere]"
                      >
                        {asString(row[asString(column.key) ?? ""]) ?? ""}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )
    }

    case "attachment-list": {
      const items = asArray<Record<string, unknown>>(props.items).filter((item) =>
        Boolean(asString(item.title) ?? asString(item.text) ?? asString(item.summary)),
      )
      if (items.length === 0) return null

      return (
        <div key={key} className="space-y-2">
          {items.map((item, index) => (
            <div
              key={`${key}-attachment-${index}`}
              className="rounded-xl border border-border/60 bg-background/80 px-3 py-2.5"
            >
              <p className="text-sm font-medium text-foreground [overflow-wrap:anywhere]">
                {asString(item.title) ?? asString(item.text) ?? ""}
              </p>
              {asString(item.summary) ? (
                <p className="mt-1 text-xs leading-5 text-muted-foreground [overflow-wrap:anywhere]">
                  {asString(item.summary)}
                </p>
              ) : null}
            </div>
          ))}
        </div>
      )
    }

    case "callout": {
      const title = asString(props.title)
      const text = asString(props.text)
      if (!title && !text) return null

      if (asString(props.tone) === "info") {
        return (
          <div key={key} className="rounded-xl border border-ai/15 bg-ai/5 px-3 py-2.5">
            {title ? <p className="text-[10px] font-semibold uppercase tracking-[0.1em] text-ai">{title}</p> : null}
            {text ? (
              <div className={cn("flex items-start gap-2", title ? "mt-1" : undefined)}>
                <Sparkles className="mt-0.5 h-4 w-4 shrink-0 text-ai" aria-hidden="true" />
                <p className="break-words text-xs leading-5 text-muted-foreground [overflow-wrap:anywhere]">{text}</p>
              </div>
            ) : null}
          </div>
        )
      }

      return (
        <div key={key} className={cn("rounded-xl border px-3 py-3", calloutToneClasses(asString(props.tone)))}>
          {title ? (
            <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-foreground">{title}</p>
          ) : null}
          {text ? (
            <p className={cn("break-words text-sm leading-6 text-muted-foreground [overflow-wrap:anywhere]", title ? "mt-1" : undefined)}>
              {text}
            </p>
          ) : null}
        </div>
      )
    }

    case "divider":
      return <div key={key} className="h-px bg-border/70" />

    case "chart":
      const chartItems = asArray<Record<string, unknown>>(props.items)
      if (chartItems.length === 0) return null
      const maxValue = Math.max(1, ...chartItems.map((item) => asNumber(item.value) ?? 0))

      return (
        <div key={key} className="rounded-xl border border-border/70 bg-background/80 px-4 py-4">
          {asString(props.title) ? <p className="text-sm font-semibold text-foreground">{asString(props.title)}</p> : null}
          <div className={cn("mt-3 flex flex-col", gapClass("sm"))}>
            {chartItems.length > 0 ? (
              chartItems.map((item, index) => {
                const value = asNumber(item.value) ?? 0
                const width = `${Math.max(8, Math.round((value / maxValue) * 100))}%`

                return (
                  <div key={`${key}-chart-${index}`} className="space-y-1.5">
                    <div className="flex items-center justify-between gap-3 text-xs text-muted-foreground">
                      <span>{asString(item.label) ?? `Series ${index + 1}`}</span>
                      <span className="font-medium text-foreground">{value}</span>
                    </div>
                    <div className="h-2 rounded-full bg-muted/60">
                      <div
                        className={cn("h-2 rounded-full", chartBarToneClasses(asString(item.tone)))}
                        style={{ width }}
                      />
                    </div>
                  </div>
                )
              })
            ) : null}
          </div>
        </div>
      )

    case "tabs":
      return (node.children?.length ?? 0) > 0 ? <TabsNode key={key} node={node} ctx={ctx} nodeKey={key} /> : null

    case "action-row": {
      const actionIds = asArray<string>(props.actionIds)
      const actions = actionIds.map((actionId) => ctx.actionsById.get(actionId)).filter(Boolean) as LayoutTreeAction[]
      if (actions.length === 0) return null
      const hasCandidateSubmitAction = actions.some((action) => isCandidateSelectionPayload(asRecord(action.payload)))

      return (
        <div key={key} className="mt-auto flex flex-wrap items-start gap-2 pt-1">
          {actions.map((action) => {
            if (isClarificationFreeTextAction(action)) {
              return <FreeTextClarificationAction key={action.id} action={action} ctx={ctx} candidateOwnerId={candidateOwnerId} />
            }

            const payload = asRecord(action.payload)
            const payloadType = asString(payload?.type)
            const isClarificationSubmit = payloadType === "clarification_response"
            const { candidateOptionId: candidateId } = candidateSelectionDetails(payload)
            const isCandidateSubmit =
              (payloadType === "candidate_selection" && Boolean(candidateId)) ||
              (Boolean(candidateId) && isCandidateSelectionPayload(payload))
            const isSelectedAction = Boolean(candidateId && candidateId === ctx.selectionState.selectedCandidateOptionId)
            const isSelectedCandidatePrimary = isCandidateSubmit && isSelectedAction
            const isDisabled = isCandidateSubmit && ctx.selectionState.selectionLocked === true
            const baseVariant =
              action.kind === "open_ref" || action.kind === "open_url"
                ? "outline"
                : isCandidateSubmit
                  ? isSelectedAction
                    ? "ai"
                    : "outline"
                  : buttonVariant(action.style)
            const actionIcon =
              action.kind === "open_ref" ? (
                <Link2 className="h-3.5 w-3.5 shrink-0" />
              ) : action.kind === "copy_text" ? (
                <Copy className="h-3.5 w-3.5 shrink-0" />
              ) : action.kind === "open_url" ? (
                <ExternalLink className="h-3.5 w-3.5 shrink-0" />
              ) : isSelectedAction && ctx.selectionState.selectionLocked ? (
                <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
              ) : isSelectedAction ? (
                <Check className="h-4 w-4 shrink-0" />
              ) : null
            return (
              <Button
                key={action.id}
                type="button"
                variant={baseVariant}
                size={
                  (hasCandidateSubmitAction && action.kind === "submit_message") || isClarificationSubmit
                    ? "default"
                    : "sm"
                }
                disabled={isDisabled}
                title={hasCandidateSubmitAction || isClarificationSubmit ? action.label : undefined}
                className={cn(
                  hasCandidateSubmitAction
                    ? cn(
                        "min-w-0 w-full basis-full justify-center overflow-hidden text-center text-sm",
                        isSelectedCandidatePrimary ? "min-h-9" : "min-h-9 h-auto leading-5",
                      )
                    : isClarificationSubmit
                      ? "h-9 min-w-0 w-fit max-w-full justify-center truncate text-center text-sm"
                    : "min-w-0 h-auto w-fit max-w-full self-start gap-2 justify-center text-center !whitespace-normal px-3 py-2 leading-5 [overflow-wrap:anywhere]",
                )}
                onClick={(event) => {
                  event.stopPropagation()
                  if (candidateOwnerId && !ctx.selectionState.selectionLocked) {
                    ctx.onSelectCandidate(candidateOwnerId)
                  }
                  ctx.onAction(action)
                }}
              >
                {hasCandidateSubmitAction ? (
                  <span className="mx-auto inline-flex min-w-0 max-w-full items-center justify-center gap-2">
                    {actionIcon}
                    <span className="min-w-0 overflow-hidden text-ellipsis whitespace-nowrap">{action.label}</span>
                  </span>
                ) : null}
                {!hasCandidateSubmitAction ? (
                  <>
                    {actionIcon}
                    {action.label}
                  </>
                ) : null}
              </Button>
            )
          })}
        </div>
      )
    }

    default:
      return (
        <div key={key} className="rounded-xl border border-dashed border-border bg-muted/20 px-4 py-3 text-sm text-muted-foreground">
          Unsupported node: {node.type}
        </div>
      )
  }
}

export function AgUiLayoutTreeRenderer({
  activity,
  stateSnapshot,
  onSubmitMessage,
  onAction,
  showMeta = true,
  testId = "ag-ui-layout-tree-renderer",
}: AgUiLayoutTreeRendererProps) {
  const initialSelection = stateSnapshot?.selection?.selectedCandidateOptionId ?? null
  const initialLocked = stateSnapshot?.selection?.selectionLocked === true
  const [selectionState, setSelectionState] = useState({
    required: stateSnapshot?.selection?.required ?? false,
    selectedCandidateOptionId: initialSelection,
    selectionLocked: initialLocked,
  })

  useEffect(() => {
    setSelectionState({
      required: stateSnapshot?.selection?.required ?? false,
      selectedCandidateOptionId: stateSnapshot?.selection?.selectedCandidateOptionId ?? null,
      selectionLocked: stateSnapshot?.selection?.selectionLocked === true,
    })
  }, [
    activity.blockId,
    stateSnapshot?.selection?.required,
    stateSnapshot?.selection?.selectedCandidateOptionId,
    stateSnapshot?.selection?.selectionLocked,
  ])

  const actionsById = useMemo(
    () => new Map((activity.actions ?? []).map((action) => [action.id, action])),
    [activity.actions],
  )

  const context = useMemo<RenderContext>(
    () => ({
      actionsById,
      selectionState,
      onSelectCandidate: (candidateId) => {
        setSelectionState((current) => ({
          ...current,
          selectedCandidateOptionId: candidateId,
        }))
      },
      onAction: (action) => {
        if (action.confirmText && typeof window !== "undefined" && !window.confirm(action.confirmText)) {
          return
        }

        const payload = asRecord(action.payload)
        const actionEvent: LayoutTreeActionEvent = {
          actionId: action.id,
          kind: action.kind,
          label: action.label,
          ...(payload ? { payload } : {}),
        }

        if (action.kind === "submit_message") {
          onAction?.(actionEvent)

          if (!payload) return

          const payloadType = asString(payload.type)
          const candidateId = asString(payload.candidate_option_id)

          if (payloadType === "candidate_selection" && candidateId) {
            setSelectionState((current) => ({
              ...current,
              selectedCandidateOptionId: candidateId,
              selectionLocked: true,
            }))
          }

          onSubmitMessage?.(payload, actionEvent)
          return
        }

        if (action.kind === "copy_text") {
          const text = asString(asRecord(action.payload)?.text)
          onAction?.(actionEvent)
          if (text && typeof navigator !== "undefined" && navigator.clipboard) {
            void navigator.clipboard.writeText(text)
          }
          return
        }

        if (action.kind === "open_ref") {
          onAction?.(actionEvent)
          return
        }

        if (action.kind === "open_url") {
          const url = asString(payload?.url)
          onAction?.(actionEvent)
          if (url && typeof window !== "undefined") {
            window.open(url, "_blank", "noopener,noreferrer")
          }
        }
      },
    }),
    [actionsById, onAction, onSubmitMessage, selectionState],
  )

  const renderedRoot = renderNode(activity.ui, context, activity.blockId)

  if (!renderedRoot) {
    return null
  }

  return (
    <section
      data-testid={testId}
      data-layout-tree-block-id={activity.blockId}
      className="rounded-2xl border border-border/70 bg-card p-4 shadow-card sm:p-5"
    >
      {showMeta ? (
        <div className="mb-4 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
          <span className="rounded-full bg-ai/10 px-2 py-0.5 font-medium text-ai">{activity.contract}</span>
          {activity.meta?.intent ? (
            <span className="rounded-full bg-muted px-2 py-0.5 font-medium">intent: {activity.meta.intent}</span>
          ) : null}
          {stateSnapshot?.interaction?.status ? (
            <span className="rounded-full bg-muted px-2 py-0.5 font-medium">
              status: {stateSnapshot.interaction.status}
            </span>
          ) : null}
        </div>
      ) : null}
      {renderedRoot}
    </section>
  )
}
