import { Plus } from "lucide-react"
import { Button } from "@/components/ui/button"
import { useI18n } from "@/i18n"

interface UserManagementHeaderProps {
  totalUsers: number
  enabledUsers: number
  onCreate: () => void
}

export function UserManagementHeader({ totalUsers, enabledUsers, onCreate }: UserManagementHeaderProps) {
  const { t } = useI18n()

  return (
    <header
      data-user-management-header
      className="rounded-2xl border border-border/70 bg-card/95 px-5 py-5 shadow-card"
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-2xl">
          <h1 className="text-[28px] font-semibold tracking-tight text-foreground">{t("usersPage.title")}</h1>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{t("usersPage.subtitle")}</p>
        </div>

        <div className="flex items-center gap-2 lg:pt-1">
          <div className="hidden rounded-full border border-border/70 bg-background px-3 py-1 text-[11px] font-medium text-muted-foreground sm:inline-flex">
            {t("usersPage.enabledCount")
              .replace("{enabled}", String(enabledUsers))
              .replace("{total}", String(totalUsers))}
          </div>
          <Button
            data-user-management-create
            type="button"
            size="sm"
            className="gap-2 rounded-md"
            onClick={onCreate}
          >
            <Plus className="h-3.5 w-3.5" />
            {t("usersPage.createUser")}
          </Button>
        </div>
      </div>
    </header>
  )
}
