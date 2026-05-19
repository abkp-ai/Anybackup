import { ShieldAlert, ShieldCheck, Users } from "lucide-react"
import { useI18n } from "@/i18n"

interface UserManagementStatsProps {
  totalUsers: number
  enabledUsers: number
  disabledUsers: number
}

export function UserManagementStats({ totalUsers, enabledUsers, disabledUsers }: UserManagementStatsProps) {
  const { t } = useI18n()

  const cards = [
    { label: t("usersPage.statsTotal"), value: totalUsers, icon: Users, tone: "bg-ai-surface text-ai" },
    { label: t("usersPage.statsEnabled"), value: enabledUsers, icon: ShieldCheck, tone: "bg-success-surface text-success" },
    { label: t("usersPage.statsDisabled"), value: disabledUsers, icon: ShieldAlert, tone: "bg-secondary text-foreground" },
  ] as const

  return (
    <section data-user-management-stats className="grid gap-3 md:grid-cols-3" aria-label="User statistics">
      {cards.map((card) => {
        const Icon = card.icon

        return (
          <article key={card.label} className="rounded-2xl border border-border/70 bg-card/95 p-4 shadow-[var(--shadow-xs)]">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-medium uppercase tracking-[0.12em] text-muted-foreground">{card.label}</p>
                <p className="mt-2 text-2xl font-semibold tracking-tight text-foreground">{card.value}</p>
              </div>
              <div className={`flex h-10 w-10 items-center justify-center rounded-lg ${card.tone}`}>
                <Icon className="h-4.5 w-4.5" />
              </div>
            </div>
          </article>
        )
      })}
    </section>
  )
}
