/**
 * 写作任务 WebSocket URL 安全日志测试。
 *
 * WebSocket 认证当前通过查询参数传递，因此控制台只能记录剥离查询参数后的 URL，
 * 禁止把短期或长期认证凭据写入日志、Playwright 报告与测试附件。
 */
import { beforeEach, describe, expect, it, vi } from 'vitest'

const getWsAuthQueryMock = vi.hoisted(() => vi.fn())

vi.mock('@/api', () => ({ default: {} }))
vi.mock('@/config', () => ({ API_BASE_URL: '' }))
vi.mock('@/utils/authStorage', () => ({ getWsAuthQuery: getWsAuthQueryMock }))

import { connectWritingTaskWS } from '../writing-task'

describe('connectWritingTaskWS 安全日志', () => {
  beforeEach(() => {
    getWsAuthQueryMock.mockReturnValue('token=super-secret-e2e-token')
    class FakeWebSocket {
      constructor(url) {
        this.url = url
      }
    }
    vi.stubGlobal('WebSocket', FakeWebSocket)
    vi.spyOn(console, 'log').mockImplementation(() => {})
  })

  it('不把认证查询参数输出到控制台', () => {
    connectWritingTaskWS(42)

    const loggedText = console.log.mock.calls.flat().join(' ')
    expect(loggedText).not.toContain('super-secret-e2e-token')
    expect(loggedText).not.toContain('token=')
    expect(loggedText).toContain('/api/v1/writing-tasks/42/ws')
  })
})
