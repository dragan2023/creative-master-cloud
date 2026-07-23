/**
 * Axios 实例和拦截器
 * 从 index.js 拆分 - API 核心引导代码
 */
import axios from 'axios'
import { API_BASE_URL } from '@/config'
import { ElMessage } from 'element-plus'
import router from '@/router'
import { getToken, clearAuth } from '@/utils/authStorage'
import { createMessageDeduper, resolveErrorAction } from '@/api/errorPolicy'

// 全局错误通知去重器：同一请求的相同错误在时间窗口内只展示一次
const errorDeduper = createMessageDeduper()
// 单次登录跳转保护：连续多次 401 只跳转一次
let isRedirectingToLogin = false

// 创建axios实例
export const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 默认30秒超时（普通API请求）
  maxContentLength: 200 * 1024 * 1024, // 200MB
  maxBodyLength: 200 * 1024 * 1024, // 200MB
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器 - 添加Token
api.interceptors.request.use(
  (config) => {
    const token = getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    const status = error.response?.status
    const currentPath = router.currentRoute.value.path

    // 通过纯函数策略解析处理动作（是否跳转/是否展示/去重）
    const action = resolveErrorAction(error, {
      currentPath,
      deduper: errorDeduper,
      isRedirectingToLogin
    })

    // 401 未授权 - 跳转登录页（连续多次只跳转一次）
    if (action.kind === 'unauthorized') {
      if (action.shouldRedirectLogin) {
        isRedirectingToLogin = true
        clearAuth()
        console.warn('[API] 401 未授权，跳转登录页')
        Promise.resolve(router.push({ path: '/login', query: { redirect: currentPath } }))
          .finally(() => { isRedirectingToLogin = false })
      }
      return Promise.reject(error)
    }

    // 499 表示请求被取消（客户端断开连接），静默处理
    if (action.kind === 'cancelled') {
      console.log('[API] 请求被取消:', action.message)
      return Promise.reject({ cancelled: true, message: action.message })
    }

    // 422 参数校验失败：输出详细字段级别错误便于排查
    if (status === 422) {
      console.error('[API] 422 参数校验失败:', JSON.stringify(error.response?.data?.detail, null, 2))
      console.error('[API] 请求体:', JSON.stringify(error.config?.data, null, 2))
    }

    // 安全调用 ElMessage：防止 Element Plus + Vue 3.5 key:0 泄漏导致 setAttribute crash
    // 仅在去重策略判定应展示时才弹出通知
    if (action.shouldShowMessage && action.message) {
      try {
        ElMessage.error(action.message)
      } catch (domErr) {
        console.error('[API] 错误通知渲染崩溃（ElMessage bug）:', domErr)
        console.error('[API] 原始请求错误:', { status, message: action.message, url: error.config?.url })
      }
    }
    return Promise.reject(error)
  }
)
