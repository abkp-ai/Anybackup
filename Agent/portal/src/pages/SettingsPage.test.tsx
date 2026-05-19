import { render, screen } from "@testing-library/react"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { routes } from "@/config/routes"
import { SettingsPage } from "@/pages/SettingsPage"
import { useAuthStore } from "@/store/useAuthStore"
import { useUserManagementStore } from "@/store/useUserManagementStore"

describe("SettingsPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks()
    localStorage.clear()
    useAuthStore.setState({
      currentUser: {
        id: "user-001",
        username: "admin",
        displayName: "Backup Administrator",
        role: "backup_admin",
        tenantId: "tenant-001",
      },
      bootstrapped: true,
      loading: false,
      error: null,
    })
    useUserManagementStore.setState({
      users: [
        {
          id: "user-001",
          username: "admin",
          displayName: "Backup Administrator",
          role: "backup_admin",
          status: "enabled",
          createdAt: "2026-05-01T08:00:00.000Z",
          updatedAt: "2026-05-01T08:00:00.000Z",
          lastLoginAt: "2026-05-08T10:30:00.000Z",
        },
        {
          id: "user-002",
          username: "operator",
          displayName: "Operations Lead",
          role: "backup_admin",
          status: "disabled",
          createdAt: "2026-05-02T08:00:00.000Z",
          updatedAt: "2026-05-03T08:00:00.000Z",
        },
      ],
      loading: false,
      loadedOnce: true,
      saving: false,
      message: null,
      error: null,
      feedbackAutoDismiss: false,
      searchQuery: "",
      statusFilter: "all",
    })
  })

  it("renders a settings-only entry without the user management jump card", () => {
    render(
      <MemoryRouter initialEntries={[routes.settings]}>
        <SettingsPage />
      </MemoryRouter>,
    )

    expect(screen.getByRole("heading", { name: "Settings", level: 1 })).toBeInTheDocument()
    expect(screen.getAllByText("Signed in as")).toHaveLength(1)
    expect(screen.getByText("Backup Administrator")).toBeInTheDocument()
    expect(screen.getAllByText("Current language")).toHaveLength(1)
    expect(screen.getByText("English")).toBeInTheDocument()

    expect(screen.queryByRole("link", { name: "Open User Management" })).not.toBeInTheDocument()
    expect(screen.queryByText("View users, create users, enable or disable accounts, and reset passwords as an administrator.")).not.toBeInTheDocument()
    expect(screen.queryByText("Enabled 1 / 2")).not.toBeInTheDocument()
    expect(screen.queryByText("Total users")).not.toBeInTheDocument()
  })
})
