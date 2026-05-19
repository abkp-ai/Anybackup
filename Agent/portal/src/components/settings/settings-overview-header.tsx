import { Languages, UserRound } from "lucide-react"
import { useI18n } from "@/i18n"
import type { CurrentUser } from "@/types/auth"

interface SettingsOverviewHeaderProps {
  currentUser: CurrentUser | null
  localeLabel: string
}

export function SettingsOverviewHeader({ currentUser, localeLabel }: SettingsOverviewHeaderProps) {
  const { t } = useI18n()

  return (
    <header className="rounded-2xl border border-border/70 bg-card/95 p-6 shadow-card">
      <div className="flex flex-col gap-5">
        <div className="max-w-2xl">
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">{t("settings.title")}</h1>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{t("settings.description")}</p>
        </div>

        <div data-settings-context-strip className="flex flex-wrap gap-3 border-t border-border/60 pt-4">
          <div
            data-settings-account-summary
            className="inline-flex min-h-[52px] min-w-[220px] items-center gap-3 rounded-xl border border-border/70 bg-background/70 px-4 py-3"
          >
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-ai-surface text-ai">
              <UserRound className="h-4.5 w-4.5" />
            </div>
            <div className="min-w-0">
              <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
                {t("settings.accountSummaryTitle")}
              </p>
              <p className="mt-1 truncate text-sm font-semibold text-foreground">
                {currentUser?.displayName ?? currentUser?.username ?? "--"}
              </p>
              <p className="mt-0.5 truncate text-xs text-muted-foreground">
                {currentUser?.username ?? "--"} · {t("settings.accountSummaryRole")}: {currentUser?.role ?? "--"}
              </p>
            </div>
          </div>

          <div className="inline-flex min-h-[52px] min-w-[180px] items-center gap-3 rounded-xl border border-border/70 bg-background/70 px-4 py-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-secondary text-foreground">
              <Languages className="h-4.5 w-4.5" />
            </div>
            <div className="min-w-0">
              <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
                {t("settings.currentLanguageLabel")}
              </p>
              <p className="mt-1 text-sm font-semibold text-foreground">{localeLabel}</p>
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}
