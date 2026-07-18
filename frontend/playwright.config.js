/**
 * Playwright E2E 配置（阶段03 §3.5 断网恢复）
 *
 * 前后端进程由 scripts/run-e2e.mjs 显式拥有、探活并在 finally 中回收；
 * 本配置不使用 Playwright webServer，避免 Windows 子进程树回收挂起。
 */
import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 240000,
  fullyParallel: false,
  workers: 1,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: 'http://localhost:3001',
    trace: 'off',
    screenshot: 'only-on-failure'
  }
})
