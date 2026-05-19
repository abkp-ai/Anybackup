import React, { Suspense } from "react"
import ReactDOM from "react-dom/client"
import { RouterProvider } from "react-router-dom"
import { AppProviders } from "@/app/AppProviders"
import { PageBootFallback } from "@/app/PageBootFallback"
import { router } from "@/app/router"
import { emitDebugLog } from "@/lib/debug-log"
import "./index.css"

emitDebugLog({
  location: "main.tsx:entry",
  message: "main bundle executed",
  data: { href: window.location.href, path: window.location.pathname },
  hypothesisId: "H3",
})

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <AppProviders>
      <Suspense fallback={<PageBootFallback />}>
        <RouterProvider router={router} />
      </Suspense>
    </AppProviders>
  </React.StrictMode>,
)
