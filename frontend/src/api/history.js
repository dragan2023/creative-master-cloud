/**
 * historyApi - API 模块
 */
import { api } from './_axios'

export const historyApi = {
  list: (params) => api.get('/api/v1/generate/history', { params }),
  get: (id) => api.get(`/api/v1/generate/history/${id}`),
  delete: (id) => api.delete(`/api/v1/generate/history/${id}`)
}
