import { fireEvent, render, screen, within } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { storeSession } from "@/lib/session"
import { UserManagementPage } from "@/pages/UserManagementPage"
import { useAuthStore } from "@/store/useAuthStore"
import { useUserManagementStore } from "@/store/useUserManagementStore"
import type { AuthSession } from "@/types/auth"

function jsonResponse(body: unknown, status = 200, headers?: HeadersInit): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  })
}

function emptyResponse(status = 204, headers?: HeadersInit): Response {
  return new Response(null, { status, headers })
}

function keycloakUser(overrides: Record<string, unknown> = {}) {
  return {
    id: "user-001",
    username: "admin",
    firstName: "Backup Administrator",
    enabled: true,
    createdTimestamp: 1_713_600_000_000,
    attributes: {
      remark: ["System administrator"],
      lastLoginAt: ["2026-05-08T10:30:00.000Z"],
    },
    ...overrides,
  }
}

function storeApiSession() {
  const now = Date.now()
  storeSession({
    accessToken: "access-token",
    refreshToken: "refresh-token",
    tokenType: "Bearer",
    expiresAt: now + 300_000,
    refreshExpiresAt: now + 1_800_000,
    idleExpiresAt: now + 1_800_000,
    user: {
      id: "user-001",
      username: "admin",
      displayName: "Backup Administrator",
      role: "backup_admin",
      tenantId: "master",
    },
  } as AuthSession)
}

describe("UserManagementPage", () => {
  const fetchMock = vi.fn<typeof fetch>()

  afterEach(() => {
    vi.useRealTimers()
  })

  beforeEach(() => {
    vi.restoreAllMocks()
    fetchMock.mockReset()
    vi.stubGlobal("fetch", fetchMock)
    localStorage.clear()
    storeApiSession()
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
      users: [],
      loading: false,
      loadedOnce: false,
      saving: false,
      message: null,
      error: null,
      feedbackAutoDismiss: false,
      searchQuery: "",
      statusFilter: "all",
    })
  })

  it("renders a compact user list card without the old workbench header and filters", async () => {
    fetchMock.mockResolvedValueOnce(
      jsonResponse([
        keycloakUser(),
        keycloakUser({
          id: "user-002",
          username: "operator",
          firstName: "Operations Lead",
          enabled: true,
          attributes: {
            remark: ["Regional operator"],
            lastLoginAt: ["2026-05-08T08:00:00.000Z"],
          },
        }),
        keycloakUser({
          id: "user-003",
          username: "disabled-user",
          firstName: "Disabled Analyst",
          enabled: false,
          attributes: {
            remark: ["Temporary account"],
          },
        }),
      ]),
    )

    const { container } = render(<UserManagementPage />)

    await screen.findByRole("table")
    const tableCard = container.querySelector("[data-user-management-table-card]")

    if (!(tableCard instanceof HTMLElement)) {
      throw new Error("Expected user management table card")
    }

    expect(screen.queryByRole("heading", { name: "User Management", level: 1 })).not.toBeInTheDocument()
    expect(screen.queryByLabelText("User statistics")).not.toBeInTheDocument()
    expect(screen.queryByLabelText("Search users")).not.toBeInTheDocument()
    expect(screen.queryByLabelText("Status")).not.toBeInTheDocument()
    expect(within(tableCard).getByRole("button", { name: "New user" })).toBeInTheDocument()
    expect(screen.getByRole("table")).toBeInTheDocument()
    expect(container.querySelector("[data-user-management-header]")).toBeNull()
  })

  it("creates a new user and assigns the builtin admin role", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse([keycloakUser()]))
    fetchMock.mockResolvedValueOnce(
      emptyResponse(201, {
        Location: "/api/auth_service/v1/admin/realms/master/users/user-002",
      }),
    )
    fetchMock.mockResolvedValueOnce(
      jsonResponse(
        keycloakUser({
          id: "user-002",
          username: "operator",
          firstName: "Operations Lead",
        }),
      ),
    )
    fetchMock.mockResolvedValueOnce(
      jsonResponse({
        id: "role-001",
        name: "backup_admin",
      }),
    )
    fetchMock.mockResolvedValueOnce(emptyResponse(204))
    fetchMock.mockResolvedValueOnce(
      jsonResponse([
        keycloakUser({
          id: "user-002",
          username: "operator",
          firstName: "Operations Lead",
        }),
        keycloakUser(),
      ]),
    )

    const user = userEvent.setup()
    render(<UserManagementPage />)

    await user.click(await screen.findByRole("button", { name: "New user" }))

    const dialog = await screen.findByRole("dialog")
    await user.type(within(dialog).getByLabelText(/^Username/i), "operator")
    await user.type(within(dialog).getByLabelText(/^Display name/i), "Operations Lead")

    const passwordInput = dialog.querySelector("#password")
    const confirmInput = dialog.querySelector("#confirmPassword")
    if (!(passwordInput instanceof HTMLInputElement) || !(confirmInput instanceof HTMLInputElement)) {
      throw new Error("Expected password fields in create-user dialog")
    }
    await user.type(passwordInput, "operator123")
    await user.type(confirmInput, "operator123")
    await user.click(within(dialog).getByRole("button", { name: "Create user" }))

    expect(await screen.findByText("User created.")).toBeInTheDocument()
    expect(await screen.findByText("operator")).toBeInTheDocument()

    const [roleUrl] = fetchMock.mock.calls[3]
    expect(roleUrl).toBe("/api/auth_service/v1/admin/realms/master/roles/backup_admin")

    const [mappingUrl, mappingInit] = fetchMock.mock.calls[4]
    expect(mappingUrl).toBe("/api/auth_service/v1/admin/realms/master/users/user-002/role-mappings/realm")
    expect(mappingInit?.method).toBe("POST")
    expect(JSON.parse(String(mappingInit?.body))).toEqual([
      {
        id: "role-001",
        name: "backup_admin",
      },
    ])
  })

  it("shows required validation errors under create inputs instead of page-level errors", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse([keycloakUser()]))
    const user = userEvent.setup()

    render(<UserManagementPage />)

    await user.click(await screen.findByRole("button", { name: "New user" }))

    const dialog = screen.getByRole("dialog")
    const form = dialog.querySelector("#user-form")
    if (!(form instanceof HTMLFormElement)) {
      throw new Error("user form not found")
    }

    fireEvent.submit(form)

    expect(await within(dialog).findByText("Please enter username")).toBeInTheDocument()
    expect(within(dialog).getByText("Please enter display name")).toBeInTheDocument()
    expect(within(dialog).getByText("Please enter password")).toBeInTheDocument()
    expect(within(dialog).getByText("Please confirm password")).toBeInTheDocument()
    expect(screen.queryByRole("alert")).not.toBeInTheDocument()
  })

  it("prevents disabling the current user", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse([keycloakUser()]))
    const user = userEvent.setup()
    render(<UserManagementPage />)

    await screen.findByText("admin")
    await user.click(screen.getByRole("button", { name: "Disable admin" }))

    expect(await screen.findByRole("alert")).toHaveTextContent("You cannot disable the currently signed-in user")
  })

  it("hides the remark field in the create user dialog", async () => {
    fetchMock.mockResolvedValueOnce(jsonResponse([keycloakUser()]))
    const user = userEvent.setup()

    render(<UserManagementPage />)

    await user.click(await screen.findByRole("button", { name: "New user" }))

    const dialog = await screen.findByRole("dialog")
    expect(dialog.querySelector('textarea[name="remark"]')).toBeNull()
  })
})
