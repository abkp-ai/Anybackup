import "@testing-library/jest-dom/vitest"
import { cleanup } from "@testing-library/react"
import { afterEach, beforeAll, beforeEach } from "vitest"
import { ensureLocaleLoaded, getStoredLocale, LANGUAGE_STORAGE_KEY } from "@/i18n/messages"

beforeAll(async () => {
  await ensureLocaleLoaded(getStoredLocale())
})

/** Tests often call `localStorage.clear()`; keep locale keyed for stable EN assertions. */
const storageClear = Storage.prototype.clear
Storage.prototype.clear = function clearWithLocaleReset(this: Storage) {
  storageClear.call(this)
  this.setItem(LANGUAGE_STORAGE_KEY, "en")
}

beforeEach(() => {
  window.localStorage.setItem(LANGUAGE_STORAGE_KEY, "en")
})

afterEach(() => {
  cleanup()
})
