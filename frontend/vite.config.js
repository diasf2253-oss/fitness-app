import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Proxy /api calls to the FastAPI backend during development.
// In production, you'd configure your reverse proxy (nginx, etc.) instead.
export default defineConfig({
  plugins: [react()],
  server: {
    // PORT lets a harness (e.g. Claude Code's preview) assign a free port
    port: Number(process.env.PORT) || 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
