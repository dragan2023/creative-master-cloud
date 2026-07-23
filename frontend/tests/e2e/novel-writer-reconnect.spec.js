/**
 * E2E: /novel-writer/:id 写作工作台断线重连
 *
 * 目标（无真实凭据 / mock API）：
 *   1. 已登录用户可进入写作工作台，WebSocket 建连失败/断开不会导致页面崩溃；
 *   2. 断开实时连接后页面仍保持可用（重连策略生效、无未捕获异常）。
 *
 * 说明：为在无真实后端环境稳定运行，这里让 WebSocket 连接被拒绝，
 * 从而触发前端的断线/重连分支；验收关注"断线不崩溃、页面仍渲染"。
 */
import { test, expect } from '@playwright/test'
import { seedAuth, mockApi, mockProjectDetail } from './fixtures.js'

test.beforeEach(async ({ page }) => {
  await seedAuth(page)
  await mockApi(page, {
    'novel-writer/projects/123': mockProjectDetail,
    'projects/123': mockProjectDetail
  })

  // 拦截 WebSocket 握手：立即失败以触发断线/重连分支
  await page.routeWebSocket(/.*\/ws.*/, (ws) => {
    ws.close()
  }).catch(() => { /* 老版本无 routeWebSocket 时忽略 */ })
})

test('进入写作工作台且 WS 断开不导致页面崩溃', async ({ page }) => {
  const fatalErrors = []
  page.on('pageerror', (err) => fatalErrors.push(String(err)))

  await page.goto('/novel-writer/123')
  await page.waitForLoadState('networkidle')

  // 未被重定向到登录页
  expect(page.url()).not.toContain('/login')
  await expect(page).toHaveURL(/\/novel-writer\/123/)

  // 等待一段时间，让断线/重连逻辑运行
  await page.waitForTimeout(2000)

  // 页面根节点仍然渲染内容（未白屏崩溃）
  await expect(page.locator('#app')).not.toBeEmpty()
  expect(fatalErrors, fatalErrors.join('\n')).toHaveLength(0)
})
