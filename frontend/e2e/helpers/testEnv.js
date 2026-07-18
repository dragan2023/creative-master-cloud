/**
 * E2E 测试环境辅助（阶段03 §3.5）
 *
 * 职责：测试账号认证、测试项目创建、running任务准备、生产终态推送与清理。
 * 安全：token 仅存于测试进程内存并注入浏览器 localStorage，
 *       不打印到控制台、报告或截图（禁止事项 4.4）。
 */
import { request as playwrightRequest, expect } from '@playwright/test'

export const BACKEND_URL = process.env.E2E_BACKEND_URL || 'http://127.0.0.1:8002'

/** 专用E2E测试账号（仅存在于本地测试数据库） */
const E2E_TEST_USER = {
  username: 'qa_e2e_reconnect',
  email: 'qa-e2e-reconnect@example.com',
  password: 'qa-e2e-local-0001'
}

/**
 * 获取测试认证上下文：优先登录，账号不存在时自动注册
 * @returns {Promise<{api: import('@playwright/test').APIRequestContext, token: string, user: Object}>}
 */
export async function acquireTestAuth() {
  const api = await playwrightRequest.newContext({ baseURL: BACKEND_URL })

  const loginResponse = await api.post('/api/v1/auth/login', {
    data: { username: E2E_TEST_USER.username, password: E2E_TEST_USER.password }
  })
  if (loginResponse.ok()) {
    const body = await loginResponse.json()
    return { api, token: body.data.access_token, user: body.data.user }
  }

  const registerResponse = await api.post('/api/v1/auth/register', {
    data: E2E_TEST_USER
  })
  if (!registerResponse.ok()) {
    throw new Error(
      `E2E测试账号注册失败: HTTP ${registerResponse.status()} ${await registerResponse.text()}`
    )
  }
  const body = await registerResponse.json()
  return { api, token: body.data.access_token, user: body.data.user }
}

/** 构造带认证头的请求选项 */
function withAuth(token, data) {
  return {
    headers: { Authorization: `Bearer ${token}` },
    ...(data !== undefined ? { data } : {})
  }
}

/**
 * 创建E2E测试项目
 * @returns {Promise<number>} projectId
 */
export async function createTestProject(api, token) {
  const response = await api.post(
    '/api/v1/qa-test-hooks/projects',
    withAuth(token, {
      title: `E2E断网恢复-${Date.now()}`
    })
  )
  expect(response.ok(), '创建并登记QA专用项目应成功').toBeTruthy()
  const body = await response.json()
  return body.data.project_id
}

/**
 * 通过QA测试钩子创建running状态的写作任务（不启动Pipeline）
 * @returns {Promise<number>} taskId
 */
export async function seedRunningTask(api, token, projectId) {
  const response = await api.post(
    '/api/v1/qa-test-hooks/writing-tasks/seed-running',
    withAuth(token, { project_id: projectId, total_units: 5 })
  )
  if (response.status() === 404) {
    throw new Error(
      'QA测试钩子未挂载(404)：请以 QA_TEST_HOOKS=1 启动后端，' +
      '或关闭已占用8002端口的旧后端进程后重跑（Playwright会自动以正确环境拉起后端）'
    )
  }
  expect(response.ok(), '创建running测试任务应成功').toBeTruthy()
  const body = await response.json()
  return body.data.task_id
}

/**
 * 通过QA测试钩子把任务置为completed并广播生产Pipeline同款status_change
 * @returns {Promise<number>} 送达的连接数
 */
export async function emitProductionTerminalStatus(api, token, taskId) {
  const response = await api.post(
    `/api/v1/qa-test-hooks/writing-tasks/${taskId}/emit-complete`,
    withAuth(token, { total_word_count: 12000 })
  )
  expect(response.ok(), '触发生产status_change推送应成功').toBeTruthy()
  const body = await response.json()
  return body.data.delivered_connections
}

/** 清理本进程登记的QA任务及其测试项目；失败必须使E2E失败。 */
export async function cleanupQaTask(api, token, taskId) {
  const response = await api.delete(
    `/api/v1/qa-test-hooks/writing-tasks/${taskId}`,
    withAuth(token)
  )
  expect(response.ok(), 'QA任务与项目清理应成功').toBeTruthy()
  const body = await response.json()
  expect(body.success, 'QA清理响应success应为true').toBe(true)
  return body.data
}
