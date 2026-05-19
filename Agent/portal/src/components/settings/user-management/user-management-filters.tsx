import type { ChangeEvent } from "react"
import type { UserStatusFilter } from "@/store/useUserManagementStore"
import { useI18n } from "@/i18n"

interface UserManagementFiltersProps {
  searchQuery: string
  statusFilter: UserStatusFilter
  onSearchQueryChange: (value: string) => void
  onStatusFilterChange: (value: UserStatusFilter) => void
  resultCountLabel: string
}

export function UserManagementFilters({
  searchQuery,
  statusFilter,
  onSearchQueryChange,
  onStatusFilterChange,
  resultCountLabel,
}: UserManagementFiltersProps) {
  const { t } = useI18n()

  const handleStatusChange = (event: ChangeEvent<HTMLSelectElement>) => {
    onStatusFilterChange(event.target.value as UserStatusFilter)
  }

  return (
    <section
      data-user-management-filters
      className="grid gap-4 rounded-2xl border border-border/70 bg-card/95 p-5 shadow-card lg:grid-cols-[minmax(0,1fr)_220px_auto]"
    >
      <div className="space-y-1.5">
        <label className="block text-xs font-medium text-foreground" htmlFor="user-search">
          {t("usersPage.searchLabel")}
        </label>
        <input
          id="user-search"
          data-user-management-search
          type="search"
          value={searchQuery}
          onChange={(event) => onSearchQueryChange(event.target.value)}
          placeholder={t("usersPage.searchPlaceholder")}
          className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground transition-fast focus:border-ai/40 focus:outline-none focus:ring-2 focus:ring-ai/30"
        />
      </div>

      <div className="space-y-1.5">
        <label className="block text-xs font-medium text-foreground" htmlFor="user-status-filter">
          {t("usersPage.statusLabel")}
        </label>
        <select
          id="user-status-filter"
          data-user-management-status-filter
          value={statusFilter}
          onChange={handleStatusChange}
          className="h-10 w-full rounded-md border border-input bg-background px-3 text-sm text-foreground transition-fast focus:border-ai/40 focus:outline-none focus:ring-2 focus:ring-ai/30"
        >
          <option value="all">{t("usersPage.statusAll")}</option>
          <option value="enabled">{t("usersPage.statusEnabled")}</option>
          <option value="disabled">{t("usersPage.statusDisabled")}</option>
        </select>
      </div>

      <div className="flex items-end">
        <div className="inline-flex h-10 items-center rounded-full border border-border/70 bg-background px-3.5 text-xs font-medium text-muted-foreground">
          {resultCountLabel}
        </div>
      </div>
    </section>
  )
}
