/**
 * 长任务断网恢复 E2E（阶段03 §3.5）
 *
 * 验收路径：真实路由 /novel-writer/:id（渲染 WritingWorkbench.vue）
 * 实时链路：stores/writingTask WebSocket（唯一主连接）
 *
 * 覆盖断言：
 * 1. 进入工作台后建立恰好一条 WebSocket 主连接，UI 显示"实时连接"
 * 2. 离线15秒：UI 明确显示离线；期间零新连接（无请求风暴）
 * 3. 恢复在线：只新建一条主连接并回到"实时连接"
 * 4. 终态（真实Pipeline同款status_change）：内容校准恰好一次、连接关闭、
 *    5秒观察期内不再重连
 * 5. 离开工作台后30秒内没有该任务的新连接或轮询
 *
 * 证据记录：WebSocket连接数、任务状态请求数、内容刷新数（URL已剥离认证参数）
 */
import { test, expect } from '@playwright/test'
import {
  acquireTestAuth,
  createTestProject,
  seedRunningTask,
  emitProductionTerminalStatus,
  cleanupQaTask
} from './helpers/testEnv'

/** 离线观察时长（计划要求15秒） */
const OFFLINE_OBSERVE_MS = 15000
/** 终态后连接静默观察时长 */
const TERMINAL_QUIET_MS = 5000
/** 离开工作台后的静默观察时长（计划要求30秒） */
const LEAVE_QUIET_MS = 30000

let auth = null
let projectId = null
let taskId = null

test.beforeAll(async () => {
  auth = await acquireTestAuth()
  projectId = await createTestProject(auth.api, auth.token)
  taskId = await seedRunningTask(auth.api, auth.token, projectId)
})

test.afterAll(async () => {
  try {
    if (auth?.api && taskId) {
      const cleaned = await cleanupQaTask(auth.api, auth.token, taskId)
      expect(cleaned.task_id).toBe(taskId)
      expect(cleaned.project_id).toBe(projectId)
    }
  } finally {
    await auth?.api?.dispose()
  }
})

test('长任务断网15秒恢复后单连接续传，终态只刷新一次', async ({ page, context }) => {
  // ==================== 证据计数器（URL剥离认证参数防泄露） ====================
  const wsConnections = []
  const wsClosures = []
  page.on('websocket', (ws) => {
    const sanitizedUrl = ws.url().split('?')[0]
    if (sanitizedUrl.includes(`/writing-tasks/${taskId}/ws`)) {
      wsConnections.push({ url: sanitizedUrl, at: Date.now() })
      ws.on('close', () => wsClosures.push({ url: sanitizedUrl, at: Date.now() }))
    }
  })

  const taskStatusRequests = []
  const unitsRefreshRequests = []
  const sseConnections = []
  page.on('request', (request) => {
    const sanitizedUrl = request.url().split('?')[0]
    if (sanitizedUrl.includes('/task-events') || request.resourceType() === 'eventsource') {
      sseConnections.push({ url: sanitizedUrl, at: Date.now() })
    } else if (sanitizedUrl.includes(`/writing-tasks/${taskId}/units`)) {
      unitsRefreshRequests.push({ url: sanitizedUrl, at: Date.now() })
    } else if (sanitizedUrl.includes('/writing-tasks')) {
      taskStatusRequests.push({ url: sanitizedUrl, at: Date.now() })
    }
  })

  // ==================== 认证注入（token仅入localStorage，不落日志） ====================
  await page.addInitScript(
    ([token, userJson]) => {
      localStorage.setItem('token', token)
      localStorage.setItem('userInfo', userJson)
    },
    [auth.token, JSON.stringify(auth.user)]
  )

  // ==================== 1. 进入真实工作台并建立主连接 ====================
  await page.goto(`/novel-writer/${projectId}`)
  await expect(page.locator('.writing-workbench')).toBeVisible({ timeout: 30000 })

  const connectionState = page.locator('.connection-state')
  await expect(connectionState).toContainText('实时连接', { timeout: 30000 })
  expect(wsConnections.length, '初始应恰好建立一条WS主连接').toBe(1)

  // ==================== 2. 离线15秒：显示离线且零新连接 ====================
  const wsCountBeforeOffline = wsConnections.length
  await context.setOffline(true)
  await expect(connectionState).toContainText('离线', { timeout: 10000 })

  await page.waitForTimeout(OFFLINE_OBSERVE_MS)
  expect(
    wsConnections.length,
    '离线期间不得创建新连接（无请求风暴）'
  ).toBe(wsCountBeforeOffline)

  // ==================== 3. 恢复在线：只新建一条主连接 ====================
  await context.setOffline(false)
  await expect(connectionState).toContainText('实时连接', { timeout: 20000 })
  expect(
    wsConnections.length,
    '恢复在线后只应新建一条主实时连接'
  ).toBe(wsCountBeforeOffline + 1)

  // 给重连后的连接短暂稳定期，确认无额外连接抖动
  await page.waitForTimeout(2000)
  expect(wsConnections.length).toBe(wsCountBeforeOffline + 1)

  // ==================== 4. 终态：真实Pipeline同款status_change ====================
  const unitsCountBeforeComplete = unitsRefreshRequests.length
  const closuresBeforeTerminal = wsClosures.length
  const deliveredConnections = await emitProductionTerminalStatus(auth.api, auth.token, taskId)
  expect(deliveredConnections, '生产status_change应送达至少1条连接').toBeGreaterThanOrEqual(1)

  // 连接关闭（终态由store主动断开）
  await expect(connectionState).toContainText('连接已关闭', { timeout: 15000 })
  await expect.poll(() => wsClosures.length, {
    message: '生产status_change分支应由Store关闭当前WebSocket',
    timeout: 10000
  }).toBe(closuresBeforeTerminal + 1)

  // 内容自动校准恰好一次
  await expect
    .poll(() => unitsRefreshRequests.length, {
      message: '终态后应触发一次内容校准(fetchUnits)',
      timeout: 10000
    })
    .toBe(unitsCountBeforeComplete + 1)

  // 5秒观察期：不再重连、不再重复校准
  const wsCountAtTerminal = wsConnections.length
  await page.waitForTimeout(TERMINAL_QUIET_MS)
  expect(wsConnections.length, '终态后5秒观察期内不得重连').toBe(wsCountAtTerminal)
  expect(
    unitsRefreshRequests.length,
    '终态内容校准只允许一次'
  ).toBe(unitsCountBeforeComplete + 1)

  // ==================== 5. 离开工作台：30秒内无该任务新连接/轮询 ====================
  const wsCountBeforeLeave = wsConnections.length
  const taskRequestCountBeforeLeave = taskStatusRequests.length
  const unitsCountBeforeLeave = unitsRefreshRequests.length

  await page.goto('/novel-writer')
  await page.waitForTimeout(LEAVE_QUIET_MS)

  expect(wsConnections.length, '离开工作台后不得出现该任务新WS连接').toBe(wsCountBeforeLeave)
  expect(
    unitsRefreshRequests.length,
    '离开工作台后不得出现该任务内容请求'
  ).toBe(unitsCountBeforeLeave)
  const newTaskRequests = taskStatusRequests
    .slice(taskRequestCountBeforeLeave)
    .filter((entry) => entry.url.includes(`/writing-tasks/${taskId}`))
  expect(newTaskRequests, '离开工作台后不得出现该任务状态轮询').toHaveLength(0)
  expect(sseConnections, '写作工作台不得为同一任务并行启动SSE主连接').toHaveLength(0)

  // ==================== 证据输出（已脱敏，无token） ====================
  console.log(
    '[E2E证据] WS连接数=%d, WS关闭数=%d, SSE连接数=%d, 任务状态请求数=%d, 内容刷新数=%d',
    wsConnections.length,
    wsClosures.length,
    sseConnections.length,
    taskStatusRequests.length,
    unitsRefreshRequests.length
  )
  console.log('[E2E证据] WS连接时间线:', JSON.stringify(wsConnections))
})
