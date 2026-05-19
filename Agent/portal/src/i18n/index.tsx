import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from "react"
import { PageBootFallback } from "@/app/PageBootFallback"
import { emitDebugLog } from "@/lib/debug-log"
import {
  ensureLocaleLoaded,
  getStoredLocale,
  isLocaleLoaded,
  LANGUAGE_STORAGE_KEY,
  translate,
  type Locale,
  type MessageKey,
} from "@/i18n/messages"

export const LANGUAGE_SWITCH_ENABLED = false

interface I18nContextValue {
  locale: Locale
  setLocale: (locale: Locale) => void
  t: (key: MessageKey) => string
}

const I18nContext = createContext<I18nContextValue | null>(null)

export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(() => getStoredLocale())
  const [ready, setReady] = useState(() => isLocaleLoaded(getStoredLocale()))
  const [bundleVersion, setBundleVersion] = useState(0)

  useEffect(() => {
    let cancelled = false
    const startedAt = Date.now()
    emitDebugLog({
      location: "I18nProvider.tsx:loadLocale:start",
      message: "loading locale bundle",
      data: { locale },
      hypothesisId: "H6",
    })

    void ensureLocaleLoaded(locale).then(() => {
      if (cancelled) return
      emitDebugLog({
        location: "I18nProvider.tsx:loadLocale:end",
        message: "locale bundle loaded",
        data: { locale, durationMs: Date.now() - startedAt },
        hypothesisId: "H6",
      })
      setReady(true)
      setBundleVersion((value) => value + 1)
    })

    return () => {
      cancelled = true
    }
  }, [locale])

  const setLocale = (nextLocale: Locale) => {
    setLocaleState(nextLocale)
    window.localStorage.setItem(LANGUAGE_STORAGE_KEY, nextLocale)
    setReady(false)
  }

  const contextValue = useMemo<I18nContextValue>(() => {
    void bundleVersion
    return {
      locale,
      setLocale,
      t: (key) => translate(key, locale),
    }
  }, [locale, bundleVersion])

  if (!ready) return <PageBootFallback />

  return <I18nContext.Provider value={contextValue}>{children}</I18nContext.Provider>
}

export function useI18n() {
  const context = useContext(I18nContext)
  if (!context) throw new Error("useI18n must be used within I18nProvider")
  return context
}
