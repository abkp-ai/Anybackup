import { useNavigate } from "react-router-dom"
import {
  ChevronLeft,
  ChevronRight,
  LoaderCircle,
  MessageSquare,
  MessageSquarePlus,
  Search,
  Settings,
  Users,
} from "lucide-react"
import { routes } from "@/config/routes"
import { useI18n } from "@/i18n"
import { cn } from "@/lib/cn"
import { useAuthStore } from "@/store/useAuthStore"
import { useConversationStore } from "@/store/useConversationStore"
import { useLayoutStore } from "@/store/useLayoutStore"
import type { ConversationSummary } from "@/types/conversation"
import { SidebarAccountMenu } from "@/components/navigation/sidebar-account-menu"

export function ConversationSidebar() {
  const { t } = useI18n()
  const navigate = useNavigate()
  const sidebarCollapsed = useLayoutStore((state) => state.sidebarCollapsed)
  const toggleSidebar = useLayoutStore((state) => state.toggleSidebar)
  const currentUser = useAuthStore((state) => state.currentUser)
  const logout = useAuthStore((state) => state.logout)
  const conversations = useConversationStore((state) => state.conversations)
  const query = useConversationStore((state) => state.query)
  const listLoading = useConversationStore((state) => state.listLoading)
  const selectedWorkspace = useConversationStore((state) => state.selectedWorkspace)
  const activateLocalDraftWorkspace = useConversationStore((state) => state.activateLocalDraftWorkspace)
  const selectConversation = useConversationStore((state) => state.selectConversation)
  const setSearchQuery = useConversationStore((state) => state.setSearchQuery)

  const displayName = currentUser?.displayName ?? t("sidebar.demoUser")
  const accountName = currentUser?.username ?? "Melon.zhao@aishu.cn"
  const roleLabel = t("sidebar.systemAdmin")
  const accountMenuPanelPositionClass = sidebarCollapsed
    ? "fixed bottom-[100px] left-[72px]"
    : "fixed bottom-[54px] left-[248px]"

  const handleNewConversation = () => {
    activateLocalDraftWorkspace()
    navigate(routes.home)
  }

  const handleSelectConversation = async (conversationId: string) => {
    navigate(routes.home)
    try {
      await selectConversation(conversationId)
    } catch {
      // The store already exposes the error to the main panel.
    }
  }

  const handleLogout = async () => {
    await logout()
    navigate(routes.login)
  }

  const renderHistoryButton = (conversation: ConversationSummary, collapsed = false) => {
    const isActiveConversation =
      selectedWorkspace?.kind === "conversation" && selectedWorkspace.conversationId === conversation.conversationId

    return (
      <button
        key={conversation.conversationId}
        type="button"
        onClick={() => void handleSelectConversation(conversation.conversationId)}
        title={collapsed ? conversation.title : undefined}
        className={cn(
          "focus-ring transition-fast",
          collapsed
            ? "flex h-10 w-10 items-center justify-center rounded-lg bg-white/85 text-xs font-semibold text-foreground shadow-[var(--shadow-xs)] hover:bg-white"
            : "flex h-9 w-full items-center gap-2 rounded-md px-2.5 text-left text-xs",
          isActiveConversation
            ? collapsed
              ? "bg-ai-surface text-ai shadow-card"
              : "bg-accent text-accent-foreground shadow-sm"
            : collapsed
              ? "border-transparent"
              : "text-foreground/70 hover:bg-accent/50",
        )}
      >
        {collapsed ? (
          conversation.title.slice(0, 1)
        ) : (
          <>
            <MessageSquare className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
            <span className="min-w-0 truncate font-medium">{conversation.title}</span>
          </>
        )}
      </button>
    )
  }

  return (
    <aside
      className={cn(
        "flex h-screen shrink-0 flex-col border-r border-border/70 bg-[hsl(var(--sidebar))] transition-all duration-200 ease-in-out",
        sidebarCollapsed ? "w-14" : "w-[240px]",
      )}
    >
      <div className={cn("flex h-14 items-center px-3", sidebarCollapsed && "justify-center")}>
        <div className={cn("flex items-center gap-2.5 overflow-hidden", sidebarCollapsed && "justify-center")}>
          <img src="/images/logo-icon.png" alt="Anybackup" className="h-6 w-6 shrink-0 object-contain" />
          {!sidebarCollapsed ? (
            <div className="flex items-baseline gap-1.5 whitespace-nowrap">
              <span className="text-[15px] font-semibold tracking-tight text-foreground">Anybackup</span>
              <span className="text-[13px] font-semibold text-[hsl(var(--ai))]">Agent</span>
            </div>
          ) : null}
        </div>
      </div>

      {!sidebarCollapsed ? (
        <div className="px-3 pb-2 pt-2">
          <button
            type="button"
            onClick={handleNewConversation}
            title={t("sidebar.newConversation")}
            className={cn(
              "focus-ring flex h-7 w-full items-center gap-2 rounded-sm border border-border/60 bg-white/75 px-2.5 text-xs font-medium text-foreground transition-fast hover:bg-white hover:shadow-card",
              selectedWorkspace?.kind === "localDraft" && "bg-white shadow-sm",
            )}
          >
            <MessageSquarePlus className="h-3 w-3 shrink-0 text-ai" />
            <span>{t("sidebar.newConversation")}</span>
          </button>
        </div>
      ) : null}

      {!sidebarCollapsed ? (
        <div className="px-3 pb-1.5">
          <label className="relative flex h-7 items-center rounded-sm border border-input bg-background transition-fast focus-within:border-ai/30 focus-within:ring-2 focus-within:ring-ai/10">
            <Search className="absolute left-2 top-1/2 h-3 w-3 shrink-0 -translate-y-1/2 text-muted-foreground" />
            <input
              value={query}
              onChange={(event) => void setSearchQuery(event.target.value)}
              placeholder={t("sidebar.searchConversation")}
              className="min-w-0 flex-1 border-0 bg-transparent pl-6 pr-2 text-xs text-foreground outline-none placeholder:text-muted-foreground"
            />
          </label>
        </div>
      ) : null}

      <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
        <div className="scrollbar-sidebar flex min-h-0 flex-1 flex-col overflow-y-auto px-2 pb-3">
          {sidebarCollapsed ? (
            <div className="flex flex-col items-center gap-2 pt-1">
              <button
                type="button"
                onClick={handleNewConversation}
                aria-label={t("sidebar.newConversation")}
                title={t("sidebar.newConversation")}
                className={cn(
                  "focus-ring flex h-10 w-10 items-center justify-center rounded-lg text-ai shadow-card transition-fast hover:bg-ai-surface",
                  selectedWorkspace?.kind === "localDraft" ? "bg-ai-surface" : "bg-white",
                )}
              >
                <MessageSquarePlus className="h-4 w-4" />
              </button>
              {conversations.map((conversation) => renderHistoryButton(conversation, true))}
            </div>
          ) : listLoading ? (
            <div className="mx-1 flex items-center gap-2 rounded-lg border border-border bg-white/85 px-3 py-2 text-xs text-muted-foreground shadow-card">
              <LoaderCircle className="h-4 w-4 animate-spin" />
              {t("sidebar.refreshingConversations")}
            </div>
          ) : conversations.length === 0 ? (
            <div className="mx-1 rounded-md border border-dashed border-border bg-white/60 px-3 py-4 text-xs text-muted-foreground">
              {query.trim() ? t("sidebar.noMatchedConversation") : t("sidebar.noConversationYet")}
            </div>
          ) : (
            <section>
              <div className="px-1 pb-2 text-xs font-semibold tracking-wider text-muted-foreground">
                {t("sidebar.historyConversation")}
                <span className="ml-1 font-normal text-muted-foreground/40">
                  ({conversations.length})
                </span>
              </div>
              <div className="space-y-0.5 px-1">{conversations.map((conversation) => renderHistoryButton(conversation))}</div>
            </section>
          )}
        </div>
      </div>

      <div className="flex flex-col gap-1 py-3">
        {sidebarCollapsed ? (
          <>
            <div className="px-2">
              <SidebarAccountMenu
                sidebarCollapsed={sidebarCollapsed}
                displayName={displayName}
                accountName={accountName}
                roleLabel={roleLabel}
                logoutLabel={t("sidebar.logout")}
                panelPositionClass={accountMenuPanelPositionClass}
                onLogout={handleLogout}
              />
            </div>
            <div className="px-2">
              <button
                type="button"
                onClick={toggleSidebar}
                title={t("sidebar.expandSidebar")}
                className="focus-ring flex h-10 w-full items-center justify-center rounded-lg text-muted-foreground transition-all duration-200 hover:bg-white/60 hover:text-foreground"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
            </div>
            <div className="px-2">
              <button
                type="button"
                onClick={() => navigate(routes.settings)}
                aria-label={t("sidebar.settings")}
                title={t("sidebar.settings")}
                className="focus-ring flex h-10 w-full items-center justify-center rounded-lg text-muted-foreground transition-all duration-200 hover:bg-white/60 hover:text-foreground"
              >
                <Settings className="h-4 w-4" />
              </button>
            </div>
            <div className="px-2">
              <button
                type="button"
                onClick={() => navigate(routes.users)}
                aria-label={t("settings.userManagementTitle")}
                title={t("settings.userManagementTitle")}
                className="focus-ring flex h-10 w-full items-center justify-center rounded-lg text-muted-foreground transition-all duration-200 hover:bg-white/60 hover:text-foreground"
              >
                <Users className="h-4 w-4" />
              </button>
            </div>
          </>
        ) : (
          <div className="px-2">
            <div className="mb-1.5 flex items-center gap-1">
              <SidebarAccountMenu
                sidebarCollapsed={sidebarCollapsed}
                displayName={displayName}
                accountName={accountName}
                roleLabel={roleLabel}
                logoutLabel={t("sidebar.logout")}
                panelPositionClass={accountMenuPanelPositionClass}
                onLogout={handleLogout}
              />
              <button
                type="button"
                onClick={toggleSidebar}
                aria-label={t("sidebar.collapseSidebar")}
                className="focus-ring flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-muted-foreground transition-all duration-200 hover:bg-white/60 hover:text-foreground"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
            </div>

            <div className="flex items-center gap-1">
              <button
                type="button"
                onClick={() => navigate(routes.settings)}
                aria-label={t("sidebar.settings")}
                title={t("sidebar.settings")}
                className="focus-ring flex h-9 flex-1 items-center justify-center rounded-lg text-muted-foreground transition-all duration-200 hover:bg-white/60 hover:text-foreground"
              >
                <Settings className="h-4 w-4 shrink-0" />
              </button>
              <button
                type="button"
                onClick={() => navigate(routes.users)}
                aria-label={t("settings.userManagementTitle")}
                title={t("settings.userManagementTitle")}
                className="focus-ring flex h-9 flex-1 items-center justify-center rounded-lg text-muted-foreground transition-all duration-200 hover:bg-white/60 hover:text-foreground"
              >
                <Users className="h-4 w-4 shrink-0" />
              </button>
            </div>
          </div>
        )}
      </div>
    </aside>
  )
}
