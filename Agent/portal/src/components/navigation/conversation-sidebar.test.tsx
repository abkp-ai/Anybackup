import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { MemoryRouter } from "react-router-dom"
import { beforeEach, describe, expect, it } from "vitest"
import { ConversationSidebar } from "@/components/navigation/conversation-sidebar"
import { useAuthStore } from "@/store/useAuthStore"
import { useConversationStore } from "@/store/useConversationStore"
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

describe("ConversationSidebar", () => {
  beforeEach(() => {
    seedUser()
    useLayoutStore.setState({ sidebarCollapsed: false })
    useConversationStore.setState({
      conversations: [
        {
          conversationId: "conv-001",
          title: "Order database recovery",
          updatedAt: "2026-04-22T16:00:00+08:00",
        },
      ],
      query: "",
      listLoading: false,
      selectedWorkspace: {
        kind: "localDraft",
        localDraftId: "local-001",
      },
      error: null,
    })
  })

  it("uses the prototype-like brand row with a compact standalone new-conversation button", () => {
    const { container } = render(
      <MemoryRouter>
        <ConversationSidebar />
      </MemoryRouter>,
    )

    const aside = container.querySelector("aside")
    const newConversationButton = screen.getByRole("button", { name: "New conversation" })
    const searchInput = screen.getByPlaceholderText("Search conversations")

    expect(aside).toHaveClass("w-[240px]")
    expect(screen.getByText("Anybackup")).toBeInTheDocument()
    expect(screen.getByText("Agent")).toBeInTheDocument()
    expect(newConversationButton).toHaveClass("h-7", "rounded-sm", "text-xs")
    expect(searchInput).toHaveClass("text-xs")
    expect(searchInput.parentElement).toHaveClass("h-7", "rounded-sm")
  })

  it("keeps settings and user management separate from the user menu and shows logout inside the menu", async () => {
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <ConversationSidebar />
      </MemoryRouter>,
    )

    expect(screen.getAllByRole("button", { name: "Settings" })).toHaveLength(1)
    expect(screen.getAllByRole("button", { name: "User Management" })).toHaveLength(1)

    await user.click(screen.getByRole("button", { name: /Backup Admin/i }))

    expect(screen.getAllByRole("button", { name: "Settings" })).toHaveLength(1)
    expect(screen.getAllByRole("button", { name: "User Management" })).toHaveLength(1)
    expect(screen.getByText("System Administrator")).toBeInTheDocument()
    expect(screen.getByText("admin")).toBeInTheDocument()
    expect(screen.getByText("Language")).toBeInTheDocument()
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument()
    expect(screen.getByTestId("sidebar-account-menu-panel")).toHaveClass("fixed", "bottom-[54px]", "left-[248px]")
  })

  it("renders history items with the lighter list treatment from the prototype", () => {
    render(
      <MemoryRouter>
        <ConversationSidebar />
      </MemoryRouter>,
    )

    const historyButton = screen.getByRole("button", { name: "Order database recovery" })

    expect(historyButton).toHaveClass("h-9", "rounded-md", "text-xs")
    expect(historyButton).not.toHaveClass("rounded-2xl")
  })

  it("shows all history items when the sidebar is collapsed", () => {
    useLayoutStore.setState({ sidebarCollapsed: true })
    useConversationStore.setState({
      conversations: [
        {
          conversationId: "conv-001",
          title: "Conversation A",
          updatedAt: "2026-04-22T16:00:00+08:00",
        },
        {
          conversationId: "conv-002",
          title: "Conversation B",
          updatedAt: "2026-04-22T16:01:00+08:00",
        },
        {
          conversationId: "conv-003",
          title: "Conversation C",
          updatedAt: "2026-04-22T16:02:00+08:00",
        },
        {
          conversationId: "conv-004",
          title: "Conversation D",
          updatedAt: "2026-04-22T16:03:00+08:00",
        },
      ],
    })

    render(
      <MemoryRouter>
        <ConversationSidebar />
      </MemoryRouter>,
    )

    expect(screen.getByTitle("Conversation A")).toBeInTheDocument()
    expect(screen.getByTitle("Conversation B")).toBeInTheDocument()
    expect(screen.getByTitle("Conversation C")).toBeInTheDocument()
    expect(screen.getByTitle("Conversation D")).toBeInTheDocument()
  })

  it("pins the collapsed account popover to the sidebar edge instead of the trigger width", async () => {
    useLayoutStore.setState({ sidebarCollapsed: true })
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <ConversationSidebar />
      </MemoryRouter>,
    )

    await user.click(screen.getByTestId("sidebar-account-menu-button"))

    expect(screen.getByTestId("sidebar-account-menu-panel")).toHaveClass("fixed", "bottom-[100px]", "left-[72px]")
  })
})
