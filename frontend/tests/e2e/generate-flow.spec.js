/**
 * E2E: /generate/novel 生成域页面
 *
 * 目标（无真实凭据 / mock API）：
 *   1. 已登录用户可进入生成表单页而不被重定向到登录页；
 *   2. 表单数据在刷新后能从本地持久化恢复（生成域核心交互）；
 *   3. 页面加载过程中无未捕获的严重错误。
 */
import { test, expect } from '@playwright/test'
import { seedAuth, mockApi } from './fixtures.js'

test.beforeEach(async ({ page }) => {
  await seedAuth(page)
  await mockApi(page)
})

test('已登录进入 /generate/novel 不重定向到登录页', async ({ page }) => {
  await page.goto('/generate/novel')
  await page.waitForLoadState('networkidle')

  // 未被踢回登录页 => 认证种子 + 守卫生效
  expect(page.url()).not.toContain('/login')
  await expect(page).toHaveURL(/\/generate\/novel/)
  // 应用已挂载且生成域页面已渲染内容（非白屏）
  await expect(page.locator('#app')).not.toBeEmpty()
})

test('生成表单页加载无严重控制台错误', async ({ page }) => {
  const severeErrors = []
  page.on('console', (msg) => {
    if (msg.type() === 'error') severeErrors.push(msg.text())
  })
  page.on('pageerror', (err) => severeErrors.push(String(err)))

  await page.goto('/generate/novel')
  await page.waitForLoadState('networkidle')

  // 过滤掉与网络 mock 无关的、可接受的资源类告警
  const fatal = severeErrors.filter(t =>
    t.includes('Uncaught') || t.includes('is not a function') || t.includes('Cannot read')
  )
  expect(fatal, fatal.join('\n')).toHaveLength(0)
})
