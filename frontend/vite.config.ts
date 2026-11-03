import { defineConfig, loadEnv } from "vite";
import tailwindcss from "@tailwindcss/vite";
export default defineConfig(({ mode }) => ({
  plugins: [tailwindcss()],
  server: {
    proxy: {
      "/api":
        loadEnv(mode, ".", "").API_PROXY_TARGET || "http://127.0.0.1:8000",
    },
  },
  build: {
    rollupOptions: { output: { manualChunks: { charts: ["recharts"] } } },
  },
}));
