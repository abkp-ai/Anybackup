import { useEffect, useMemo, useState } from "react"
import { UserManagementFeedback } from "@/components/settings/user-management/user-management-feedback"
import { UserManagementTable } from "@/components/settings/user-management/user-management-table"
import { UserFormModal } from "@/components/settings/user-management/user-form-modal"
import { ResetPasswordModal } from "@/components/settings/user-management/reset-password-modal"
import { DisableUserModal } from "@/components/settings/user-management/disable-user-modal"
import { useI18n } from "@/i18n"
import { useAuthStore } from "@/store/useAuthStore"
import { useUserManagementStore } from "@/store/useUserManagementStore"

const FEEDBACK_DISMISS_DELAY_MS = 4000

export function UserManagementPageContent() {
  const { t } = useI18n()
  const currentUser = useAuthStore((state) => state.currentUser)
  const users = useUserManagementStore((state) => state.users)
  const isLoading = useUserManagementStore((state) => state.loading)
  const isSaving = useUserManagementStore((state) => state.saving)
  const message = useUserManagementStore((state) => state.message)
  const error = useUserManagementStore((state) => state.error)
  const feedbackAutoDismiss = useUserManagementStore((state) => state.feedbackAutoDismiss)
  const loadUsers = useUserManagementStore((state) => state.loadUsers)
  const create = useUserManagementStore((state) => state.create)
  const update = useUserManagementStore((state) => state.update)
  const enable = useUserManagementStore((state) => state.enable)
  const disable = useUserManagementStore((state) => state.disable)
  const resetPassword = useUserManagementStore((state) => state.resetPassword)
  const clearFeedback = useUserManagementStore((state) => state.clearFeedback)

  const [formMode, setFormMode] = useState<"create" | "edit" | null>(null)
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null)
  const [resetUserId, setResetUserId] = useState<string | null>(null)
  const [disableUserId, setDisableUserId] = useState<string | null>(null)

  useEffect(() => {
    void loadUsers()
  }, [loadUsers])

  useEffect(() => {
    if (!feedbackAutoDismiss || (!message && !error)) return

    const timeoutId = window.setTimeout(() => {
      clearFeedback()
    }, FEEDBACK_DISMISS_DELAY_MS)

    return () => window.clearTimeout(timeoutId)
  }, [clearFeedback, error, feedbackAutoDismiss, message])

  const selectedUser = useMemo(
    () => users.find((user) => user.id === selectedUserId),
    [selectedUserId, users],
  )
  const resetUser = useMemo(() => users.find((user) => user.id === resetUserId), [resetUserId, users])
  const disablingUser = useMemo(() => users.find((user) => user.id === disableUserId), [disableUserId, users])

  const onDisableClick = (userId: string) => {
    if (userId === currentUser?.id) {
      void disable(userId, currentUser.id).catch(() => undefined)
      return
    }
    setDisableUserId(userId)
  }

  return (
    <div data-user-management-page className="h-full min-h-0 flex-1 overflow-auto p-6">
      <div className="mx-auto flex max-w-6xl flex-col gap-4">
        <UserManagementFeedback message={message} error={error} />
        <UserManagementTable
          users={users}
          loading={isLoading}
          emptyStateLabel={t("usersPage.empty")}
          currentUserId={currentUser?.id}
          onCreate={() => {
            setSelectedUserId(null)
            setFormMode("create")
          }}
          onEdit={(userId) => {
            setSelectedUserId(userId)
            setFormMode("edit")
          }}
          onDisable={onDisableClick}
          onEnable={(userId) => void enable(userId).catch(() => undefined)}
          onResetPassword={setResetUserId}
        />
      </div>

      <UserFormModal
        open={formMode !== null}
        mode={formMode ?? "create"}
        user={selectedUser}
        saving={isSaving}
        onClose={() => setFormMode(null)}
        onCreate={create}
        onUpdate={update}
      />
      <ResetPasswordModal
        open={Boolean(resetUserId)}
        user={resetUser}
        saving={isSaving}
        onClose={() => setResetUserId(null)}
        onReset={resetPassword}
      />
      <DisableUserModal
        open={Boolean(disableUserId)}
        user={disablingUser}
        saving={isSaving}
        onClose={() => setDisableUserId(null)}
        onConfirm={(userId) => disable(userId, currentUser?.id ?? "")}
      />
    </div>
  )
}
