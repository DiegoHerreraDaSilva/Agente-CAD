import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Em dev, o Vite roda em :5173 e o FastAPI em :8000. Proxamos as rotas de API
// para o FastAPI para que cookies de sessão funcionem (mesma origem do ponto
// de vista do navegador) e para não precisar de CORS.
const BACKEND = 'http://localhost:8000'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/auth': BACKEND,
      '/chat': BACKEND,
      '/sessions': BACKEND,
      '/admin': BACKEND,
      '/knowledge': BACKEND,
      '/logo.png': BACKEND,
      '/health': BACKEND,
    },
  },
})
