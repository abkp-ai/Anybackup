import { create } from "zustand"
import { emitDebugLog } from "@/lib/debug-log"
import { translate } from "@/i18n/messages"
import { getCurrentUser, login, logoutCurrentUser } from "@/services/auth-service"
import type { CurrentUser, LoginRequest } from "@/types/auth"
import { ServiceError } from "@/types/auth"

interface AuthState {
  currentUser: CurrentUser | null
  bootstrapped: boolean
  loading: boolean
  error: string | null
}

interface AuthActions {
  bootstrap: () => Promise<void>
  login: (request: LoginRequest) => Promise<CurrentUser>
  logout: () => Promise<void>
  clearError: () => void
}

function toMessage(error: unknown): string {
  if (error instanceof ServiceError) return error.message
  return translate("errors.genericUnavailable")
}

export const useAuthStore = create<AuthState & AuthActions>((set) => ({
  currentUser: null,
  bootstrapped: false,
  loading: false,
  error: null,

  bootstrap: async () => {
    const startedAt = Date.now()
    emitDebugLog({
      location: "useAuthStore.ts:bootstrap:start",
      message: "auth bootstrap started",
      data: { hasStoredSession: Boolean(localStorage.getItem("agent_web_auth_session")) },
      hypothesisId: "H4",
    })
    try {
      const currentUser = await getCurrentUser()
      set({ currentUser, bootstrapped: true, error: null })
    } catch {
      set({ currentUser: null, bootstrapped: true })
    } finally {
      emitDebugLog({
        location: "useAuthStore.ts:bootstrap:end",
        message: "auth bootstrap finished",
        data: { durationMs: Date.now() - startedAt },
        hypothesisId: "H4",
      })
    }
  },

  login: async (request) => {
    set({ loading: true, error: null })
    try {
      const session = await login(request)
      const currentUser = session.user
      set({ currentUser, loading: false, error: null, bootstrapped: true })
      return currentUser
    } catch (error) {
      set({ loading: false, error: toMessage(error) })
      throw error
    }
  },

  logout: async () => {
    await logoutCurrentUser()
    set({ currentUser: null, loading: false, error: null, bootstrapped: true })
  },

  clearError: () => set({ error: null }),
}))
