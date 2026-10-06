import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

const backend = "http://127.0.0.1:8765";

export default defineConfig({
  plugins: [react()],
  build: { outDir: "../webapp/static", emptyOutDir: true, sourcemap: false },
  server: {
    host: "127.0.0.1",
    port: 5173,
    strictPort: true,
    proxy: {
      "/api": {
        target: backend,
        changeOrigin: true,
        configure(proxy) {
          proxy.on("proxyReq", (proxyReq, req) => {
            // Only the fixed development frontend can be translated to the backend origin.
            if (req.headers.origin === "http://127.0.0.1:5173")
              proxyReq.setHeader("origin", backend);
          });
        },
      },
    },
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}"],
    restoreMocks: true,
  },
});
