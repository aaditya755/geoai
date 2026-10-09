import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/chat': 'http://localhost:8000',
      '/export': 'http://localhost:8000',
      '/health': 'http://localhost:8000',
      '/attribution': 'http://localhost:8000',
    },
  },
})
