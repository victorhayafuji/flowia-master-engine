import path from 'path'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  envDir: '../../../',
  envPrefix: ['VITE_', 'SUPABASE_'],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    exclude: ['**/node_modules/**', '**/dist/**', 'e2e/**'],
    env: {
      VITE_API_URL: 'http://localhost:8000/api/v1',
      VITE_SUPABASE_URL: 'https://example.supabase.co',
      VITE_SUPABASE_KEY: 'test-anon-key',
    },
  },
})
