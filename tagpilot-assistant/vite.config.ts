import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  base: "/agent-ui/",
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: 5174,
    strictPort: true,
    origin: "http://127.0.0.1:5174",
    proxy: {
      "/dev-api": {
        target: "http://127.0.0.1:8080",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/dev-api/, ""),
      },
    },
  },
  preview: {
    port: 5174,
    strictPort: true,
  },
  test: {
    environment: "node",
  },
});
