/**
 * Axios 实例和拦截器
 * 从 index.js 拆分 - API 核心引导代码
 */
import axios from 'axios'
import { API_BASE_URL } from '@/config'
import { ElMessage } from 'element-plus'
import router from '@/router'
import { getToken, clearAuth } from '@/utils/authStorage'

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
    const message = error.response?.data?.detail || '请求失败'
    
    // 401 未授权 - 跳转登录页
    if (status === 401) {
      // 检查是否已经是登录页，避免重复跳转
      const currentPath = router.currentRoute.value.path
      if (currentPath !== '/login' && currentPath !== '/register') {
        clearAuth()
        console.warn('[API] 401 未授权，跳转登录页')
        router.push({ path: '/login', query: { redirect: currentPath } })
      }
      return Promise.reject(error)
    }
    
    // 499 表示请求被取消（客户端断开连接）
    if (status === 499) {
      // 请求被取消，不显示错误消息（静默处理）
      console.log('[API] 请求被取消:', message)
      return Promise.reject({ cancelled: true, message })
    }
    
    // 422 参数校验失败：输出详细字段级别错误
    if (status === 422) {
      const detail = error.response?.data?.detail
      console.error('[API] 422 参数校验失败:', JSON.stringify(detail, null, 2))
      console.error('[API] 请求体:', JSON.stringify(error.config?.data, null, 2))
    }
    
    // 安全调用 ElMessage：防止 Element Plus + Vue 3.5 key:0 泄漏导致 setAttribute crash
    try {
      // 对422显示友好的字段级别错误
      if (status === 422 && Array.isArray(error.response?.data?.detail)) {
        const fields = error.response.data.detail.map(e => `${e.loc?.join('.') || '?'} : ${e.msg}`).join('; ')
        ElMessage.error('参数校验失败: ' + fields)
      } else {
        ElMessage.error(message)
      }
    } catch (domErr) {
      console.error('[API] 错误通知渲染崩溃（ElMessage bug）:', domErr)
      console.error('[API] 原始请求错误:', { status, message, url: error.config?.url })
    }
    return Promise.reject(error)
  }
)
