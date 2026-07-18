/**
 * Axios 实例和拦截器
 * 从 index.js 拆分 - API 核心引导代码
 */
import axios from 'axios'
import { API_BASE_URL } from '@/config'
import { ElMessage } from 'element-plus'
import router from '@/router'
import { getToken, clearAuth } from '@/utils/authStorage'
import { normalizeApiError } from './errorPolicy'

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
// 错误提示责任收敛：规范化结果挂载到 error.normalized，
// 仅当 normalized.notify 为真时弹一次全局提示；
// 页面需要专属文案时请求显式传入 { silent: true }，禁止重复弹窗。
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    const normalized = normalizeApiError(error)
    error.normalized = normalized
    
    // 401 未授权 - 清理认证并跳转登录页（由路由处理，不弹全局提示）
    if (normalized.status === 401) {
      // 检查是否已经是登录页，避免重复跳转
      const currentPath = router.currentRoute.value.path
      if (currentPath !== '/login' && currentPath !== '/register') {
        clearAuth()
        console.warn('[API] 401 未授权，跳转登录页')
        router.push({ path: '/login', query: { redirect: currentPath } })
      }
      return Promise.reject(error)
    }
    
    // 499 请求被取消（客户端断开连接）：静默处理，保留原有 reject 形状兼容调用方
    if (normalized.cancelled) {
      console.log('[API] 请求被取消:', normalized.message)
      return Promise.reject({ cancelled: true, message: normalized.message, normalized })
    }
    
    // 422 参数校验失败：输出详细字段级别错误（仅日志，提示文案由 errorPolicy 生成）
    if (normalized.status === 422) {
      console.error('[API] 422 参数校验失败:', JSON.stringify(error.response?.data?.detail, null, 2))
      console.error('[API] 请求体:', JSON.stringify(error.config?.data, null, 2))
    }
    
    // 仅当策略判定需要提示时，显示一次全局提示
    if (normalized.notify) {
      // 安全调用 ElMessage：防止 Element Plus + Vue 3.5 key:0 泄漏导致 setAttribute crash
      try {
        ElMessage.error(normalized.message)
      } catch (domErr) {
        console.error('[API] 错误通知渲染崩溃（ElMessage bug）:', domErr)
        console.error('[API] 原始请求错误:', { status: normalized.status, message: normalized.message, url: error.config?.url })
      }
    }
    return Promise.reject(error)
  }
)
