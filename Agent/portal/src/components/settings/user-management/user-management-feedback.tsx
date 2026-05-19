interface UserManagementFeedbackProps {
  message: string | null
  error: string | null
}

export function UserManagementFeedback({ message, error }: UserManagementFeedbackProps) {
  if (!message && !error) return null

  return (
    <div data-user-management-feedback className="space-y-3">
      {message ? (
        <div
          role="status"
          aria-live="polite"
          className="rounded-lg border border-success/15 bg-success-surface/85 px-4 py-3 text-sm text-success shadow-[var(--shadow-xs)]"
        >
          {message}
        </div>
      ) : null}
      {error ? (
        <div
          role="alert"
          className="rounded-lg border border-destructive/15 bg-destructive/5 px-4 py-3 text-sm text-destructive shadow-[var(--shadow-xs)]"
        >
          {error}
        </div>
      ) : null}
    </div>
  )
}
