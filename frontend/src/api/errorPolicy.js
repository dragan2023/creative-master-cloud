/**
 * API 错误策略（纯函数）
 *
 * 统一规范化 Axios 错误，收敛全局提示责任：
 * - 401：认证流程接管（清理 + 跳转登录页），不弹全局提示
 * - 499 / ERR_CANCELED：客户端取消请求（服务端 499 或 AbortController 本地取消），保持静默
 * - 422：数组 detail 转为字段级可读文案
 * - config.silent === true：页面自行处理错误展示，拦截器不提示
 * - 其他：以 detail 字符串或 axios message 兜底，提示一次
 *
 * @module api/errorPolicy
 */

/** 兜底错误文案 */
const DEFAULT_ERROR_MESSAGE = '请求失败'

/** HTTP 状态码：未授权（认证流程接管，不重复提示） */
const HTTP_STATUS_UNAUTHORIZED = 401

/** HTTP 状态码：参数校验失败（FastAPI 返回数组 detail） */
const HTTP_STATUS_VALIDATION_FAILED = 422

/** HTTP 状态码：客户端取消请求（保持静默） */
const HTTP_STATUS_CLIENT_CANCELLED = 499

/** Axios 取消错误码：AbortController/CancelToken 本地取消（无 HTTP 响应，保持静默） */
const AXIOS_CANCELLED_ERROR_CODE = 'ERR_CANCELED'

/**
 * 将 422 数组 detail 转换为字段级可读消息
 * @param {Array<{loc?: string[], msg: string}>} detail - FastAPI 校验错误数组
 * @returns {string} 形如 "参数校验失败: body.title : 标题不能为空; ..."
 */
function formatValidationDetail(detail) {
  const fieldMessages = detail
    .map(item => `${item.loc?.join('.') || '?'} : ${item.msg}`)
    .join('; ')
  return `参数校验失败: ${fieldMessages}`
}

/**
 * 规范化 API 错误为统一结构
 * @param {Object} error - Axios 错误对象
 * @returns {{status: (number|undefined), message: string, notify: boolean, cancelled: boolean}}
 *  - status: HTTP 状态码（网络错误时为 undefined）
 *  - message: 用户可读的错误消息
 *  - notify: 是否应显示一次全局提示
 *  - cancelled: 是否为取消的请求
 */
export function normalizeApiError(error) {
  const status = error.response?.status
  const detail = error.response?.data?.detail
  const cancelled = status === HTTP_STATUS_CLIENT_CANCELLED
    || error.code === AXIOS_CANCELLED_ERROR_CODE
  const silent = error.config?.silent === true
    || status === HTTP_STATUS_UNAUTHORIZED
    || cancelled
  const message = status === HTTP_STATUS_VALIDATION_FAILED && Array.isArray(detail)
    ? formatValidationDetail(detail)
    : (typeof detail === 'string' ? detail : error.message || DEFAULT_ERROR_MESSAGE)

  return {
    status,
    message,
    notify: !silent,
    cancelled
  }
}
