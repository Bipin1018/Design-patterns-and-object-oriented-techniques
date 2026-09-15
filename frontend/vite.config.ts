import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// docker-compose sets VITE_DOCKER. In a container the dev server has to listen
// on all interfaces, and file changes on a Windows bind mount are only noticed
// if the watcher polls for them.
const inDocker = process.env.VITE_DOCKER === '1'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    strictPort: true,
    host: inDocker ? '0.0.0.0' : 'localhost',
    watch: inDocker ? { usePolling: true, interval: 300 } : undefined,
  },
})