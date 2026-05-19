import fs from "node:fs"
import path from "node:path"

const root = path.resolve(import.meta.dirname, "..")
const src = fs.readFileSync(path.join(root, "src/i18n/messages.ts"), "utf8")

const enMarker = "  en: {"
const zhMarker = '  "zh-CN": {'
const assignMarker = 'Object.assign(messages["zh-CN"]'
const recordMarker = "} as Record<Locale, MessageBundle>"

const enStart = src.indexOf(enMarker)
const zhStart = src.indexOf(zhMarker)
const assignStart = src.indexOf(assignMarker)
const recordEnd = src.indexOf(recordMarker)

const headerEnd = src.indexOf("export const messages = {")
let header = src.slice(0, headerEnd)
header = header.replace("type MessageBundle", "export type MessageBundle")
header = header.replace("const DEFAULT_LOCALE", "export const DEFAULT_LOCALE")

const enBody = src.slice(enStart + enMarker.length, zhStart).trim().replace(/,\s*$/, "")
let zhBody = src
  .slice(zhStart + zhMarker.length, assignStart > -1 ? assignStart : recordEnd)
  .trim()
  .replace(/,\s*$/, "")

if (assignStart > -1) {
  const assignOpen = src.indexOf("{", assignStart)
  const assignClose = src.indexOf("})", assignOpen)
  const assignBody = src.slice(assignOpen + 1, assignClose).trim().replace(/,\s*$/, "")
  zhBody = `${zhBody},\n${assignBody}`
}

const outDir = path.join(root, "src/i18n/messages")
fs.mkdirSync(outDir, { recursive: true })
fs.writeFileSync(path.join(outDir, "types.ts"), header)
fs.writeFileSync(
  path.join(outDir, "en.ts"),
  `import type { MessageBundle } from "./types"\n\nexport const enMessages: MessageBundle = {\n${enBody}\n}\n`,
)
fs.writeFileSync(
  path.join(outDir, "zh-CN.ts"),
  `import type { MessageBundle } from "./types"\n\nexport const zhCnMessages: MessageBundle = {\n${zhBody}\n}\n`,
)
console.log("split ok", { enLines: enBody.split("\n").length, zhLines: zhBody.split("\n").length })
