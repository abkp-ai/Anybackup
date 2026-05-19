import { render, screen } from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { describe, expect, it, vi } from "vitest"
import { SidebarAccountMenu } from "@/components/navigation/sidebar-account-menu"

function renderMenu(sidebarCollapsed: boolean) {
  const onLogout = vi.fn()

  render(
    <div className="flex">
      <SidebarAccountMenu
        sidebarCollapsed={sidebarCollapsed}
        displayName="Backup Admin"
        accountName="admin"
        roleLabel="Backup administrator"
        logoutLabel="Sign out"
        onLogout={onLogout}
      />
    </div>,
  )

  return { onLogout }
}

describe("SidebarAccountMenu", () => {
  it("opens the popover to the right in expanded mode", async () => {
    const user = userEvent.setup()
    renderMenu(false)

    await user.click(screen.getByRole("button", { name: /Backup Admin/i }))

    const popover = screen.getByRole("button", { name: "Sign out" }).parentElement?.parentElement

    expect(popover).toHaveClass("absolute", "bottom-0", "left-[calc(100%+8px)]")
    expect(popover).not.toHaveClass("bottom-[calc(100%+8px)]", "right-0")
  })

  it("keeps the popover to the right in collapsed mode", async () => {
    const user = userEvent.setup()
    renderMenu(true)

    await user.click(screen.getByRole("button", { name: /Backup Admin/i }))

    const popover = screen.getByRole("button", { name: "Sign out" }).parentElement?.parentElement

    expect(popover).toHaveClass("absolute", "bottom-0", "left-[calc(100%+8px)]")
  })
})
