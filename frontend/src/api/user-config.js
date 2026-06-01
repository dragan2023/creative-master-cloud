/**
 * userConfigApi - API 模块
 */
import { api } from './_axios'

export const userConfigApi = {
  // 代理配置（用户级别）
  getProxyConfig: () => api.get('/api/v1/auth/config/proxy'),
  setProxyConfig: (data) => api.post('/api/v1/auth/config/proxy', data),
  testProxy: () => api.post('/api/v1/auth/config/proxy/test'),

  // 文档预处理配置（用户级别）
  getPreprocessorConfig: () => api.get('/api/v1/auth/config/preprocessor'),
  setPreprocessorConfig: (data) => api.post('/api/v1/auth/config/preprocessor', data),

  // DeepSeek思考模式配置（用户级别）
  getThinkingModeConfig: () => api.get('/api/v1/auth/config/thinking-mode'),
  setThinkingModeConfig: (data) => api.post('/api/v1/auth/config/thinking-mode', data)
}
