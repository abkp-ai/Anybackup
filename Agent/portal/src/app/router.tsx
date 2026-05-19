import { createBrowserRouter, Navigate, useLocation } from "react-router-dom"
import type { ReactNode } from "react"
import { isAuthenticated, isGuideDone } from "@/lib/session"
import { routes } from "@/config/routes"
import { routerBasenameFromBasePath } from "@/config/base-path"

function loginRedirectFor(pathname: string, search: string) {
  const returnTo = encodeURIComponent(`${pathname}${search}`)
  return `${routes.login}?returnTo=${returnTo}`
}

function RequireAuthenticated({ children }: { children: ReactNode }) {
  const location = useLocation()

  if (!isAuthenticated()) return <Navigate to={loginRedirectFor(location.pathname, location.search)} replace />
  if (!isGuideDone()) return <Navigate to={routes.guide} replace />
  return <>{children}</>
}

export const router = createBrowserRouter(
  [
    {
      path: routes.login,
      lazy: async () => {
        const { LoginPage } = await import("@/pages/LoginPage")
        return { Component: LoginPage }
      },
    },
    {
      path: routes.guide,
      lazy: async () => {
        const { GuidePage } = await import("@/pages/GuidePage")
        const Component = () => {
          if (!isAuthenticated()) return <Navigate to={routes.login} replace />
          return <GuidePage />
        }
        return { Component }
      },
    },
    {
      path: routes.visualAppSidebar,
      lazy: async () => {
        const { VisualAppSidebarPage } = await import("@/pages/VisualAppSidebarPage")
        const Component = () => (
          <RequireAuthenticated>
            <VisualAppSidebarPage />
          </RequireAuthenticated>
        )
        return { Component }
      },
    },
    {
      path: "/",
      lazy: async () => {
        const { AppShell } = await import("@/components/layout/AppShell")
        const Component = () => (
          <RequireAuthenticated>
            <AppShell />
          </RequireAuthenticated>
        )
        return { Component }
      },
      children: [
        {
          index: true,
          lazy: async () => {
            const { HomePage } = await import("@/pages/HomePage")
            return { Component: HomePage }
          },
        },
        {
          path: "chat-demo",
          lazy: async () => {
            const { ChatStatesDemoPage } = await import("@/pages/ChatStatesDemoPage")
            return { Component: ChatStatesDemoPage }
          },
        },
        {
          path: "settings",
          lazy: async () => {
            const { SettingsPage } = await import("@/pages/SettingsPage")
            return { Component: SettingsPage }
          },
        },
        {
          path: "settings/users",
          lazy: async () => {
            const { UserManagementPage } = await import("@/pages/UserManagementPage")
            return { Component: UserManagementPage }
          },
        },
      ],
    },
  ],
  { basename: routerBasenameFromBasePath(import.meta.env.BASE_URL) },
)
