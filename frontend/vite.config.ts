import { defineConfig } from "vite";

const ORCHESTRATOR_INTERNAL = process.env.ORCHESTRATOR_INTERNAL_URL ?? "http://orchestrator-service:8001";

export default defineConfig({
  server: {
    port: 5173,
    proxy: {
      "/orchestrate":   { target: ORCHESTRATOR_INTERNAL, changeOrigin: true },
      "/approve":       { target: ORCHESTRATOR_INTERNAL, changeOrigin: true },
      "/tool":          { target: ORCHESTRATOR_INTERNAL, changeOrigin: true },
      "/settings":      { target: ORCHESTRATOR_INTERNAL, changeOrigin: true },
      "/auth":          { target: ORCHESTRATOR_INTERNAL, changeOrigin: true },
      "/health":        { target: ORCHESTRATOR_INTERNAL, changeOrigin: true },
    },
  },
});
