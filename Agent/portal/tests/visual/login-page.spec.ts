import fs from "node:fs/promises"
import path from "node:path"
import { expect, test, type Page } from "@playwright/test"
import pixelmatch from "pixelmatch"
import { PNG } from "pngjs"

const ARTIFACT_DIR = path.join(process.cwd(), "test-results", "login-page")
const BASELINE_DIR = path.join(process.cwd(), "tests", "visual", "baselines")
const maxDiffRatio = Number(process.env.VISUAL_LOGIN_MAX_DIFF_RATIO ?? "0.003")
const updateBaseline = process.env.VISUAL_LOGIN_UPDATE_BASELINE === "1"

type LoginVisualState = "default" | "focus" | "error" | "loading"

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

function statePaths(state: LoginVisualState) {
  return {
    baselineSourcePath: path.join(BASELINE_DIR, `login-page-${state}.png`),
    baselineArtifactPath: path.join(ARTIFACT_DIR, `baseline-login-page-${state}.png`),
    currentPath: path.join(ARTIFACT_DIR, `current-login-page-${state}.png`),
    diffPath: path.join(ARTIFACT_DIR, `diff-login-page-${state}.png`),
    reportPath: path.join(ARTIFACT_DIR, `report-${state}.json`),
  }
}

async function openLoginPage(page: Page) {
  await page.goto("/login", { waitUntil: "networkidle" })
  await page.locator("form").waitFor({ state: "visible", timeout: 15_000 })
}

async function captureDefaultState(page: Page) {
  return page.screenshot({
    animations: "disabled",
    caret: "hide",
  })
}

async function captureFocusState(page: Page) {
  await page.getByLabel("Username").focus()
  return page.screenshot({
    animations: "disabled",
    caret: "hide",
  })
}

async function captureErrorState(page: Page) {
  await page.getByRole("button", { name: "Sign in" }).click()
  await expect(page.getByText("Please enter username")).toBeVisible()
  return page.screenshot({
    animations: "disabled",
    caret: "hide",
  })
}

async function captureLoadingState(page: Page) {
  let releaseTokenRequest: (() => void) | null = null

  await page.route("**/openid-connect/token", async (route) => {
    await new Promise<void>((resolve) => {
      releaseTokenRequest = resolve
    })

    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        access_token: "visual-token",
        expires_in: 3600,
        refresh_token: "visual-refresh-token",
        token_type: "Bearer",
        scope: "openid",
      }),
    })
  })

  await page.route("**/openid-connect/userinfo", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        sub: "visual-user",
        preferred_username: "visual.user",
        name: "Visual User",
        roles: ["backup_admin"],
      }),
    })
  })

  await page.locator("#username").fill("visual.user")
  await page.locator("#password").fill("visual-password")
  await page.getByRole("button", { name: "Sign in" }).click()
  await expect(page.getByRole("button", { name: "Signing in" })).toBeDisabled()

  const screenshot = await page.screenshot({
    animations: "disabled",
    caret: "hide",
  })

  releaseTokenRequest?.()
  return screenshot
}

async function captureState(page: Page, state: LoginVisualState) {
  if (state === "default") return captureDefaultState(page)
  if (state === "focus") return captureFocusState(page)
  if (state === "error") return captureErrorState(page)
  return captureLoadingState(page)
}

async function writeBaselineArtifacts(state: LoginVisualState, currentBuffer: Buffer) {
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

async function assertStateAgainstBaseline(state: LoginVisualState, currentBuffer: Buffer) {
  const { baselineSourcePath, baselineArtifactPath, currentPath, diffPath, reportPath } = statePaths(state)
  const baselineBuffer = await fs.readFile(baselineSourcePath).catch(() => null)

  if (!baselineBuffer) {
    throw new Error(
      `Missing login visual baseline for state "${state}". ` +
        `Run "npm run visual:login:update" to approve a baseline first.`,
    )
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
      `Login page state "${state}" diff ratio ${diffRatio.toFixed(6)} exceeded threshold ${maxDiffRatio.toFixed(6)}. ` +
        `See ${diffPath} and ${reportPath}.`,
    )
  }
}

async function runStateCheck(page: Page, state: LoginVisualState) {
  await openLoginPage(page)
  const currentBuffer = await captureState(page, state)

  if (updateBaseline) {
    await writeBaselineArtifacts(state, currentBuffer)
    return
  }

  await assertStateAgainstBaseline(state, currentBuffer)
}

for (const state of ["default", "focus", "error", "loading"] as const) {
  test(`login page ${state} state matches approved baseline`, async ({ page }) => {
    await runStateCheck(page, state)
  })
}
