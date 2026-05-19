import { useEffect, useState } from "react"
import { useNavigate, useSearchParams } from "react-router-dom"
import { motion } from "framer-motion"
import { AlertCircle, ArrowRight, Eye, EyeOff } from "lucide-react"
import { publicAssetUrlFromBasePath } from "@/config/base-path"
import { routes } from "@/config/routes"
import { isGuideDone } from "@/lib/session"
import { emitDebugLog } from "@/lib/debug-log"
import { validateLoginFields } from "@/lib/password-policy"
import { useAuthStore } from "@/store/useAuthStore"
import { Button } from "@/components/ui/button"
import { useI18n } from "@/i18n"
import { cn } from "@/lib/cn"

const logoIconUrl = publicAssetUrlFromBasePath(import.meta.env.BASE_URL, "/images/logo-icon.png")

export function LoginPage() {
  useEffect(() => {
    emitDebugLog({
      location: "LoginPage.tsx:mount",
      message: "login page rendered",
      data: { href: window.location.href },
      hypothesisId: "H1",
    })
  }, [])

  const { t } = useI18n()
  const [name, setName] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [error, setError] = useState("")
  const [fieldError, setFieldError] = useState<string | null>(null)
  const isLoading = useAuthStore((state) => state.loading)
  const login = useAuthStore((state) => state.login)
  const clearError = useAuthStore((state) => state.clearError)
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()

  const onSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (isLoading) return

    setError("")
    setFieldError(null)
    clearError()

    const validation = validateLoginFields(name, password)
    if (validation) {
      setFieldError(validation.field)
      setError(validation.message)
      return
    }

    try {
      const currentUser = await login({ username: name.trim(), password })
      const returnTo = searchParams.get("returnTo")
      navigate(returnTo || (isGuideDone(currentUser) ? routes.home : routes.guide), { replace: true })
    } catch (authError) {
      setError(authError instanceof Error ? authError.message : t("login.serviceUnavailable"))
    }
  }

  const fieldClass =
    "h-10 w-full rounded-md border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground transition-fast focus:border-ai/40 focus:outline-none focus:ring-2 focus:ring-ai/30"

  const showNameError = fieldError === "username"
  const showPasswordError = fieldError === "password"

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background p-4">
      <div className="pointer-events-none absolute inset-0 bg-gradient-hero" />

      <motion.div
        initial={{ opacity: 0, y: 20, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.4 }}
        className="relative mx-6 w-full max-w-sm"
      >
        <form className="rounded-xl border border-border bg-card p-8 shadow-card" onSubmit={onSubmit}>
          <div className="mb-8 flex flex-col items-center">
            <img src={logoIconUrl} alt="Anybackup" className="mb-3 h-14 w-14 object-contain" />
            <h1 className="text-xl font-bold leading-tight text-foreground">Anybackup</h1>
            <p className="mt-1 text-xs font-normal tracking-[0.22em] text-muted-foreground">{t("common.appTagline")}</p>
          </div>

          <div className="space-y-4">
            <div>
              <label className="mb-1.5 block text-xs font-medium text-foreground" htmlFor="username">
                {t("login.username")}
              </label>
              <input
                id="username"
                type="text"
                className={cn(fieldClass, showNameError ? "border-destructive/50" : "border-input")}
                placeholder={t("login.usernamePlaceholder")}
                value={name}
                onChange={(event) => {
                  setName(event.target.value)
                  setError("")
                  setFieldError(null)
                }}
              />
            </div>

            <div>
              <label className="mb-1.5 block text-xs font-medium text-foreground" htmlFor="password">
                {t("login.password")}
              </label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  className={cn(fieldClass, "pr-10", showPasswordError ? "border-destructive/50" : "border-input")}
                  placeholder={t("login.passwordPlaceholder")}
                  value={password}
                  onChange={(event) => {
                    setPassword(event.target.value)
                    setError("")
                    setFieldError(null)
                  }}
                />
                <button
                  type="button"
                  aria-label={showPassword ? t("login.hidePassword") : t("login.showPassword")}
                  className="transition-fast absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                  onClick={() => setShowPassword((value) => !value)}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {error ? (
              <motion.div
                initial={{ opacity: 0, y: -4 }}
                animate={{ opacity: 1, y: 0 }}
                className="flex items-center gap-1.5 text-xs text-destructive"
              >
                <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                {error}
              </motion.div>
            ) : null}

            <Button type="submit" variant="ai" size="lg" className="mt-2 w-full gap-2" disabled={isLoading}>
              {isLoading ? (
                <span className="h-4 w-4 animate-spin rounded-full border-2 border-primary-foreground/30 border-t-primary-foreground" />
              ) : (
                <ArrowRight className="h-4 w-4" />
              )}
              {isLoading ? t("login.submitting") : t("login.submit")}
            </Button>
          </div>
        </form>
      </motion.div>
    </div>
  )
}
