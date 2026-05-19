import { defineConfig } from "vitest/config"
import { loadEnv } from "vite"
import react from "@vitejs/plugin-react"
import path from "path"
import { fileURLToPath } from "url"
import { viteBaseFromBasePath } from "./src/config/base-path"

const currentDir = path.dirname(fileURLToPath(import.meta.url))

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), "")
  const authServiceProxyTarget = env.VITE_AUTH_SERVICE_PROXY_TARGET?.trim()
  const conversationServiceProxyTarget = env.VITE_CONVERSATION_SERVICE_PROXY_TARGET?.trim()

  const proxy: Record<string, { target: string; changeOrigin: boolean; secure: boolean }> = {}

  if (authServiceProxyTarget) {
    proxy["/api/auth_service"] = {
      target: authServiceProxyTarget,
      changeOrigin: true,
      secure: false,
    }
  }

  if (conversationServiceProxyTarget) {
    proxy["/api/conversation_service"] = {
      target: conversationServiceProxyTarget,
      changeOrigin: true,
      secure: false,
    }
  }

  return {
    base: viteBaseFromBasePath(env.VITE_APP_BASE_PATH),
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(currentDir, "./src"),
      },
    },
    build: {
      modulePreload: false,
      rollupOptions: {
        output: {
          manualChunks(id) {
            if (id.includes("/src/i18n/messages/zh-CN")) return "locale-zh-CN"
            if (id.includes("/src/i18n/messages/en")) return "locale-en"
            if (!id.includes("node_modules")) return undefined
            if (id.includes("@ag-ui")) return "vendor-agui"
            if (id.includes("react-markdown") || id.includes("remark") || id.includes("micromark")) {
              return "vendor-markdown"
            }
            if (id.includes("framer-motion")) return "vendor-motion"
            if (id.includes("react-router")) return "vendor-router"
            if (id.includes("react-dom")) return "vendor-react-dom"
            if (id.includes("/react/") || id.includes("scheduler/")) return "vendor-react"
            if (id.includes("zustand")) return "vendor-zustand"
            if (id.includes("lucide-react")) return "vendor-icons"
            return undefined
          },
        },
      },
    },
    server: Object.keys(proxy).length > 0 ? { proxy } : undefined,
    test: {
      environment: "jsdom",
      setupFiles: ["./src/test/rtl-wrapper-mock.ts", "./src/test/setup.ts"],
    },
  }
})
