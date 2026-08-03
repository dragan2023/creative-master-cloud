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

  // 422：参数校验失败，展示字段标签而非内部路径（仍走去重）
  if (status === 422 && Array.isArray(rawMessage)) {
    const labelMsg = formatValidationErrors(rawMessage)
    const validationMessage = '参数校验失败: ' + labelMsg
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

// ============================================================
// 错误分类体系 — 网络、认证、限流、模型不可用、任务中断
// ============================================================

/** 错误类别枚举 */
export const ErrorKind = Object.freeze({
  NETWORK: 'network',
  UNAUTHORIZED: 'unauthorized',
  RATE_LIMITED: 'rate-limited',
  MODEL_UNAVAILABLE: 'model-unavailable',
  TASK_INTERRUPTED: 'task-interrupted',
  VALIDATION: 'validation',
  CANCELLED: 'cancelled',
  ERROR: 'error'
})

/** 常见内部字段路径到用户友好标签的映射 */
const FIELD_LABEL_MAP = {
  'title': '标题',
  'topic': '主题',
  'content': '内容',
  'description': '描述',
  'name': '名称',
  'model': '模型',
  'provider': '提供商',
  'api_key': 'API密钥',
  'api_base': 'API地址',
  'template': '模板',
  'text': '文本',
  'password': '密码',
  'username': '用户名',
  'email': '邮箱',
  'phone': '手机号',
  'type': '类型',
  'format': '格式',
  'style': '风格',
  'length': '长度',
  'genre': '体裁',
  'plot': '情节',
  'synopsis': '概要',
  'chapters': '章节数',
  'chapter_count': '章节数',
  'characters': '角色',
  'outline': '大纲',
  'prompt': '提示词',
  'system_prompt': '系统提示词',
  'input_params': '输入参数',
  'knowledge_files': '知识文件',
  'temperature': '创意度',
  'max_tokens': '最大长度',
  'narrative_mode': '叙事模式'
}

/**
 * 将内部字段路径转换为用户友好的标签。
 * 例如 "body.title" → "标题"，"input_params.0.name" → "名称"
 * @param {string} locStr - 字段路径，如 "body.title" 或 "title"
 * @returns {string}
 */
export function fieldPathToLabel(locStr) {
  if (!locStr) return '未知字段'
  // 取最后一段有意义的字段名（跳过 body/, 数字索引, query/, path/）
  const parts = locStr.split('.')
  // 反向找第一个非数字非 body/query/path 的有效字段名
  for (let i = parts.length - 1; i >= 0; i--) {
    const p = parts[i]
    if (p === 'body' || p === 'query' || p === 'path' || /^\d+$/.test(p)) continue
    return FIELD_LABEL_MAP[p] || p
  }
  return locStr
}

/**
 * 将 FastAPI 422 detail 数组转换为用户可读的字段标签消息。
 * @param {Array} detail - error.response?.data?.detail
 * @returns {string}
 */
export function formatValidationErrors(detail) {
  if (!Array.isArray(detail)) return '参数校验失败'
  return detail
    .map(e => {
      const locStr = e.loc?.join('.') || ''
      const label = fieldPathToLabel(locStr)
      const msg = e.msg || '格式不正确'
      return `「${label}」${msg}`
    })
    .join('；')
}

/**
 * 综合分类错误类型。
 * 用于决定前端展示哪个 RecoverableErrorState 组件。
 *
 * @param {Object} error - Axios 错误对象
 * @returns {{ kind: string, retryAfterSeconds: number }}
 */
export function classifyError(error) {
  const status = error?.response?.status
  const data = error?.response?.data
  const detailStr = error?.response?.data?.detail || ''

  // 网络错误：无状态码且无响应
  if (!status && error.code === 'ERR_NETWORK') {
    return { kind: ErrorKind.NETWORK, retryAfterSeconds: 0 }
  }
  if (!status && error.message === 'Network Error') {
    return { kind: ErrorKind.NETWORK, retryAfterSeconds: 0 }
  }

  // 超时
  if (error.code === 'ECONNABORTED') {
    return { kind: ErrorKind.NETWORK, retryAfterSeconds: 0 }
  }

  // 认证
  if (status === 401 || status === 403) {
    return { kind: ErrorKind.UNAUTHORIZED, retryAfterSeconds: 0 }
  }

  // 限流
  if (status === 429) {
    const retryAfter = parseInt(error?.response?.headers?.['retry-after'] || '0', 10)
    return { kind: ErrorKind.RATE_LIMITED, retryAfterSeconds: retryAfter || 15 }
  }

  // 模型不可用 (503 / 502 / 504)
  if (status === 503 || status === 502 || status === 504) {
    if (detailStr.includes('model') || detailStr.includes('模型')) {
      return { kind: ErrorKind.MODEL_UNAVAILABLE, retryAfterSeconds: 0 }
    }
    return { kind: ErrorKind.MODEL_UNAVAILABLE, retryAfterSeconds: 0 }
  }

  // 任务中断: 后端主动返回 409 表示任务状态冲突/已中断
  if (status === 409) {
    return { kind: ErrorKind.TASK_INTERRUPTED, retryAfterSeconds: 0 }
  }

  // 取消
  if (status === 499) {
    return { kind: ErrorKind.CANCELLED, retryAfterSeconds: 0 }
  }

  // 校验
  if (status === 422) {
    return { kind: ErrorKind.VALIDATION, retryAfterSeconds: 0 }
  }

  // 其他服务端/客户端错误
  if (status && status >= 500) {
    // 检查消息中是否包含模型相关关键词
    const msg = (typeof data?.detail === 'string' ? data.detail : '') || ''
    if (msg.includes('model') || msg.includes('Model') || msg.includes('unavailable')) {
      return { kind: ErrorKind.MODEL_UNAVAILABLE, retryAfterSeconds: 0 }
    }
  }

  return { kind: ErrorKind.ERROR, retryAfterSeconds: 0 }
}

/**
 * 根据错误分类获取推荐恢复动作集合。
 *
 * @param {string} kind - ErrorKind 值
 * @returns {{ primary: 'retry'|'relogin'|'retry-after'|'recover'|null, secondary: string[] }}
 */
export function getRecoveryActions(kind) {
  switch (kind) {
    case ErrorKind.NETWORK:
      return { primary: 'retry', secondary: ['cancel'] }
    case ErrorKind.UNAUTHORIZED:
      return { primary: 'relogin', secondary: [] }
    case ErrorKind.RATE_LIMITED:
      return { primary: 'retry-after', secondary: ['cancel'] }
    case ErrorKind.MODEL_UNAVAILABLE:
      return { primary: 'retry', secondary: ['cancel'] }
    case ErrorKind.TASK_INTERRUPTED:
      return { primary: 'recover', secondary: ['cancel', 'view-tasks'] }
    case ErrorKind.VALIDATION:
      return { primary: null, secondary: [] }
    case ErrorKind.CANCELLED:
      return { primary: null, secondary: [] }
    default:
      return { primary: 'retry', secondary: ['cancel', 'view-tasks'] }
  }
}
