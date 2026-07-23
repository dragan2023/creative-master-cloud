import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright 端到端测试配置
 *
 * 设计目标：可在"无真实凭据 / 无真实后端"的环境运行。
 *   - 所有 /api 请求在浏览器层被 page.route 拦截并返回 mock 数据，
 *     不会触达 vite 代理，也不会调用真实模型或密钥；
 *   - 通过 addInitScript 在应用启动前注入 token + userInfo，绕过登录。
 *
 * 开发服务器由本配置自动拉起（vite dev, 端口 3001）。
 */
const PORT = 3001
const BASE_URL = `http://localhost:${PORT}`

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 30_000,
  expect: { timeout: 8_000 },
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: 0,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: BASE_URL,
    trace: 'on-first-retry',
    // 保证浏览器在无头环境稳定
    headless: true
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] }
    }
  ],
  webServer: {
    command: 'npm run dev',
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000
  }
})
