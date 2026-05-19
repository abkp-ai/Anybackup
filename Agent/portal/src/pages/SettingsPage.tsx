import { SettingsOverviewHeader } from "@/components/settings/settings-overview-header"
import { useI18n } from "@/i18n"
import { useAuthStore } from "@/store/useAuthStore"

export function SettingsPage() {
  const { locale, t } = useI18n()
  const currentUser = useAuthStore((state) => state.currentUser)
  const localeLabel = locale === "zh-CN" ? t("settings.languageChinese") : t("settings.languageEnglish")

  return (
    <div data-settings-page className="h-full min-h-0 flex-1 overflow-auto p-6">
      <div className="mx-auto max-w-4xl">
        <SettingsOverviewHeader currentUser={currentUser} localeLabel={localeLabel} />
      </div>
    </div>
  )
}
