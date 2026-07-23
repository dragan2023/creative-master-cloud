/**
 * 实时连接状态与重连退避工具
 *
 * 为生成域 SSE / 写作工作台 WebSocket 提供统一的连接状态枚举与
 * 带抖动的指数退避算法。此模块为纯函数实现，不依赖 Vue 或浏览器 API，
 * 便于单元测试与跨模块复用。
 *
 * @module utils/connectionState
 */

/**
 * 连接生命周期状态枚举
 * idle         尚未建立连接
 * connecting   正在建立首个连接
 * connected    连接已建立且正常
 * reconnecting 连接中断，正在按退避策略重连
 * closed       连接被主动关闭（终态/离开路由/取消）
 * error        连接因不可恢复错误终止
 */
export const ConnectionState = Object.freeze({
  IDLE: 'idle',
  CONNECTING: 'connecting',
  CONNECTED: 'connected',
  RECONNECTING: 'reconnecting',
  CLOSED: 'closed',
  ERROR: 'error'
})

/** 退避算法默认参数 */
const DEFAULT_BACKOFF_BASE_MS = 1000
const DEFAULT_BACKOFF_MAX_MS = 30000
const DEFAULT_BACKOFF_JITTER_RATIO = 0.2

/**
 * 计算第 N 次重连的等待时长（带抖动的指数退避）。
 *
 * 退避公式：min(base * 2^attempt, max)，再叠加 ±jitterRatio 的随机抖动，
 * 避免多个客户端同时重连造成雪崩。
 *
 * @param {number} attempt 已重连次数（从 0 开始）
 * @param {Object} [options]
 * @param {number} [options.baseMs=1000] 基础延迟
 * @param {number} [options.maxMs=30000] 最大延迟上限
 * @param {number} [options.jitterRatio=0.2] 抖动比例（0 表示无抖动，测试可用）
 * @param {() => number} [options.random=Math.random] 随机源（便于测试注入）
 * @returns {number} 本次重连应等待的毫秒数（向下取整，且不为负）
 */
export function nextBackoffDelay(attempt, options = {}) {
  const baseMs = options.baseMs ?? DEFAULT_BACKOFF_BASE_MS
  const maxMs = options.maxMs ?? DEFAULT_BACKOFF_MAX_MS
  const jitterRatio = options.jitterRatio ?? DEFAULT_BACKOFF_JITTER_RATIO
  const random = options.random ?? Math.random

  const safeAttempt = Math.max(0, Math.floor(attempt))
  const exponential = Math.min(baseMs * Math.pow(2, safeAttempt), maxMs)

  if (jitterRatio <= 0) {
    return Math.max(0, Math.floor(exponential))
  }

  // 抖动范围：[-jitterRatio, +jitterRatio]
  const jitter = exponential * jitterRatio * (random() * 2 - 1)
  const delay = Math.min(exponential + jitter, maxMs)
  return Math.max(0, Math.floor(delay))
}

/** 可发起重连的状态集合 */
const RECONNECTABLE_STATES = new Set([
  ConnectionState.CONNECTED,
  ConnectionState.CONNECTING,
  ConnectionState.RECONNECTING
])

/**
 * 判断当前是否应继续重连。
 *
 * @param {Object} params
 * @param {string} params.state 当前连接状态
 * @param {number} params.attempts 已重连次数
 * @param {number} params.maxAttempts 最大重连次数
 * @param {boolean} [params.isTaskRunning=true] 关联任务是否仍在运行
 * @returns {boolean}
 */
export function shouldReconnect({ state, attempts, maxAttempts, isTaskRunning = true }) {
  if (!isTaskRunning) return false
  if (state === ConnectionState.CLOSED || state === ConnectionState.ERROR) return false
  if (!RECONNECTABLE_STATES.has(state)) return false
  return attempts < maxAttempts
}
