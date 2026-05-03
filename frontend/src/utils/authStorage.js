/**
 * 认证令牌统一访问层
 *
 * 集中管理 token 的读写操作，消除散落的 localStorage 直接调用。
 * 当前使用 localStorage 存储 token。
 *
 * @module authStorage
 */

const TOKEN_KEY = 'token'
const USER_INFO_KEY = 'userInfo'

// ==================== Token 操作 ====================

/** 获取认证令牌 */
export function getToken() {
  return localStorage.getItem(TOKEN_KEY)
}

/** 设置认证令牌 */
export function setToken(newToken) {
  localStorage.setItem(TOKEN_KEY, newToken)
}

/** 移除认证令牌 */
export function removeToken() {
  localStorage.removeItem(TOKEN_KEY)
}

// ==================== 用户信息操作 ====================

/** 获取用户信息对象 */
export function getUserInfo() {
  try {
    return JSON.parse(localStorage.getItem(USER_INFO_KEY) || 'null')
  } catch {
    return null
  }
}

/** 设置用户信息 */
export function setUserInfo(info) {
  localStorage.setItem(USER_INFO_KEY, JSON.stringify(info))
}

/** 移除用户信息 */
export function removeUserInfo() {
  localStorage.removeItem(USER_INFO_KEY)
}

// ==================== 组合操作 ====================

/** 保存登录数据（token + userInfo） */
export function saveAuthData(access_token, user) {
  setToken(access_token)
  setUserInfo(user)
}

/** 清除所有认证数据 */
export function clearAuth() {
  removeToken()
  removeUserInfo()
}

// ==================== 便捷构造器 ====================

/**
 * 构建 Authorization 请求头
 * 用于 axios 拦截器、fetch 请求等场景
 * @returns {Object} 包含 Authorization 字段的 headers 对象
 */
export function getAuthHeaders() {
  const token = getToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

/**
 * 构建 SSE 连接的认证查询参数
 *
 * 当前实现：优先使用 ticket 认证，降级到 token 认证
 *   1. 先调用后端 /api/v1/novel-writer/projects/{id}/sse-ticket 获取 ticket
 *   2. 使用 ticket 建立 SSE 连接
 *   3. Ticket 使用后立即失效，提升安全性
 *
 * @param {number} projectId - 项目 ID（用于获取 ticket）
 * @returns {Promise<URLSearchParams>} 认证参数
 */
export async function getSseAuthParams(projectId) {
  const params = new URLSearchParams()
  
  // 尝试获取 ticket
  if (projectId) {
    try {
      const token = getToken()
      const response = await fetch(
        `/api/v1/novel-writer/projects/${projectId}/sse-ticket`,
        {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
          }
        }
      )
      
      if (response.ok) {
        const data = await response.json()
        const ticket = data.data?.ticket
        if (ticket) {
          params.set('ticket', ticket)
          return params
        }
      }
    } catch (error) {
      console.warn('[SSE] 获取 ticket 失败，降级到 token 认证:', error)
    }
  }
  
  // 降级：使用 token 认证
  const token = getToken()
  if (token) {
    params.set('token', token)
  }
  return params
}

/**
 * 构建 WebSocket 连接的认证 URL 参数
 *
 * 当前实现：token 直接附加到 URL
 * 未来实现：与 SSE ticket 机制统一
 *
 * @returns {string} 认证查询字符串（不含 ? 前缀），如 "token=xxx"
 */
export function getWsAuthQuery() {
  const token = getToken()
  if (!token) return ''
  return `token=${encodeURIComponent(token)}`
}
