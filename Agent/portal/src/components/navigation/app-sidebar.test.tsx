import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { AppSidebar } from "@/components/navigation/app-sidebar"
import { useAuthStore } from "@/store/useAuthStore"
import { useLayoutStore } from "@/store/useLayoutStore"

function seedUser() {
  useAuthStore.setState({
    currentUser: {
      id: "user-001",
      username: "admin",
      displayName: "Backup Admin",
      role: "backup_admin",
      tenantId: "tenant-001",
    },
    bootstrapped: true,
    loading: false,
    error: null,
  })
}

describe("AppSidebar", () => {
  beforeEach(() => {
    seedUser()
    useLayoutStore.setState({ sidebarCollapsed: false })
  })

  it("keeps settings and user management outside the account popover while exposing account details inside it", async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <AppSidebar />
      </MemoryRouter>,
    )

    expect(screen.getAllByRole("link", { name: "Settings" })).toHaveLength(1)
    expect(screen.getAllByRole("link", { name: "User Management" })).toHaveLength(1)

    await user.click(screen.getByRole("button", { name: /Backup Admin/i }))

    expect(screen.getAllByRole("link", { name: "Settings" })).toHaveLength(1)
    expect(screen.getAllByRole("link", { name: "User Management" })).toHaveLength(1)
    expect(screen.getByText("System Administrator")).toBeInTheDocument()
    expect(screen.getByText("admin")).toBeInTheDocument()
    expect(screen.getByText("Language")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument()
  })

  it("logs out through the auth store from the account popover", async () => {
    const logout = vi.fn().mockResolvedValue(undefined)
    useAuthStore.setState({ logout })
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <AppSidebar />
      </MemoryRouter>,
    )

    await user.click(screen.getByRole("button", { name: /Backup Admin/i }))
    await user.click(screen.getByRole("button", { name: "Sign out" }))

    expect(logout).toHaveBeenCalledTimes(1)
  })
})
