/**
 * 单元测试：API 错误处理策略
 *
 * 对应验收标准：
 *   - 连续多次 401 只跳转登录一次；
 *   - 相同请求的相同错误在时间窗口内只展示一次。
 */
import { describe, it, expect } from 'vitest'
import {
  createMessageDeduper,
  buildErrorKey,
  resolveErrorAction
} from '@/api/errorPolicy'

/** 构造一个模拟 Axios 错误 */
function makeError({ status, method = 'get', url = '/api/x', detail } = {}) {
  return {
    response: status !== undefined ? { status, data: { detail } } : undefined,
    config: { method, url }
  }
}

describe('errorPolicy - 401 登录跳转去重', () => {
  it('首个 401 应跳转登录', () => {
    const deduper = createMessageDeduper()
    const action = resolveErrorAction(makeError({ status: 401 }), {
      currentPath: '/generate',
      deduper,
      isRedirectingToLogin: false
    })
    expect(action.kind).toBe('unauthorized')
    expect(action.shouldRedirectLogin).toBe(true)
    expect(action.shouldShowMessage).toBe(false)
  })

  it('已在跳转途中时第二个 401 不再跳转', () => {
    const deduper = createMessageDeduper()
    const action = resolveErrorAction(makeError({ status: 401 }), {
      currentPath: '/generate',
      deduper,
      isRedirectingToLogin: true
    })
    expect(action.shouldRedirectLogin).toBe(false)
  })

  it('位于登录页时 401 不触发跳转', () => {
    const deduper = createMessageDeduper()
    const action = resolveErrorAction(makeError({ status: 401 }), {
      currentPath: '/login',
      deduper,
      isRedirectingToLogin: false
    })
    expect(action.shouldRedirectLogin).toBe(false)
  })
})

describe('errorPolicy - 相同错误去重', () => {
  it('时间窗口内相同请求的相同错误只展示一次', () => {
    const deduper = createMessageDeduper(2000)
    const err = makeError({ status: 500, method: 'post', url: '/api/gen', detail: '服务器错误' })

    const first = resolveErrorAction(err, { currentPath: '/generate', deduper, now: 1000 })
    const second = resolveErrorAction(err, { currentPath: '/generate', deduper, now: 1500 })

    expect(first.shouldShowMessage).toBe(true)
    expect(second.shouldShowMessage).toBe(false)
    expect(first.message).toBe('服务器错误')
  })

  it('超出时间窗口后可再次展示', () => {
    const deduper = createMessageDeduper(2000)
    const err = makeError({ status: 500, method: 'post', url: '/api/gen', detail: '服务器错误' })

    const first = resolveErrorAction(err, { currentPath: '/generate', deduper, now: 1000 })
    const later = resolveErrorAction(err, { currentPath: '/generate', deduper, now: 4000 })

    expect(first.shouldShowMessage).toBe(true)
    expect(later.shouldShowMessage).toBe(true)
  })

  it('499(取消)应静默不展示', () => {
    const deduper = createMessageDeduper()
    const action = resolveErrorAction(makeError({ status: 499 }), {
      currentPath: '/generate',
      deduper
    })
    expect(action.kind).toBe('cancelled')
    expect(action.shouldShowMessage).toBe(false)
  })

  it('buildErrorKey 对同一请求同一消息生成稳定 key', () => {
    const err = makeError({ status: 500, method: 'POST', url: '/api/gen' })
    expect(buildErrorKey(err, 'x')).toBe(buildErrorKey(err, 'x'))
  })
})
