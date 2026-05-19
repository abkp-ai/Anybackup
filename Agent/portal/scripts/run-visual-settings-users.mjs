import path from "node:path"
import { spawn } from "node:child_process"

const args = process.argv.slice(2)
const playwrightBin = path.join(
  process.cwd(),
  "node_modules",
  ".bin",
  process.platform === "win32" ? "playwright.cmd" : "playwright",
)

const playwrightArgs = ["test", "-c", "playwright.settings-users.config.ts"]

if (args.includes("--headed")) {
  playwrightArgs.push("--headed")
}

const runner = spawn(playwrightBin, playwrightArgs, {
  stdio: "inherit",
  env: {
    ...process.env,
    ...(args.includes("--update-baseline") ? { VISUAL_SETTINGS_USERS_UPDATE_BASELINE: "1" } : {}),
  },
})

runner.on("exit", (code) => {
  process.exit(code ?? 1)
})

runner.on("error", (error) => {
  console.error(error)
  process.exit(1)
})
