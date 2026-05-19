import { NavLink, useNavigate } from "react-router-dom"
import { ChevronLeft, ChevronRight, Layers, Settings, Users } from "lucide-react"
import { routes } from "@/config/routes"
import { cn } from "@/lib/cn"
import { useAuthStore } from "@/store/useAuthStore"
import { useI18n } from "@/i18n"
import { useLayoutStore } from "@/store/useLayoutStore"
import { SidebarAccountMenu } from "@/components/navigation/sidebar-account-menu"

interface NavItem {
  to: string
  label: string
  icon: typeof Layers
  end?: boolean
}

export function AppSidebar() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const sidebarCollapsed = useLayoutStore((s) => s.sidebarCollapsed)
  const toggleSidebar = useLayoutStore((s) => s.toggleSidebar)
  const currentUser = useAuthStore((s) => s.currentUser)
  const logout = useAuthStore((s) => s.logout)
  const displayName = currentUser?.displayName ?? t("sidebar.demoUser")
  const accountName = currentUser?.username ?? "Melon.zhao@aishu.cn"
  const roleLabel = t("sidebar.systemAdmin")

  const navItems: NavItem[] = [{ to: routes.home, label: t("workspace.breadcrumb.home"), icon: Layers, end: true }]

  const sidebarWidth = sidebarCollapsed ? "w-14" : "w-[200px]"

  return (
    <aside
      data-testid="visual-app-sidebar"
      className={cn(
        "relative z-[100] flex h-screen shrink-0 flex-col transition-all duration-200 ease-in-out",
        sidebarWidth,
      )}
      style={{ backgroundColor: "#F3F5F7" }}
    >
      <div className={cn("flex h-14 items-center px-3", sidebarCollapsed && "justify-center")}>
        <div className={cn("flex items-center gap-2.5 overflow-hidden", sidebarCollapsed && "justify-center")}>
          <img src="/images/logo-icon.png" alt="Anybackup" className="h-6 w-6 shrink-0 object-contain" />
          {!sidebarCollapsed && (
            <div className="flex items-baseline gap-1.5 whitespace-nowrap">
              <span className="text-[15px] font-semibold tracking-tight text-foreground">Anybackup</span>
              <span className="text-[13px] font-semibold text-[hsl(var(--ai))]">Agent</span>
            </div>
          )}
        </div>
      </div>

      <nav className="flex flex-1 flex-col gap-1 overflow-x-hidden overflow-y-auto py-3">
        {navItems.map((item) => {
          const Icon = item.icon
          return (
            <div key={item.to} className="px-2">
              <NavLink
                to={item.to}
                end={item.end}
                title={item.label}
                className={({ isActive }) =>
                  cn(
                    "flex w-full items-center gap-3 rounded-lg transition-all duration-200",
                    sidebarCollapsed ? "h-10 justify-center" : "h-9 px-3",
                    isActive
                      ? "bg-white text-primary shadow-sm"
                      : "text-muted-foreground hover:bg-white/60 hover:text-foreground",
                  )
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon className={cn("h-5 w-5 shrink-0", isActive && "text-primary")} />
                    {!sidebarCollapsed && <span className="truncate text-sm font-medium">{item.label}</span>}
                  </>
                )}
              </NavLink>
            </div>
          )
        })}
      </nav>

      <div className="flex flex-col gap-1 py-3">
        <div className={cn("px-2", sidebarCollapsed && "flex flex-col items-center gap-1")}>
          <div className={cn("flex items-center gap-1", !sidebarCollapsed && "mb-1")}>
            <SidebarAccountMenu
              sidebarCollapsed={sidebarCollapsed}
              displayName={displayName}
              accountName={accountName}
              roleLabel={roleLabel}
              logoutLabel={t("sidebar.logout")}
              panelPositionClass={sidebarCollapsed ? "fixed bottom-4 left-[72px]" : "fixed bottom-4 left-[208px]"}
              onLogout={async () => {
                await logout()
                navigate(routes.login)
              }}
            />
            {!sidebarCollapsed && (
              <button
                type="button"
                onClick={toggleSidebar}
                data-testid="app-sidebar-collapse-toggle"
                title={t("sidebar.collapseSidebar")}
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-all duration-200 hover:bg-white/60 hover:text-foreground"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>

        {sidebarCollapsed ? (
          <div className="px-2">
            <button
              type="button"
              onClick={toggleSidebar}
              data-testid="app-sidebar-expand-toggle"
              title={t("sidebar.expandSidebar")}
              className="flex h-10 w-full items-center justify-center rounded-lg text-muted-foreground transition-all duration-200 hover:bg-white/60 hover:text-foreground"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
          </div>
        ) : null}

        <div className="px-2">
          <div className={cn("flex gap-1", sidebarCollapsed && "flex-col")}>
            <NavLink
              to={routes.settings}
              aria-label={t("sidebar.settings")}
              title={t("sidebar.settings")}
              className={({ isActive }) =>
                cn(
                  "flex items-center justify-center rounded-lg transition-all duration-200",
                  sidebarCollapsed ? "h-10 w-full" : "h-9 flex-1",
                  isActive
                    ? "bg-white text-primary shadow-sm"
                    : "text-muted-foreground hover:bg-white/60 hover:text-foreground",
                )
              }
            >
              {({ isActive }) => <Settings className={cn("h-4 w-4 shrink-0", isActive && "text-primary")} />}
            </NavLink>

            <NavLink
              to={routes.users}
              aria-label={t("settings.userManagementTitle")}
              title={t("settings.userManagementTitle")}
              className={({ isActive }) =>
                cn(
                  "flex items-center justify-center rounded-lg transition-all duration-200",
                  sidebarCollapsed ? "h-10 w-full" : "h-9 flex-1",
                  isActive
                    ? "bg-white text-primary shadow-sm"
                    : "text-muted-foreground hover:bg-white/60 hover:text-foreground",
                )
              }
            >
              {({ isActive }) => <Users className={cn("h-4 w-4 shrink-0", isActive && "text-primary")} />}
            </NavLink>
          </div>
        </div>
      </div>
    </aside>
  )
}
