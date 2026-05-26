import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  base: '/quote/',
  server: {
    port: 5173,
    proxy: {
      '/quote/api': {
        target: 'http://127.0.0.1:5001',
        rewrite: (path) => path.replace(/^\/quote/, '')
      },
      '/quote/uploads': {
        target: 'http://127.0.0.1:5001',
        rewrite: (path) => path.replace(/^\/quote/, '')
      },
    },
  },
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'index.html'),
        univer: resolve(__dirname, 'univer.html'),
      },
    },
  },
  resolve: {
    dedupe: ['react', 'react-dom', '@wendellhu/redi', 'rxjs'],
  },
  optimizeDeps: {
    include: [
      'react',
      'react-dom',
      'rxjs',
      '@wendellhu/redi',
    ],
  },
})
