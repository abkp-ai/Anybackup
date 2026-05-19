import type { LucideIcon } from "lucide-react"
import { ArrowRight, Clock3 } from "lucide-react"
import { Link } from "react-router-dom"
import { cn } from "@/lib/cn"

interface SettingsModuleCardProps {
  moduleId: string
  icon: LucideIcon
  title: string
  description: string
  status: string
  badge?: string
  to?: string
  actionLabel?: string
}

export function SettingsModuleCard({
  moduleId,
  icon: Icon,
  title,
  description,
  status,
  badge,
  to,
  actionLabel,
}: SettingsModuleCardProps) {
  const content = (
    <div className="flex h-full flex-col gap-4 rounded-2xl border border-border/70 bg-card/95 p-5 shadow-card transition-smooth hover:-translate-y-0.5 hover:shadow-card-hover">
      <div className="flex items-start justify-between gap-3">
        <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-ai-surface text-ai">
          <Icon className="h-5 w-5" />
        </div>
        {badge ? (
          <span className="inline-flex items-center rounded-full border border-border/70 bg-background px-2.5 py-1 text-[11px] font-medium text-muted-foreground">
            {badge}
          </span>
        ) : null}
      </div>

      <div className="space-y-2">
        <h2 className="text-base font-semibold text-foreground">{title}</h2>
        <p className="text-sm leading-6 text-muted-foreground">{description}</p>
      </div>

      <div className="mt-auto flex items-center justify-between gap-3 rounded-xl border border-border/60 bg-background/70 px-3.5 py-3 text-sm">
        <span className="text-muted-foreground">{status}</span>
        {to ? (
          <ArrowRight className="h-4 w-4 text-foreground" />
        ) : (
          <Clock3 className="h-4 w-4 text-muted-foreground" />
        )}
      </div>
    </div>
  )

  if (!to) {
    return (
      <div aria-disabled="true" className="h-full" data-settings-module-card={moduleId}>
        {content}
      </div>
    )
  }

  return (
    <Link
      to={to}
      aria-label={actionLabel ?? title}
      className={cn("block h-full")}
      data-discover="true"
      data-settings-module-card={moduleId}
    >
      {content}
    </Link>
  )
}
