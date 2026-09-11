import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
    watch: {
      // Atomic writers (editor save handlers, agent file tools) write to a sibling
      // `<file>.<pid>.<uuid>.tmpdir/` directory and delete it immediately after the rename.
      // chokidar would try to watch that path and hit EBUSY, which surfaces as an unhandled
      // FSWatcher 'error' and kills `npm run dev` on Windows. Never watch those directories,
      // and never watch build output or VCS metadata.
      ignored: [
        '**/.git/**',
        '**/node_modules/**',
        '**/dist/**',
        '**/.*.tmpdir/**',
        '**/*.tmp',
        '**/*.crswap',
      ],
    },
  },
})
