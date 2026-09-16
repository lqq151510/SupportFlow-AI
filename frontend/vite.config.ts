// 运行环境为 Node，但本仓库未安装 @types/node；此声明与运行时语义一致，
// 仅覆盖本文件用到的 env 读取。
declare const process: { env: Record<string, string | undefined>; cwd(): string }

import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// 前后端同域：开发期把 /api 代理到后端（cookie 会话与 CSRF 双提交因此同源）。
// 目标地址可用 VITE_API_TARGET 覆盖（默认 http://localhost:8080，与 docker-compose 一致）。
const API_TARGET = process.env.VITE_API_TARGET || 'http://localhost:8080'

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      // 与 tsconfig.app.json 的 paths 对齐；Rollup 不读 tsconfig，需要在此显式声明。
      '@': process.cwd() + '/src',
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: API_TARGET,
        changeOrigin: true,
      },
      '/healthz': {
        target: API_TARGET,
        changeOrigin: true,
      },
    },
  },
})
