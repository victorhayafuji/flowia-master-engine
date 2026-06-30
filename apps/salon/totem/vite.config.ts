import { defineConfig } from "vite"
import react from "@vitejs/plugin-react"

// Standalone kiosk PWA — separate build/deploy from the admin dashboard so its
// service worker never caches the dashboard.
export default defineConfig({
  plugins: [react()],
  server: { port: 5174 },
})
