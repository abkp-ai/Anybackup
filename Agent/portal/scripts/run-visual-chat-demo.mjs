import path from "node:path"
import { spawn } from "node:child_process"

const args = process.argv.slice(2)
const playwrightBin = path.join(
  process.cwd(),
  "node_modules",
  ".bin",
  process.platform === "win32" ? "playwright.cmd" : "playwright",
)

const playwrightArgs = ["test", "-c", "playwright.chat-demo.config.ts"]

if (args.includes("--update-baseline")) {
  process.env.VISUAL_CHAT_DEMO_UPDATE_BASELINE = "1"
}

if (args.includes("--headed")) {
  playwrightArgs.push("--headed")
}

const runner = spawn(playwrightBin, playwrightArgs, {
  stdio: "inherit",
  env: process.env,
})

runner.on("exit", (code) => {
  process.exit(code ?? 1)
})

runner.on("error", (error) => {
  console.error(error)
  process.exit(1)
})
