import { Pencil, Plus, RotateCcw, UserRoundCheck, UserRoundX } from "lucide-react"
import { Button } from "@/components/ui/button"
import { UserStatusBadge } from "@/components/settings/user-management/user-status-badge"
import { useI18n } from "@/i18n"
import type { ManagedUser } from "@/types/user-management"

interface UserManagementTableProps {
  users: ManagedUser[]
  loading: boolean
  emptyStateLabel: string
  currentUserId?: string
  onCreate: () => void
  onEdit: (userId: string) => void
  onDisable: (userId: string) => void
  onEnable: (userId: string) => void
  onResetPassword: (userId: string) => void
}

function formatLastLogin(value: string | undefined, fallback: string): string {
  if (!value) return fallback

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return fallback

  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date)
}

export function UserManagementTable({
  users,
  loading,
  emptyStateLabel,
  currentUserId,
  onCreate,
  onEdit,
  onDisable,
  onEnable,
  onResetPassword,
}: UserManagementTableProps) {
  const { t } = useI18n()

  return (
    <section
      data-user-management-table-card
      className="overflow-hidden rounded-2xl border border-border/80 bg-card/95 shadow-card"
    >
      <header className="flex flex-col gap-3 border-b border-border/70 bg-gradient-to-r from-ai-surface/80 via-white to-white px-4 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-sm font-semibold text-foreground">{t("usersPage.listTitle")}</h2>
          <p className="mt-1 text-xs text-muted-foreground">{t("usersPage.listHint")}</p>
        </div>
        <div className="flex items-center gap-2">
          <div className="inline-flex w-fit rounded-full border border-border/70 bg-white/85 px-3 py-1 text-[11px] font-medium text-muted-foreground">
            {t("usersPage.userCount").replace("{count}", String(users.length))}
          </div>
          <Button
            type="button"
            size="sm"
            className="gap-2 rounded-md"
            onClick={onCreate}
            data-user-management-create
          >
            <Plus className="h-3.5 w-3.5" />
            {t("usersPage.createUser")}
          </Button>
        </div>
      </header>

      <div className="overflow-x-auto">
        {loading ? (
          <div className="px-4 py-12 text-center text-sm text-muted-foreground">{t("usersPage.loading")}</div>
        ) : users.length === 0 ? (
          <div className="px-4 py-12 text-center text-sm text-muted-foreground">{emptyStateLabel}</div>
        ) : (
          <table data-user-management-table className="min-w-[960px] w-full text-left" role="table">
            <thead className="bg-muted/30 text-[11px] font-medium text-muted-foreground">
              <tr>
                <th className="px-4 py-3">{t("usersPage.colUsername")}</th>
                <th className="px-4 py-3">{t("usersPage.colDisplayName")}</th>
                <th className="px-4 py-3">{t("usersPage.colRole")}</th>
                <th className="px-4 py-3">{t("usersPage.colStatus")}</th>
                <th className="px-4 py-3">{t("usersPage.colLastLogin")}</th>
                <th className="px-4 py-3 text-right">{t("usersPage.colActions")}</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => {
                const isCurrentUser = user.id === currentUserId
                const lastLogin = formatLastLogin(user.lastLoginAt, t("usersPage.neverSignedIn"))

                return (
                  <tr key={user.id} className="border-t border-border/70 align-top transition-colors hover:bg-muted/15">
                    <td className="px-4 py-3">
                      <span className="block text-sm font-medium text-foreground">{user.username}</span>
                      {isCurrentUser ? (
                        <span className="mt-1 inline-flex rounded-full border border-ai/15 bg-ai-surface px-2 py-0.5 text-[10px] font-medium text-ai">
                          {t("usersPage.currentAccount")}
                        </span>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 text-sm text-foreground">{user.displayName}</td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">{t("sidebar.backupAdmin")}</td>
                    <td className="px-4 py-3">
                      <UserStatusBadge status={user.status} />
                    </td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">{lastLogin}</td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap justify-end gap-2">
                        <Button
                          type="button"
                          variant="ghost"
                          size="xs"
                          className="gap-1.5 rounded-sm"
                          onClick={() => onEdit(user.id)}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                          {t("usersPage.edit")}
                        </Button>
                        {user.status === "enabled" ? (
                          <Button
                            type="button"
                            variant="ghost"
                            size="xs"
                            className="gap-1.5 rounded-sm text-destructive hover:text-destructive"
                            aria-label={`${t("usersPage.disable")} ${user.username}`}
                            onClick={() => onDisable(user.id)}
                          >
                            <UserRoundX className="h-3.5 w-3.5" />
                            {t("usersPage.disable")}
                          </Button>
                        ) : (
                          <Button
                            type="button"
                            variant="ghost"
                            size="xs"
                            className="gap-1.5 rounded-sm"
                            onClick={() => onEnable(user.id)}
                          >
                            <UserRoundCheck className="h-3.5 w-3.5" />
                            {t("usersPage.enable")}
                          </Button>
                        )}
                        <Button
                          type="button"
                          variant="ghost"
                          size="xs"
                          className="gap-1.5 rounded-sm"
                          onClick={() => onResetPassword(user.id)}
                        >
                          <RotateCcw className="h-3.5 w-3.5" />
                          {t("usersPage.resetPassword")}
                        </Button>
                      </div>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>
    </section>
  )
}
