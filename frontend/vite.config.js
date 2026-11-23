import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// During development the browser calls /api/... on the Vite server (port 5173),
// and Vite forwards it to the FastAPI backend. No CORS problems, no hard-coded URLs.
const backend = process.env.VITE_BACKEND_URL || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: { '/api': { target: backend, changeOrigin: true } },
  },
  test: {
    environment: 'jsdom',
    setupFiles: './tests/setup.js',
    globals: true,
  },
})
