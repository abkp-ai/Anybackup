type DebugLogPayload = {
  location: string
  message: string
  data?: Record<string, unknown>
  hypothesisId: string
}

export function emitDebugLog(payload: DebugLogPayload): void {
  if (import.meta.env.MODE === "test") return

  // #region agent log
  globalThis
    .fetch?.("http://127.0.0.1:7644/ingest/8848a97e-f65f-45ef-a034-862d5acd2083", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Debug-Session-Id": "31f784" },
      body: JSON.stringify({
        sessionId: "31f784",
        ...payload,
        timestamp: Date.now(),
      }),
    })
    ?.catch?.(() => {})
  // #endregion
}
