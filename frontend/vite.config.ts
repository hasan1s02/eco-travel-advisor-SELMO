import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// The Rasa REST channel is proxied in development so the browser never makes a
// cross-origin request, which keeps the CORS surface of the deployed bot at
// zero. In Docker, VITE_RASA_URL points straight at the rasa service instead.
export default defineConfig({
  plugins: [react()],
  server: {
    host: "0.0.0.0",
    port: 3000,
    proxy: {
      "/rasa": {
        target: process.env.RASA_URL ?? "http://localhost:5005",
        changeOrigin: true,
        rewrite: (p) => p.replace(/^\/rasa/, ""),
      },
    },
  },
  build: { outDir: "dist", sourcemap: true },
});
