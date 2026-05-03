/**
 * authApi - API 模块
 */
import { api } from './_axios'

export const authApi = {
  // 登录
  login: (data) => api.post('/api/v1/auth/login', data),
  // 注册
  register: (data) => api.post('/api/v1/auth/register', data),
  // 获取当前用户信息
  getProfile: () => api.get('/api/v1/auth/me')
}
