import { api } from './_axios'

// 管理员API
export const adminApi = {
  // ==================== 仪表盘 ====================
  // 获取仪表盘统计数据
  getDashboard: () => api.get('/api/v1/admin/dashboard'),
  
  // 获取系统健康状态
  getHealth: () => api.get('/api/v1/admin/health'),
  
  // ==================== 用户管理 ====================
  // 获取用户列表
  getUsers: (params) => api.get('/api/v1/admin/users', { params }),
  
  // 获取单个用户详情
  getUser: (id) => api.get(`/api/v1/admin/users/${id}`),
  
  // 更新用户信息
  updateUser: (id, data) => api.put(`/api/v1/admin/users/${id}`, data),
  
  // 删除用户
  deleteUser: (id) => api.delete(`/api/v1/admin/users/${id}`),
  
  // 重置用户密码
  resetPassword: (id, password) => api.post(`/api/v1/admin/users/${id}/reset-password`, { password }),
  
  // ==================== 租户管理 ====================
  // 获取租户列表
  getTenants: (params) => api.get('/api/v1/admin/tenants', { params }),
  
  // 获取单个租户详情
  getTenant: (id) => api.get(`/api/v1/admin/tenants/${id}`),
  
  // 更新租户信息
  updateTenant: (id, data) => api.put(`/api/v1/admin/tenants/${id}`, data),
  
  // 删除租户
  deleteTenant: (id) => api.delete(`/api/v1/admin/tenants/${id}`),
  
  // 更新租户套餐
  updateTenantPlan: (id, plan) => api.put(`/api/v1/admin/tenants/${id}/plan`, { plan }),
  
  // ==================== 操作日志 ====================
  // 获取操作日志
  getLogs: (params) => api.get('/api/v1/admin/logs', { params }),
  
  // 导出操作日志
  exportLogs: (params) => api.get('/api/v1/admin/logs/export', { params, responseType: 'blob' }),
  
  // ==================== 系统配置 ====================
  // 获取系统配置
  getConfig: () => api.get('/api/v1/admin/config'),
  
  // 更新系统配置
  updateConfig: (data) => api.put('/api/v1/admin/config', data),
  
  // ==================== 提示词管理 ====================
  // 获取提示词模板列表
  getPrompts: (params) => api.get('/api/v1/admin/prompts', { params }),
  
  // 创建提示词模板
  createPrompt: (data) => api.post('/api/v1/admin/prompts', data),
  
  // 更新提示词模板
  updatePrompt: (id, data) => api.put(`/api/v1/admin/prompts/${id}`, data),
  
  // 删除提示词模板
  deletePrompt: (id) => api.delete(`/api/v1/admin/prompts/${id}`),

  // ==================== 体验指标（阶段04新增） ====================
  /**
   * 获取体验质量指标
   * @param {Object} [params] - 查询参数
   * @param {number} [params.days=14] - 统计最近 N 天
   * @param {number} [params.tenant_id] - 租户ID（不传则跨租户聚合）
   */
  getExperienceMetrics: (params) => api.get('/api/v1/admin/experience-metrics', { params })
}

export default adminApi
