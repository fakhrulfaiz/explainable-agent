import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(() => {
  const hmrHost = process.env.VITE_HMR_HOST || 'localhost'
  const hmrClientPort = process.env.VITE_HMR_CLIENT_PORT
    ? Number(process.env.VITE_HMR_CLIENT_PORT)
    : 80

  return {
    plugins: [react()],
    server: {
      host: true,
      port: 5173,
      watch: {
        usePolling: true,
        interval: 100,
      },
      hmr: {
        host: hmrHost,
        clientPort: hmrClientPort,
        protocol: 'ws',
      },
    },
  }
})
