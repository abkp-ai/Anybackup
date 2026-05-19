import fs from "node:fs/promises"
import path from "node:path"
import { test, type Page } from "@playwright/test"
import pixelmatch from "pixelmatch"
import { PNG } from "pngjs"

const ARTIFACT_DIR = path.join(process.cwd(), "test-results", "chat-layout-tree")
const BASELINE_DIR = path.join(process.cwd(), "tests", "visual", "baselines")
const updateBaseline = process.env.VISUAL_CHAT_DEMO_UPDATE_BASELINE === "1"
const maxDiffRatio = Number(process.env.VISUAL_CHAT_DEMO_MAX_DIFF_RATIO ?? "0.001")

const AUTH_KEY = "agent_web_auth_session"
const GUIDE_KEY_PREFIX = "agent_web_guide_state"
const LOCALE_KEY = "agent.portal.locale"

type VisualState = "layout-tree-candidate-compare-default"

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

function statePaths(state: VisualState) {
  return {
    baselineSourcePath: path.join(BASELINE_DIR, `${state}.png`),
    baselineArtifactPath: path.join(ARTIFACT_DIR, `baseline-${state}.png`),
    currentPath: path.join(ARTIFACT_DIR, `current-${state}.png`),
    diffPath: path.join(ARTIFACT_DIR, `diff-${state}.png`),
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
      localeValue: "en",
      guideValue: { completed: true },
      authValue: {
        accessToken: "visual-token",
        expiresAt,
        idleExpiresAt,
        user: {
          id: "visual-user",
          username: "visual.admin",
          displayName: "Visual Administrator",
          role: "backup_admin",
          tenantId: "default",
        },
      },
    },
  )
}

async function openState(page: Page, state: VisualState) {
  await seedVisualAuth(page)
  await page.goto("/chat-demo", { waitUntil: "networkidle" })

  const targetSelector =
    state === "layout-tree-candidate-compare-default"
      ? "[data-testid='chat-demo-layout-tree-renderer']"
      : "[data-testid='chat-demo-layout-tree-renderer']"

  await page.locator(targetSelector).waitFor({ state: "visible", timeout: 15_000 })
  const target = page.locator(targetSelector).first()

  return target.screenshot({
    animations: "disabled",
    caret: "hide",
  })
}

async function writeBaselineArtifacts(state: VisualState, currentBuffer: Buffer) {
  const { baselineSourcePath, baselineArtifactPath, currentPath, diffPath, reportPath } = statePaths(state)

  await fs.mkdir(BASELINE_DIR, { recursive: true })
  await fs.mkdir(ARTIFACT_DIR, { recursive: true })

  const currentPng = PNG.sync.read(currentBuffer)
  const blankDiff = new PNG({ width: currentPng.width, height: currentPng.height })

  await Promise.all([
    fs.writeFile(baselineSourcePath, currentBuffer),
    fs.writeFile(baselineArtifactPath, currentBuffer),
    fs.writeFile(currentPath, currentBuffer),
    fs.writeFile(diffPath, PNG.sync.write(blankDiff)),
    fs.writeFile(
      reportPath,
      JSON.stringify(
        {
          state,
          mode: "baseline-updated",
          compareWidth: currentPng.width,
          compareHeight: currentPng.height,
          appSize: { width: currentPng.width, height: currentPng.height },
          baselineSize: { width: currentPng.width, height: currentPng.height },
          diffPixels: 0,
          totalPixels: currentPng.width * currentPng.height,
          diffRatio: 0,
          maxDiffRatio,
        },
        null,
        2,
      ),
    ),
  ])
}

async function assertStateAgainstBaseline(state: VisualState, currentBuffer: Buffer) {
  const { baselineSourcePath, baselineArtifactPath, currentPath, diffPath, reportPath } = statePaths(state)
  const baselineBuffer = await fs.readFile(baselineSourcePath).catch(() => null)

  if (!baselineBuffer) {
    throw new Error(`Missing visual baseline for state "${state}". Run "npm run visual:chat-demo:update" first.`)
  }

  await fs.mkdir(ARTIFACT_DIR, { recursive: true })

  const currentPng = PNG.sync.read(currentBuffer)
  const baselinePng = PNG.sync.read(baselineBuffer)
  const compareWidth = Math.min(currentPng.width, baselinePng.width)
  const compareHeight = Math.min(currentPng.height, baselinePng.height)

  const currentComparable = cropToSize(currentPng, compareWidth, compareHeight)
  const baselineComparable = cropToSize(baselinePng, compareWidth, compareHeight)
  const diffPng = new PNG({ width: compareWidth, height: compareHeight })

  const diffPixels = pixelmatch(
    baselineComparable.data,
    currentComparable.data,
    diffPng.data,
    compareWidth,
    compareHeight,
    { threshold: 0.1 },
  )

  const totalPixels = compareWidth * compareHeight
  const diffRatio = diffPixels / totalPixels

  await Promise.all([
    fs.writeFile(baselineArtifactPath, baselineBuffer),
    fs.writeFile(currentPath, currentBuffer),
    fs.writeFile(diffPath, PNG.sync.write(diffPng)),
    fs.writeFile(
      reportPath,
      JSON.stringify(
        {
          state,
          compareWidth,
          compareHeight,
          appSize: { width: currentPng.width, height: currentPng.height },
          baselineSize: { width: baselinePng.width, height: baselinePng.height },
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
      `Visual state "${state}" diff ratio ${diffRatio.toFixed(6)} exceeded threshold ${maxDiffRatio.toFixed(6)}. ` +
        `See ${diffPath} and ${reportPath}.`,
    )
  }
}

for (const state of ["layout-tree-candidate-compare-default"] as const) {
  test(`${state} matches approved baseline`, async ({ page }) => {
    const currentBuffer = await openState(page, state)
    if (updateBaseline) {
      await writeBaselineArtifacts(state, currentBuffer)
      return
    }
    await assertStateAgainstBaseline(state, currentBuffer)
  })
}
