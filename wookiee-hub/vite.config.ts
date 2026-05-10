import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"
import tailwindcss from "@tailwindcss/vite"
import path from "path"

export default defineConfig({
  plugins: [tailwindcss(), react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    proxy: {
      "/api": {
        target: "http://localhost:8002",
        changeOrigin: true,
      },
    },
  },
  build: {
    // Manual chunks to keep main bundle under ~700KB.
    // Heavy libraries get their own chunks so they cache independently across deploys.
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          query: ["@tanstack/react-query"],
          supabase: ["@supabase/supabase-js"],
          icons: ["lucide-react"],
        },
      },
    },
    chunkSizeWarningLimit: 700,
  },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/setupTests.ts"],
    globals: true,
  },
})
