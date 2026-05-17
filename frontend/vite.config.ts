import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    host: true,
    proxy: {
      '/api': {
        target: 'http://localhost:8002',
        changeOrigin: true,
        configure: (proxy) => {
          proxy.on('proxyRes', (proxyRes) => {
            if (proxyRes.headers.location) {
              proxyRes.headers.location = proxyRes.headers.location.replace(
                'http://localhost:8002', 'http://localhost:3000'
              )
            }
          })
        }
      },
      '/data': {
        target: 'http://127.0.0.1:8001',
        changeOrigin: true
      }
    }
  }
})
