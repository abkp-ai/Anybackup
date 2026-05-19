import { useEffect, useRef, useState } from "react"
import { Globe, LogOut, User } from "lucide-react"
import { cn } from "@/lib/cn"
import { useI18n } from "@/i18n"

interface SidebarAccountMenuProps {
  sidebarCollapsed: boolean
  displayName: string
  accountName: string
  roleLabel: string
  logoutLabel: string
  onLogout: () => Promise<void> | void
  panelPositionClass?: string
}

export function SidebarAccountMenu({
  sidebarCollapsed,
  displayName,
  accountName,
  roleLabel,
  logoutLabel,
  onLogout,
  panelPositionClass,
}: SidebarAccountMenuProps) {
  const { locale, setLocale, t } = useI18n()
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!userMenuOpen) return

    const handler = (event: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setUserMenuOpen(false)
      }
    }

    document.addEventListener("mousedown", handler)
    return () => document.removeEventListener("mousedown", handler)
  }, [userMenuOpen])

  const handleLogout = async () => {
    setUserMenuOpen(false)
    await onLogout()
  }

  const popoverPositionClass = panelPositionClass ?? "absolute bottom-0 left-[calc(100%+8px)]"

  return (
    <div className="relative min-w-0 flex-1" ref={menuRef} data-testid="sidebar-account-menu-root">
      <button
        type="button"
        onClick={() => setUserMenuOpen((open) => !open)}
        title={sidebarCollapsed ? displayName : undefined}
        data-testid="sidebar-account-menu-button"
        className={cn(
          "focus-ring transition-all duration-200",
          sidebarCollapsed
            ? "flex h-10 w-full items-center justify-center rounded-lg"
            : "flex h-9 w-full items-center gap-3 rounded-lg px-3",
          userMenuOpen ? "bg-white shadow-sm" : "hover:bg-white/60",
        )}
      >
        <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[hsl(var(--ai))] to-[hsl(var(--ai)/0.7)] text-primary-foreground">
          <User className="h-3.5 w-3.5" />
        </div>

        {!sidebarCollapsed ? (
          <div className="min-w-0 flex-1 text-left">
            <span className="block truncate text-sm font-medium text-foreground">{displayName}</span>
          </div>
        ) : null}
      </button>

      {userMenuOpen ? (
        <div
          data-testid="sidebar-account-menu-panel"
          className={cn(
            "z-[160] w-64 overflow-hidden rounded-xl border border-border bg-card shadow-lg animate-fade-in-scale",
            popoverPositionClass,
          )}
        >
          <div className="border-b border-border bg-gradient-to-br from-[hsl(var(--ai)/0.05)] to-transparent p-4">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-[hsl(var(--ai))] to-[hsl(var(--ai)/0.7)] text-primary-foreground shadow-sm">
                <User className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-semibold text-foreground">{displayName}</p>
                <p className="text-[11px] text-muted-foreground">{roleLabel}</p>
                <p className="mt-0.5 truncate text-[10px] text-muted-foreground/70">{accountName}</p>
              </div>
            </div>
          </div>
          <div className="border-b border-border px-4 py-3">
            <div className="flex items-center justify-between gap-4">
              <span className="flex items-center gap-2 text-xs text-muted-foreground">
                <Globe className="h-3.5 w-3.5" />
                {t("sidebar.language")}
              </span>
              <div className="flex items-center rounded-lg bg-secondary p-0.5">
                <button
                  type="button"
                  onClick={() => setLocale("zh-CN")}
                  className={cn(
                    "rounded-md px-2.5 py-1 text-[11px] font-medium transition-all duration-200",
                    locale === "zh-CN"
                      ? "bg-card text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {t("language.zhShort")}
                </button>
                <button
                  type="button"
                  onClick={() => setLocale("en")}
                  className={cn(
                    "rounded-md px-2.5 py-1 text-[11px] font-medium transition-all duration-200",
                    locale === "en"
                      ? "bg-card text-foreground shadow-sm"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  English
                </button>
              </div>
            </div>
          </div>
          <div className="p-2">
            <button
              type="button"
              onClick={() => void handleLogout()}
              className="focus-ring flex w-full items-center gap-2.5 rounded-lg px-3 py-2 text-xs font-medium text-destructive transition-all duration-200 hover:bg-destructive/5"
            >
              <LogOut className="h-3.5 w-3.5" />
              {logoutLabel}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
