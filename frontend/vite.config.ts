import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 3030,
    proxy: {
      '/api': 'http://localhost:8030',
      '/ws': { target: 'http://localhost:8030', ws: true },
    },
  },
})
