/**
 * knowledgeApi - API 模块
 */
import { api } from './_axios'

export const knowledgeApi = {
  // 列表查询（短操作，30秒超时）
  list: (params) => api.get('/api/v1/knowledge', { params, timeout: 30000 }),
  // 上传文件（长操作，使用全局超时）
  upload: (formData) => api.post('/api/v1/knowledge/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  // 更新知识库（短操作，30秒超时）
  update: (id, data) => api.put(`/api/v1/knowledge/${id}`, data, { timeout: 30000 }),
  // 删除知识库（使用全局超时，可能涉及大量数据清理）
  delete: (id) => api.delete(`/api/v1/knowledge/${id}`),
  // 获取进度（短操作，15秒超时）
  getProgress: (id) => api.get(`/api/v1/knowledge/${id}/progress`, { timeout: 15000 }),
  // 获取所有处理中的知识库（短操作，15秒超时）
  getAllProcessing: () => api.get('/api/v1/knowledge/processing/all', { timeout: 15000 }),
  // 停止处理（短操作，15秒超时）
  stopProcessing: (id) => api.post(`/api/v1/knowledge/${id}/stop`, null, { timeout: 15000 }),
  // 获取知识图谱（中等操作，60秒超时）
  getGraph: (id, maxNodes = 100) => api.get(`/api/v1/knowledge/${id}/graph`, { params: { max_nodes: maxNodes }, timeout: 60000 }),
  // 获取全局知识图谱（中等操作，60秒超时）
  getGlobalGraph: (maxNodes = 100) => api.get('/api/v1/knowledge/graph/global', { params: { max_nodes: maxNodes }, timeout: 60000 })
}
