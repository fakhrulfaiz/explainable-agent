import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    host: true,
    port: 5173,
    allowedHosts: ['.ngrok-free.dev', '.ngrok.io'], // Add this line
    watch: {
      usePolling: true,
      interval: 100,
    },
    hmr: {
      host: process.env.VITE_HMR_HOST || 'localhost',
      clientPort: process.env.VITE_HMR_CLIENT_PORT ? Number(process.env.VITE_HMR_CLIENT_PORT) : 80,
      protocol: 'ws',
    },
  },
})