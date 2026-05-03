/**
 * actionApi - API 模块
 */
import { api } from './_axios'

export const actionApi = {
  // 记录行为
  track: (data) => api.post('/api/v1/generate/action', data),
  // 获取行为统计
  getStats: () => api.get('/api/v1/generate/action/stats')
}
