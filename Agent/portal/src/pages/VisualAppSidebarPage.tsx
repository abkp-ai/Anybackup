import { useEffect } from "react"
import { AppSidebar } from "@/components/navigation/app-sidebar"
import { useLayoutStore } from "@/store/useLayoutStore"

export function VisualAppSidebarPage() {
  const sidebarCollapsed = useLayoutStore((state) => state.sidebarCollapsed)

  useEffect(() => {
    useLayoutStore.setState({ sidebarCollapsed: true })
  }, [])

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#F3F5F7]">
      <AppSidebar />
      <main
        className="flex-1"
        style={{
          backgroundColor: "#F8F9FA",
          borderTopLeftRadius: sidebarCollapsed ? 0 : 24,
        }}
      />
    </div>
  )
}
