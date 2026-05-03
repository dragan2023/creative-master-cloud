/**
 * mcpApi - API 模块
 */
import { api } from './_axios'

export const mcpApi = {
  // 获取所有MCP服务状态
  getStatus: () => api.get('/api/v1/mcp/status'),
  
  // 获取可用提供者列表
  getProviders: () => api.get('/api/v1/mcp/providers'),
  
  // 获取MCP配置
  getConfig: () => api.get('/api/v1/mcp/config'),
  
  // 更新MCP配置
  updateConfig: (data) => api.put('/api/v1/mcp/config', data),
  
  // 测试指定提供者连接
  testProvider: (provider) => api.post(`/api/v1/mcp/test/${provider}`),
  
  // 获取实时热点数据
  getTrending: (params) => api.get('/api/v1/mcp/trending', { params }),
  
  // 获取缓存统计
  getCacheStats: () => api.get('/api/v1/mcp/cache/stats'),
  
  // 清除缓存
  clearCache: (provider) => api.delete('/api/v1/mcp/cache', { params: { provider } }),
  
  // 获取平台列表
  getPlatforms: (provider) => api.get('/api/v1/mcp/platforms', { params: { provider } })
}
