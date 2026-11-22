import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/health": "http://127.0.0.1:8000",
      "/topics": "http://127.0.0.1:8000",
      "/lesson": "http://127.0.0.1:8000",
      "/prompt": "http://127.0.0.1:8000",
      "/export": "http://127.0.0.1:8000",
      "/handwriting": "http://127.0.0.1:8000"
    }
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: false
  }
});
