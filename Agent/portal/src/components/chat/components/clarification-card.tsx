import { useEffect, useMemo, useState } from "react"
import { Check, CheckCircle2, CircleHelp } from "lucide-react"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/cn"
import type { ConversationClarificationRichPayload } from "@/types/conversation"

interface ClarificationCardProps {
  payload: ConversationClarificationRichPayload
  submitting: boolean
  onSubmit: (input: {
    clarificationId?: string
    selectedValue?: string
    freeText?: string
  }) => void
}

export function ClarificationCard({ payload, submitting, onSubmit }: ClarificationCardProps) {
  const [selectedValue, setSelectedValue] = useState<string | undefined>(payload.selectedValue)
  const [freeTextValue, setFreeTextValue] = useState(payload.freeTextValue ?? "")
  const [optimisticLocked, setOptimisticLocked] = useState(payload.responseLocked === true)

  useEffect(() => {
    setSelectedValue(payload.selectedValue)
    setFreeTextValue(payload.freeTextValue ?? "")
    setOptimisticLocked(payload.responseLocked === true)
  }, [payload.freeTextValue, payload.responseLocked, payload.selectedValue, payload.prompt])

  const isLocked = optimisticLocked || payload.responseLocked === true
  const allowFreeText = payload.inputConstraints?.allowFreeText === true
  const isRequired = payload.inputConstraints?.required === true
  const trimmedFreeText = freeTextValue.trim()
  const hasResponse = Boolean(selectedValue || trimmedFreeText)
  const submitDisabled = submitting || isLocked || (isRequired && !hasResponse)
  const submitLabel = isLocked ? "Submitted" : "Submit confirmation"

  const selectedOptionLabel = useMemo(
    () => payload.options.find((option) => option.value === selectedValue)?.label,
    [payload.options, selectedValue],
  )

  return (
    <section className="rounded-2xl border border-border/70 bg-card p-3 shadow-card sm:p-4">
      <header className="space-y-1.5">
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-ai/80">Clarification</p>
        <div className="flex flex-wrap items-center gap-2">
          <h3 className="text-sm font-semibold leading-6 text-foreground sm:text-[15px]">{payload.prompt}</h3>
          {isLocked ? (
            <span className="rounded-full bg-muted px-2 py-0.5 text-[10px] font-medium text-muted-foreground">
              Submitted
            </span>
          ) : null}
        </div>
      </header>

      <div className="mt-3 space-y-3">
        <div className="flex flex-wrap gap-2">
          {payload.options.map((option) => {
            const isActiveOption = option.value === selectedValue

            return (
              <button
                key={option.value}
                type="button"
                disabled={submitting || isLocked}
                aria-pressed={isActiveOption}
                className={cn(
                  "inline-flex items-center gap-2 rounded-xl border px-3 py-2 text-sm font-medium transition-all duration-200",
                  isActiveOption
                    ? "border-ai/60 bg-ai/8 text-foreground ring-1 ring-ai/20"
                    : "border-border/70 bg-background/80 text-muted-foreground hover:border-ai/25 hover:text-foreground",
                  "disabled:cursor-not-allowed disabled:opacity-70",
                )}
                onClick={() => setSelectedValue(option.value)}
              >
                {isActiveOption ? <CheckCircle2 className="h-4 w-4 text-ai" aria-hidden="true" /> : <CircleHelp className="h-4 w-4" aria-hidden="true" />}
                {option.label}
              </button>
            )
          })}
        </div>

        {allowFreeText ? (
          <label className="block space-y-1.5">
            <span className="text-xs font-medium text-muted-foreground">
              {payload.inputConstraints?.freeTextLabel ?? "Additional input"}
            </span>
            <input
              aria-label={payload.inputConstraints?.freeTextLabel ?? "Additional input"}
              type="text"
              value={freeTextValue}
              disabled={submitting || isLocked}
              onChange={(event) => setFreeTextValue(event.target.value)}
              placeholder={payload.inputConstraints?.freeTextPlaceholder ?? "Type your answer"}
              className="w-full rounded-xl border border-border bg-background/90 px-3 py-2.5 text-sm text-foreground outline-none transition-all duration-200 placeholder:text-muted-foreground/70 focus:border-ai/40 focus:ring-2 focus:ring-ai/15 disabled:cursor-not-allowed disabled:opacity-70"
            />
          </label>
        ) : null}

        {isLocked && (selectedOptionLabel || trimmedFreeText) ? (
          <div className="rounded-xl border border-ai/15 bg-ai/5 px-3 py-2.5 text-xs leading-5 text-muted-foreground">
            {selectedOptionLabel ? <p>Selected: {selectedOptionLabel}</p> : null}
            {trimmedFreeText ? <p className="mt-1 break-words">Input: {trimmedFreeText}</p> : null}
          </div>
        ) : null}

        <div className="flex justify-end">
          <Button
            type="button"
            variant={isLocked ? "secondary" : "ai"}
            className="h-9 gap-2 text-sm"
            disabled={submitDisabled}
            onClick={() => {
              setOptimisticLocked(true)
              onSubmit({
                ...(payload.clarificationId ? { clarificationId: payload.clarificationId } : {}),
                ...(selectedValue ? { selectedValue } : {}),
                ...(trimmedFreeText ? { freeText: trimmedFreeText } : {}),
              })
            }}
          >
            <Check className="h-4 w-4" aria-hidden="true" />
            {submitLabel}
          </Button>
        </div>
      </div>
    </section>
  )
}
