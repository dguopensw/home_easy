import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  assetsInclude: ['**/*.wasm', '**/*.data', '**/*.loader.js', '**/*.framework.js'],
  server: {
    allowedHosts: [
      'bobble-antibody-facebook.ngrok-free.dev'
    ],
    headers: {
      "Cross-Origin-Embedder-Policy": "require-corp",
      "Cross-Origin-Opener-Policy": "same-origin",
    },
    fs: {
      strict: false
    },
  },
  
  publicDir: 'public',

  optimizeDeps: {
    exclude: ['unity/Build'] 
  },
  build: {
  // 빌드 시 assets 폴더로 복사될 때 파일명이 바뀌지 않도록 설정
  rollupOptions: {
    external: [/unity\/.*/],
  }
}
})
