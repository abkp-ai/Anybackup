import fs from "node:fs/promises"
import path from "node:path"
import { test, type Browser, type Locator, type Page } from "@playwright/test"
import pixelmatch from "pixelmatch"
import { PNG } from "pngjs"

const ARTIFACT_DIR = path.join(process.cwd(), "test-results", "sidebar-account-menu")
const PROTOTYPE_URL = process.env.PROTOTYPE_URL ?? "http://127.0.0.1:4174"
const APP_VISUAL_URL = "/__visual/app-sidebar"

const AUTH_KEY = "agent_web_auth_session"
const GUIDE_KEY_PREFIX = "agent_web_guide_state"
const LOCALE_KEY = "agent.portal.locale"

const VIEWPORT = { width: 1440, height: 900 }
const maxDiffRatio = Number(process.env.VISUAL_ACCOUNT_MAX_DIFF_RATIO ?? "0.001")

type AccountVisualState = "expanded-open" | "collapsed-open"

type GeometryMetrics = {
  sidebarRight: number
  panelLeft: number
  triggerRight: number
}

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

function statePaths(state: AccountVisualState) {
  return {
    appPath: path.join(ARTIFACT_DIR, `current-app-sidebar-account-menu-${state}.png`),
    prototypePath: path.join(ARTIFACT_DIR, `baseline-prototype-sidebar-account-menu-${state}.png`),
    diffPath: path.join(ARTIFACT_DIR, `diff-sidebar-account-menu-${state}.png`),
    reportPath: path.join(ARTIFACT_DIR, `report-${state}.json`),
  }
}

async function seedVisualAuth(page: Page) {
  const now = Date.now()
  const expiresAt = now + 60 * 60 * 1000
  const idleExpiresAt = now + 30 * 60 * 1000

  await page.context().addInitScript(
    ({ authKey, guideKeyPrefix, localeKey, authValue, guideValue, localeValue }) => {
      window.localStorage.setItem(authKey, JSON.stringify(authValue))
      window.localStorage.setItem(`${guideKeyPrefix}:default:visual-user`, JSON.stringify(guideValue))
      window.localStorage.setItem(localeKey, localeValue)
    },
    {
      authKey: AUTH_KEY,
      guideKeyPrefix: GUIDE_KEY_PREFIX,
      localeKey: LOCALE_KEY,
      localeValue: "zh-CN",
      guideValue: { completed: true },
      authValue: {
        accessToken: "visual-token",
        expiresAt,
        idleExpiresAt,
        user: {
          id: "visual-user",
          username: "Melon.zhao@aishu.cn",
          displayName: "赵理想",
          role: "backup_admin",
          tenantId: "default",
        },
      },
    },
  )

  await page.route("**/openid-connect/userinfo", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        sub: "visual-user",
        preferred_username: "Melon.zhao@aishu.cn",
        name: "赵理想",
        email: "Melon.zhao@aishu.cn",
        roles: ["backup_admin"],
      }),
    })
  })
}

async function openAppAccountMenu(page: Page, state: AccountVisualState) {
  await seedVisualAuth(page)
  await page.goto(APP_VISUAL_URL, { waitUntil: "networkidle" })

  const sidebar = page.getByTestId("visual-app-sidebar")
  await sidebar.waitFor({ state: "visible", timeout: 15_000 })

  if (state === "expanded-open") {
    await page.getByTestId("app-sidebar-expand-toggle").click()
    await page.waitForTimeout(250)
  }

  const trigger = page.getByTestId("sidebar-account-menu-button")
  await trigger.waitFor({ state: "visible", timeout: 10_000 })
  await trigger.click()

  const panel = page.getByTestId("sidebar-account-menu-panel")
  await panel.waitFor({ state: "visible", timeout: 10_000 })

  return { trigger, panel }
}

async function skipPrototypeGuideIfNeeded(page: Page) {
  const skipGuide = page.getByRole("button", { name: /跳过|skip/i }).first()
  if ((await skipGuide.count()) > 0 && (await skipGuide.first().isVisible().catch(() => false))) {
    await skipGuide.first().click()
    await page.waitForLoadState("networkidle")
    await page.waitForTimeout(500)
  }
}

async function openPrototypeAccountMenu(browser: Browser, state: AccountVisualState) {
  const prototypeContext = await browser.newContext({ viewport: VIEWPORT })
  const prototypePage = await prototypeContext.newPage()

  await prototypePage.goto(PROTOTYPE_URL, { waitUntil: "networkidle" })
  await skipPrototypeGuideIfNeeded(prototypePage)

  const sidebar = prototypePage.locator("#root > div > aside").first()
  await sidebar.waitFor({ state: "visible", timeout: 20_000 })

  if (state === "expanded-open") {
    const expandButton = sidebar.locator("button:has(svg.lucide-chevron-right)").first()
    await expandButton.click()
    await prototypePage.waitForTimeout(250)
  }

  const trigger = sidebar.locator("button:has(svg.lucide-user)").first()
  await trigger.waitFor({ state: "visible", timeout: 10_000 })
  await trigger.click()

  const panel = sidebar.locator("div.fixed").last()
  await panel.waitFor({ state: "visible", timeout: 10_000 })

  return { prototypeContext, prototypePage, trigger, panel }
}

async function screenshotClip(trigger: Locator, panel: Locator, state: AccountVisualState) {
  const triggerBox = await trigger.boundingBox()
  const panelBox = await panel.boundingBox()
  if (!triggerBox || !panelBox) {
    throw new Error(`Unable to resolve bounding box for state "${state}".`)
  }

  const directionTolerance = 2
  if (panelBox.x + directionTolerance < triggerBox.x + triggerBox.width) {
    throw new Error(
      `Sidebar account menu "${state}" is not opening to the right of its trigger. ` +
        `triggerRight=${(triggerBox.x + triggerBox.width).toFixed(1)}, panelLeft=${panelBox.x.toFixed(1)}.`,
    )
  }

  return panel.screenshot({
    animations: "disabled",
    caret: "hide",
  })
}

async function waitForPanelToSettle(panel: Locator, state: AccountVisualState) {
  await panel.evaluate(
    async (element, currentState) => {
      const isSettled = () => {
        const style = window.getComputedStyle(element)
        if (style.opacity !== "1") {
          return false
        }

        if (style.transform === "none") {
          return true
        }

        try {
          const matrix = new DOMMatrixReadOnly(style.transform)
          return Math.abs(matrix.a - 1) < 0.001 && Math.abs(matrix.d - 1) < 0.001
        } catch {
          return false
        }
      }

      if (isSettled()) {
        return
      }

      const deadline = performance.now() + 1_000
      await new Promise<void>((resolve, reject) => {
        const tick = () => {
          if (isSettled()) {
            resolve()
            return
          }

          if (performance.now() > deadline) {
            reject(new Error(`Sidebar account menu "${currentState}" animation did not settle in time.`))
            return
          }

          window.requestAnimationFrame(tick)
        }

        window.requestAnimationFrame(tick)
      })
    },
    state,
  )
}

async function readGeometry(trigger: Locator, panel: Locator, sidebar: Locator, state: AccountVisualState): Promise<GeometryMetrics> {
  const [triggerBox, panelBox, sidebarBox] = await Promise.all([
    trigger.boundingBox(),
    panel.boundingBox(),
    sidebar.boundingBox(),
  ])

  if (!triggerBox || !panelBox || !sidebarBox) {
    throw new Error(`Unable to resolve geometry for state "${state}".`)
  }

  return {
    sidebarRight: sidebarBox.x + sidebarBox.width,
    panelLeft: panelBox.x,
    triggerRight: triggerBox.x + triggerBox.width,
  }
}

async function runStateComparison(page: Page, browser: Browser, state: AccountVisualState) {
  await fs.mkdir(ARTIFACT_DIR, { recursive: true })

  const { trigger: appTrigger, panel: appPanel } = await openAppAccountMenu(page, state)
  await waitForPanelToSettle(appPanel, state)
  const appSidebar = page.getByTestId("visual-app-sidebar")
  const appGeometry = await readGeometry(appTrigger, appPanel, appSidebar, state)
  const appBuffer = await screenshotClip(appTrigger, appPanel, state)

  const { prototypeContext, prototypePage, trigger: prototypeTrigger, panel: prototypePanel } = await openPrototypeAccountMenu(browser, state)
  await waitForPanelToSettle(prototypePanel, state)
  const prototypeSidebar = prototypePage.locator("#root > div > aside").first()
  const prototypeGeometry = await readGeometry(prototypeTrigger, prototypePanel, prototypeSidebar, state)
  const prototypeBuffer = await screenshotClip(prototypeTrigger, prototypePanel, state)
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
  const appSidebarGap = appGeometry.panelLeft - appGeometry.sidebarRight
  const prototypeSidebarGap = prototypeGeometry.panelLeft - prototypeGeometry.sidebarRight
  const sidebarGapDelta = Math.abs(appSidebarGap - prototypeSidebarGap)
  const { appPath, prototypePath, diffPath, reportPath } = statePaths(state)

  await Promise.all([
    fs.writeFile(appPath, appBuffer),
    fs.writeFile(prototypePath, prototypeBuffer),
    fs.writeFile(diffPath, PNG.sync.write(diffPng)),
    fs.writeFile(
      reportPath,
      JSON.stringify(
        {
          state,
          compareWidth,
          compareHeight,
          appSize: { width: appPng.width, height: appPng.height },
          prototypeSize: { width: prototypePng.width, height: prototypePng.height },
          appGeometry: {
            sidebarRight: appGeometry.sidebarRight,
            panelLeft: appGeometry.panelLeft,
            triggerRight: appGeometry.triggerRight,
            sidebarGap: appSidebarGap,
          },
          prototypeGeometry: {
            sidebarRight: prototypeGeometry.sidebarRight,
            panelLeft: prototypeGeometry.panelLeft,
            triggerRight: prototypeGeometry.triggerRight,
            sidebarGap: prototypeSidebarGap,
          },
          sidebarGapDelta,
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
      `Sidebar account menu "${state}" diff ratio ${diffRatio.toFixed(6)} exceeded threshold ${maxDiffRatio.toFixed(6)}. ` +
        `See ${diffPath} and ${reportPath}.`,
    )
  }

  if (sidebarGapDelta > 1) {
    throw new Error(
      `Sidebar account menu "${state}" sidebar gap drifted by ${sidebarGapDelta.toFixed(3)}px. ` +
        `App gap=${appSidebarGap.toFixed(3)}px, prototype gap=${prototypeSidebarGap.toFixed(3)}px.`,
    )
  }
}

for (const state of ["expanded-open", "collapsed-open"] as const) {
  test(`sidebar account menu ${state} matches prototype`, async ({ page, browser }) => {
    await runStateComparison(page, browser, state)
  })
}
