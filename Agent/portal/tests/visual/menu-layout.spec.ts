import fs from "node:fs/promises"
import path from "node:path"
import { test } from "@playwright/test"
import pixelmatch from "pixelmatch"
import { PNG } from "pngjs"

const ARTIFACT_DIR = path.join(process.cwd(), "test-results", "menu-layout")
const PROTOTYPE_URL = process.env.PROTOTYPE_URL ?? "http://127.0.0.1:4174"

const AUTH_KEY = "agent_web_auth_session"
const GUIDE_KEY_PREFIX = "agent_web_guide_state"

const maxDiffRatio = Number(process.env.VISUAL_MENU_MAX_DIFF_RATIO ?? "0.003")

type PngLike = {
  width: number
  height: number
  data: Buffer
}

function cropToSize(input: PngLike, width: number, height: number): PNG {
  const output = new PNG({ width, height })
  for (let y = 0; y < height; y += 1) {
    const srcStart = y * input.width * 4
    const srcEnd = srcStart + width * 4
    const dstStart = y * width * 4
    input.data.copy(output.data, dstStart, srcStart, srcEnd)
  }
  return output
}

test("menu layout diff against prototype demo", async ({ page, browser }) => {
  await fs.mkdir(ARTIFACT_DIR, { recursive: true })

  const now = Date.now()
  const expiresAt = now + 60 * 60 * 1000
  const idleExpiresAt = now + 30 * 60 * 1000

  // Bypass local auth guard for visual comparison only.
  await page.context().addInitScript(
    ({ authKey, guideKeyPrefix, authValue, guideValue }) => {
      window.localStorage.setItem(authKey, JSON.stringify(authValue))
      window.localStorage.setItem(`${guideKeyPrefix}:default:u1`, JSON.stringify(guideValue))
    },
    {
      authKey: AUTH_KEY,
      guideKeyPrefix: GUIDE_KEY_PREFIX,
      authValue: {
        accessToken: "visual-token",
        expiresAt,
        idleExpiresAt,
        user: {
          id: "u1",
          username: "visual.user",
          displayName: "Visual User",
          role: "backup_admin",
          tenantId: "default",
        },
      },
      guideValue: { completed: true },
    },
  )

  await page.goto("/", { waitUntil: "networkidle" })
  const appSidebar = page.locator("#root > div > aside").first()
  await appSidebar.waitFor({ state: "visible", timeout: 15_000 })

  const prototypeContext = await browser.newContext({
    viewport: { width: 1440, height: 900 },
  })
  const prototypePage = await prototypeContext.newPage()
  await prototypePage.goto(PROTOTYPE_URL, { waitUntil: "networkidle" })
  let prototypeSidebar = prototypePage.locator("#root > div > aside").first()
  if ((await prototypeSidebar.count()) === 0) {
    const skipGuide = prototypePage.locator("button.absolute.bottom-8").first()
    if ((await skipGuide.count()) > 0) {
      await skipGuide.click()
      await prototypePage.waitForLoadState("networkidle")
      await prototypePage.waitForTimeout(1000)
    }
    prototypeSidebar = prototypePage.locator("#root > div > aside").first()
  }
  await prototypeSidebar.waitFor({ state: "visible", timeout: 20_000 })

  const appBuffer = await appSidebar.screenshot({
    animations: "disabled",
    caret: "hide",
  })
  const prototypeBuffer = await prototypeSidebar.screenshot({
    animations: "disabled",
    caret: "hide",
  })

  await prototypeContext.close()

  const appPng = PNG.sync.read(appBuffer)
  const prototypePng = PNG.sync.read(prototypeBuffer)

  const compareWidth = Math.min(appPng.width, prototypePng.width)
  const compareHeight = Math.min(appPng.height, prototypePng.height)

  const appComparable = cropToSize(appPng, compareWidth, compareHeight)
  const prototypeComparable = cropToSize(prototypePng, compareWidth, compareHeight)
  const diffPng = new PNG({ width: compareWidth, height: compareHeight })

  const diffPixels = pixelmatch(
    prototypeComparable.data,
    appComparable.data,
    diffPng.data,
    compareWidth,
    compareHeight,
    { threshold: 0.1 },
  )

  const totalPixels = compareWidth * compareHeight
  const diffRatio = diffPixels / totalPixels

  const appPath = path.join(ARTIFACT_DIR, "current-app-sidebar.png")
  const prototypePath = path.join(ARTIFACT_DIR, "baseline-prototype-sidebar.png")
  const diffPath = path.join(ARTIFACT_DIR, "diff-sidebar.png")
  const reportPath = path.join(ARTIFACT_DIR, "report.json")

  await Promise.all([
    fs.writeFile(appPath, appBuffer),
    fs.writeFile(prototypePath, prototypeBuffer),
    fs.writeFile(diffPath, PNG.sync.write(diffPng)),
    fs.writeFile(
      reportPath,
      JSON.stringify(
        {
          compareWidth,
          compareHeight,
          appSize: { width: appPng.width, height: appPng.height },
          prototypeSize: { width: prototypePng.width, height: prototypePng.height },
          diffPixels,
          totalPixels,
          diffRatio,
          maxDiffRatio,
        },
        null,
        2,
      ),
    ),
  ])

  if (diffRatio > maxDiffRatio) {
    throw new Error(
      `Menu layout diff ratio ${diffRatio.toFixed(6)} exceeded threshold ${maxDiffRatio.toFixed(6)}. ` +
        `See ${diffPath} and ${reportPath}.`,
    )
  }
})
