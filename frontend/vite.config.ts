import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

const api = process.env.ATLAS_API ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { '/api': api } },
  preview: { port: 4173, proxy: { '/api': api } },
})
