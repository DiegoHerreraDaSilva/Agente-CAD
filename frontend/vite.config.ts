import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

// Em dev, o Vite roda em :5173 e o FastAPI em :8001. Proxamos as rotas de API
// para o FastAPI para que cookies de sessão funcionem (mesma origem do ponto
// de vista do navegador) e para não precisar de CORS. :8001 (não :8000) por
// decisão do time — ajuste local pra evitar conflito com outro serviço.
const BACKEND = 'http://localhost:8001'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/auth': BACKEND,
      '/chat': BACKEND,
      '/sessions': BACKEND,
      '/snippets': BACKEND,
      '/admin': BACKEND,
      '/knowledge': BACKEND,
      '/logo.png': BACKEND,
      '/logo-light.png': BACKEND,
      '/health': BACKEND,
    },
  },
})
