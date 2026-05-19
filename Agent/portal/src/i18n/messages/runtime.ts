import type { Locale, MessageBundle, MessageKey } from "./types"
import { getStoredLocale } from "./types"

const bundles: Partial<Record<Locale, MessageBundle>> = {}

export function isLocaleLoaded(locale: Locale): boolean {
  return Boolean(bundles[locale])
}

export async function ensureLocaleLoaded(locale: Locale): Promise<MessageBundle> {
  const cached = bundles[locale]
  if (cached) return cached

  if (locale === "zh-CN") {
    const { zhCnMessages } = await import("./zh-CN")
    bundles["zh-CN"] = zhCnMessages
    return zhCnMessages
  }

  const { enMessages } = await import("./en")
  bundles.en = enMessages
  return enMessages
}

export function translate(key: MessageKey, locale: Locale = getStoredLocale()): string {
  const bundle = bundles[locale] ?? bundles.en
  return bundle?.[key] ?? bundles.en?.[key] ?? key
}
