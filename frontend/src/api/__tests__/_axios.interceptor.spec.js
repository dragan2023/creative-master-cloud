/**
 * Axios 响应拦截器错误提示所有权集成测试
 *
 * 通过替换 axios adapter 模拟真实 HTTP 往返（不 mock 拦截器本身），
 * 验证一次接口失败最多产生一次用户提示的所有权规则：
 * 1. 默认 500 → 全局提示恰好一次
 * 2. silent: true → 拦截器提示零次
 * 3. 页面自定义处理（silent + 页面 catch 提示）→ 合计提示一次
 * 4. 取消请求（AbortController / CanceledError）→ 提示零次
 * 5. 401 → 认证流程接管（清理 + 跳转登录页），不叠加普通错误提示
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import axios from 'axios'

const elMessageErrorMock = vi.hoisted(() => vi.fn())
const routerPushMock = vi.hoisted(() => vi.fn())
const clearAuthMock = vi.hoisted(() => vi.fn())

vi.mock('element-plus', () => ({
  ElMessage: { error: elMessageErrorMock }
}))

vi.mock('@/router', () => ({
  default: {
    currentRoute: { value: { path: '/novel-writer' } },
    push: routerPushMock
  }
}))

vi.mock('@/utils/authStorage', () => ({
  getToken: () => null,
  clearAuth: clearAuthMock
}))

import { ElMessage } from 'element-plus'
import { api } from '../_axios'

/**
 * 构造以指定 HTTP 状态码失败的 adapter
 * @param {number} status - HTTP 状态码
 * @param {string} detail - 后端 detail 字段
 * @returns {Function} axios adapter
 */
function failWithStatus(status, detail) {
  return (config) => {
    const response = { status, statusText: 'ERROR', data: { detail }, headers: {}, config }
    return Promise.reject(new axios.AxiosError(
      `Request failed with status code ${status}`,
      axios.AxiosError.ERR_BAD_RESPONSE,
      config,
      null,
      response
    ))
  }
}

/** 构造模拟客户端本地取消（AbortController）的 adapter */
function failWithCancellation() {
  return () => Promise.reject(new axios.CanceledError('canceled'))
}

beforeEach(() => {
  elMessageErrorMock.mockClear()
  routerPushMock.mockClear()
  clearAuthMock.mockClear()
})

describe('_axios 响应拦截器错误提示所有权', () => {
  it('should_notify_exactly_once_for_default_500_error', async () => {
    api.defaults.adapter = failWithStatus(500, '服务器内部错误')

    await expect(api.get('/api/v1/demo')).rejects.toBeTruthy()

    expect(elMessageErrorMock).toHaveBeenCalledTimes(1)
    expect(elMessageErrorMock).toHaveBeenCalledWith('服务器内部错误')
  })

  it('should_not_notify_when_request_declares_silent_true', async () => {
    api.defaults.adapter = failWithStatus(500, '服务器内部错误')

    await expect(api.get('/api/v1/demo', { silent: true })).rejects.toBeTruthy()

    expect(elMessageErrorMock).not.toHaveBeenCalled()
  })

  it('should_show_single_notification_when_page_owns_error_display', async () => {
    api.defaults.adapter = failWithStatus(500, '服务器内部错误')

    // 模拟页面所有权：silent 请求 + 页面 catch 内唯一一次自定义提示
    try {
      await api.get('/api/v1/demo', { silent: true })
      expect.unreachable('请求应当失败')
    } catch (error) {
      expect(error.normalized.notify).toBe(false)
      ElMessage.error('加载项目列表失败，请检查网络后重试')
    }

    expect(elMessageErrorMock).toHaveBeenCalledTimes(1)
    expect(elMessageErrorMock).toHaveBeenCalledWith('加载项目列表失败，请检查网络后重试')
  })

  it('should_stay_silent_for_cancelled_request', async () => {
    api.defaults.adapter = failWithCancellation()

    await expect(api.get('/api/v1/demo')).rejects.toMatchObject({ cancelled: true })

    expect(elMessageErrorMock).not.toHaveBeenCalled()
  })

  it('should_stay_silent_for_server_side_499_cancellation', async () => {
    api.defaults.adapter = failWithStatus(499, '客户端断开连接')

    await expect(api.get('/api/v1/demo')).rejects.toMatchObject({ cancelled: true })

    expect(elMessageErrorMock).not.toHaveBeenCalled()
  })

  it('should_delegate_401_to_auth_flow_without_extra_error_toast', async () => {
    api.defaults.adapter = failWithStatus(401, '未授权')

    await expect(api.get('/api/v1/demo')).rejects.toBeTruthy()

    expect(elMessageErrorMock).not.toHaveBeenCalled()
    expect(clearAuthMock).toHaveBeenCalledTimes(1)
    expect(routerPushMock).toHaveBeenCalledWith({
      path: '/login',
      query: { redirect: '/novel-writer' }
    })
  })
})
