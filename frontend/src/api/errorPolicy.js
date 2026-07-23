/**
 * API 错误处理策略（纯函数）
 *
 * 将 Axios 响应拦截器中的"是否跳转登录/是否展示消息/如何去重"决策
 * 从副作用中剥离为纯函数，便于单元测试并保证以下不变量：
 *   1. 连续多次 401 只触发一次登录跳转；
 *   2. 相同请求的相同错误在时间窗口内只展示一次通知。
 *
 * @module api/errorPolicy
 */

/** 通知去重默认时间窗口（毫秒） */
const DEFAULT_DEDUP_WINDOW_MS = 2000

/**
 * 创建一个基于 key 的消息去重器。
 *
 * @param {number} [windowMs=2000] 去重时间窗口
 * @returns {{ shouldShow: (key: string, now?: number) => boolean, reset: () => void }}
 */
export function createMessageDeduper(windowMs = DEFAULT_DEDUP_WINDOW_MS) {
  const lastShownAt = new Map()

  function shouldShow(key, now = Date.now()) {
    const prev = lastShownAt.get(key)
    if (prev !== undefined && now - prev < windowMs) {
      return false
    }
    lastShownAt.set(key, now)
    // 顺带清理过期条目，避免无限增长
    for (const [k, ts] of lastShownAt) {
      if (now - ts >= windowMs) lastShownAt.delete(k)
    }
    return true
  }

  function reset() {
    lastShownAt.clear()
  }

  return { shouldShow, reset }
}

/**
 * 从错误对象构造去重 key（状态 + 请求方法 + 路径 + 消息）。
 * @param {Object} error Axios 错误对象
 * @param {string} message 已解析的错误消息
 * @returns {string}
 */
export function buildErrorKey(error, message) {
  const status = error?.response?.status ?? 'network'
  const method = (error?.config?.method || 'get').toLowerCase()
  const url = error?.config?.url || 'unknown'
  return `${status}:${method}:${url}:${message}`
}

/**
 * 解析响应错误，返回结构化的处理动作，由调用方执行副作用。
 *
 * @param {Object} error Axios 错误对象
 * @param {Object} ctx 上下文
 * @param {string} ctx.currentPath 当前路由 path
 * @param {{ shouldShow: Function }} ctx.deduper 消息去重器
 * @param {boolean} [ctx.isRedirectingToLogin=false] 是否已在跳转登录途中
 * @param {number} [ctx.now] 当前时间戳（便于测试）
 * @returns {{ kind: string, message: (string|null), shouldShowMessage: boolean, shouldRedirectLogin: boolean }}
 *   kind: 'unauthorized' | 'cancelled' | 'validation' | 'error'
 */
export function resolveErrorAction(error, ctx) {
  const {
    currentPath,
    deduper,
    isRedirectingToLogin = false,
    now = Date.now()
  } = ctx || {}

  const status = error?.response?.status
  const rawMessage = error?.response?.data?.detail
  const message = normalizeMessage(rawMessage)

  // 401 未授权：仅当不在登录/注册页且未处于跳转途中时跳转，且只跳转一次
  if (status === 401) {
    const onAuthPage = currentPath === '/login' || currentPath === '/register'
    const shouldRedirectLogin = !onAuthPage && !isRedirectingToLogin
    return {
      kind: 'unauthorized',
      message: null,
      shouldShowMessage: false,
      shouldRedirectLogin
    }
  }

  // 499：请求被客户端取消，静默处理
  if (status === 499) {
    return {
      kind: 'cancelled',
      message,
      shouldShowMessage: false,
      shouldRedirectLogin: false
    }
  }

  // 422：参数校验失败，展示字段级错误（仍走去重）
  if (status === 422 && Array.isArray(rawMessage)) {
    const fields = rawMessage
      .map(e => `${e.loc?.join('.') || '?'} : ${e.msg}`)
      .join('; ')
    const validationMessage = '参数校验失败: ' + fields
    const key = buildErrorKey(error, validationMessage)
    return {
      kind: 'validation',
      message: validationMessage,
      shouldShowMessage: deduper ? deduper.shouldShow(key, now) : true,
      shouldRedirectLogin: false
    }
  }

  // 其它错误：按 key 去重后展示
  const key = buildErrorKey(error, message)
  return {
    kind: 'error',
    message,
    shouldShowMessage: deduper ? deduper.shouldShow(key, now) : true,
    shouldRedirectLogin: false
  }
}

/**
 * 归一化错误消息，兼容字符串/数组/缺失场景。
 * @param {*} rawMessage
 * @returns {string}
 */
function normalizeMessage(rawMessage) {
  if (typeof rawMessage === 'string' && rawMessage.trim()) {
    return rawMessage
  }
  return '请求失败'
}
