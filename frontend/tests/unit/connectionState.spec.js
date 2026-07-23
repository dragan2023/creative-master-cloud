/**
 * 单元测试：连接状态枚举与退避重连策略
 */
import { describe, it, expect } from 'vitest'
import {
  ConnectionState,
  nextBackoffDelay,
  shouldReconnect
} from '@/utils/connectionState'

describe('nextBackoffDelay 指数退避', () => {
  it('无抖动时按 base*2^attempt 增长', () => {
    const opts = { baseMs: 1000, maxMs: 30000, jitterRatio: 0 }
    expect(nextBackoffDelay(0, opts)).toBe(1000)
    expect(nextBackoffDelay(1, opts)).toBe(2000)
    expect(nextBackoffDelay(2, opts)).toBe(4000)
    expect(nextBackoffDelay(3, opts)).toBe(8000)
  })

  it('不超过最大上限', () => {
    const opts = { baseMs: 1000, maxMs: 5000, jitterRatio: 0 }
    expect(nextBackoffDelay(10, opts)).toBe(5000)
  })

  it('带抖动时结果落在合理区间内且非负', () => {
    const opts = { baseMs: 1000, maxMs: 30000, jitterRatio: 0.2, random: () => 1 }
    const d = nextBackoffDelay(2, opts) // exp=4000, jitter=+800
    expect(d).toBeGreaterThanOrEqual(0)
    expect(d).toBeLessThanOrEqual(30000)
  })
})

describe('shouldReconnect', () => {
  it('任务未运行时不重连', () => {
    expect(shouldReconnect({
      state: ConnectionState.CONNECTED, attempts: 0, maxAttempts: 5, isTaskRunning: false
    })).toBe(false)
  })

  it('已关闭或错误终态不重连', () => {
    expect(shouldReconnect({ state: ConnectionState.CLOSED, attempts: 0, maxAttempts: 5 })).toBe(false)
    expect(shouldReconnect({ state: ConnectionState.ERROR, attempts: 0, maxAttempts: 5 })).toBe(false)
  })

  it('达到最大次数后停止重连', () => {
    expect(shouldReconnect({ state: ConnectionState.RECONNECTING, attempts: 5, maxAttempts: 5 })).toBe(false)
    expect(shouldReconnect({ state: ConnectionState.RECONNECTING, attempts: 4, maxAttempts: 5 })).toBe(true)
  })
})
