/**
 * Playwright E2E 配置（阶段03 §3.5 断网恢复）
 *
 * webServer 自动拉起真实前后端测试环境：
 * - 后端: uvicorn @127.0.0.1:8002，启用 QA_TEST_HOOKS=1（测试钩子端点）
 * - 前端: Vite dev server @localhost:3001（代理 /api/ 到 8002）
 *
 * 注意：若复用已在运行的后端（reuseExistingServer），该后端必须以
 * QA_TEST_HOOKS=1 启动，否则测试会以明确错误提示失败。
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
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure'
  },
  webServer: [
    {
      command: 'venv\\Scripts\\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8002',
      cwd: '../backend',
      url: 'http://127.0.0.1:8002/api/v1/health',
      reuseExistingServer: true,
      timeout: 120000,
      env: {
        QA_TEST_HOOKS: '1'
      }
    },
    {
      command: 'npm run dev',
      url: 'http://localhost:3001',
      reuseExistingServer: true,
      timeout: 120000,
      env: {
        BROWSER: 'none'
      }
    }
  ]
})
