/**
 * apiKeyApi - API 模块
 */
import { api } from './_axios'

export const apiKeyApi = {
  list: () => api.get('/api/v1/auth/api-keys'),
  create: (data) => api.post('/api/v1/auth/api-keys', data),
  delete: (id) => api.delete(`/api/v1/auth/api-keys/${id}`),
  setDefault: (id) => api.put(`/api/v1/auth/api-keys/${id}/default`),
  // 测试新添加的API Key（添加时调用）
  test: (data) => api.post('/api/v1/auth/api-keys/test', data),
  // 测试已保存的API Key（列表中调用）
  testSaved: (id) => api.post(`/api/v1/auth/api-keys/${id}/test`)
}
