/**
 * 多Agent协作文学作品生成系统 - 写作任务API
 * 
 * 模块: api
 * 文件: writing-task.js
 * 功能: 提供写作任务的API调用和WebSocket连接
 * 
 * 依赖关系:
 *   - API基础: @/api (axios实例)
 *   - 配置: @/config (API_BASE_URL)
 * 
 * 创建时间: 2026-03-28
 * 最后修改: 2026-03-28
 * 版本: 1.0.0
 */

import api from '@/api'
import { API_BASE_URL } from '@/config'

/**
 * 写作任务API
 */
export const writingTaskApi = {
  /**
   * 创建写作任务
   * @param {Object} data - 任务配置
   * @returns {Promise}
   */
  createTask: (data) => api.post('/api/v1/writing-tasks', data),

  /**
   * 获取任务列表
   * @param {Object} params - 查询参数
   * @returns {Promise}
   */
  listTasks: (params = {}) => api.get('/api/v1/writing-tasks', { params }),

  /**
   * 获取任务详情
   * @param {number} taskId - 任务ID
   * @returns {Promise}
   */
  getTask: (taskId) => api.get(`/api/v1/writing-tasks/${taskId}`),

  /**
   * 中断任务
   * @param {number} taskId - 任务ID
   * @returns {Promise}
   */
  interruptTask: (taskId) => api.post(`/api/v1/writing-tasks/${taskId}/interrupt`),

  /**
   * 续传任务
   * @param {number} taskId - 任务ID
   * @returns {Promise}
   */
  resumeTask: (taskId) => api.post(`/api/v1/writing-tasks/${taskId}/resume`),

  /**
   * 继续生成任务
   * @param {number} taskId - 任务ID
   * @param {number} unitCount - 继续生成的单元数量
   * @returns {Promise}
   */
  continueTask: (taskId, unitCount) => api.post(`/api/v1/writing-tasks/${taskId}/continue`, { unit_count: unitCount }),

  /**
   * 删除任务
   * @param {number} taskId - 任务ID
   * @returns {Promise}
   */
  deleteTask: (taskId) => api.delete(`/api/v1/writing-tasks/${taskId}`),

  /**
   * 获取任务统计
   * @param {number} taskId - 任务ID
   * @returns {Promise}
   */
  getTaskStats: (taskId) => api.get(`/api/v1/writing-tasks/${taskId}/stats`),

  /**
   * 获取单元列表
   * @param {number} taskId - 任务ID
   * @returns {Promise}
   */
  getTaskUnits: (taskId) => api.get(`/api/v1/writing-tasks/${taskId}/units`),

  /**
   * 获取场景列表
   * @param {number} taskId - 任务ID
   * @param {number} unitIndex - 单元索引
   * @returns {Promise}
   */
  getUnitScenes: (taskId, unitIndex) => api.get(`/api/v1/writing-tasks/${taskId}/units/${unitIndex}/scenes`),

  /**
   * 获取Agent配置
   * @returns {Promise}
   */
  getAgentConfig: () => api.get('/api/v1/agent-config'),

  /**
   * 更新Agent配置
   * @param {Object} config - 配置数据
   * @returns {Promise}
   */
  updateAgentConfig: (config) => api.put('/api/v1/agent-config', config),

  /**
   * 重置Agent配置
   * @returns {Promise}
   */
  resetAgentConfig: () => api.post('/api/v1/agent-config/reset'),

  /**
   * 测试Agent模型连接
   * @param {Object} config - 测试配置 { model_id, provider }
   * @returns {Promise}
   */
  testAgentConnection: (config) => api.post('/api/v1/agent-config/test-connection', config),

  /**
   * 获取可用的AI服务提供商列表
   * @returns {Promise}
   */
  getAvailableProviders: () => api.get('/api/v1/agent-config/providers'),

  // ==================== 写作模型配置管理 ====================

  /**
   * 获取模型配置列表
   * @returns {Promise<{configs: Array}>}
   */
  getModelConfigs: () => api.get('/api/v1/writing-model-configs'),

  /**
   * 创建模型配置
   * @param {Object} data - 配置数据 {name, provider, provider_display, model_id, api_key, api_base}
   * @returns {Promise}
   */
  createModelConfig: (data) => api.post('/api/v1/writing-model-configs', data),

  /**
   * 更新模型配置
   * @param {number} id - 配置ID
   * @param {Object} data - 配置数据
   * @returns {Promise}
   */
  updateModelConfig: (id, data) => api.put(`/api/v1/writing-model-configs/${id}`, data),

  /**
   * 删除模型配置
   * @param {number} id - 配置ID
   * @returns {Promise}
   */
  deleteModelConfig: (id) => api.delete(`/api/v1/writing-model-configs/${id}`),

  /**
   * 测试已保存的模型配置
   * @param {number} id - 配置ID
   * @returns {Promise<{success: boolean, message: string}>}
   */
  testModelConfig: (id) => api.post(`/api/v1/writing-model-configs/${id}/test`),

  /**
   * 测试未保存的模型配置
   * @param {Object} data - 测试配置 {provider, model_id, api_key, api_base}
   * @returns {Promise<{success: boolean, message: string}>}
   */
  testNewModelConfig: (data) => api.post('/api/v1/writing-model-configs/test', data),

  /**
   * 导出模型配置
   * @returns {Promise<{configs: Array}>}
   */
  exportModelConfigs: () => api.get('/api/v1/writing-model-configs/export'),

  /**
   * 导入模型配置
   * @param {Object} data - 导入数据 {configs: [...]}
   * @returns {Promise<{imported: number}>}
   */
  importModelConfigs: (data) => api.post('/api/v1/writing-model-configs/import', data),

  /**
   * 导出任务内容
   * @param {number} taskId - 任务ID
   * @param {string} format - 导出格式 (txt|md)
   * @returns {Promise<Blob>}
   */
  exportTask: (taskId, format = 'txt') => api.get(`/api/v1/writing-tasks/${taskId}/export`, {
    params: { format },
    responseType: 'blob'
  }),

  /**
   * 导出单个单元内容
   * @param {number} taskId - 任务ID
   * @param {number} unitIndex - 单元索引
   * @param {string} format - 导出格式 (txt|md)
   * @returns {Promise<Blob>}
   */
  exportUnit: (taskId, unitIndex, format = 'txt') => api.get(`/api/v1/writing-tasks/${taskId}/units/${unitIndex}/export`, {
    params: { format },
    responseType: 'blob'
  })
}

/**
 * 建立WebSocket连接
 * @param {number} taskId - 任务ID
 * @param {Object} callbacks - 回调函数
 * @returns {WebSocket}
 */
export function connectWritingTaskWS(taskId, callbacks = {}) {
  const {
    onOpen,
    onMessage,
    onClose,
    onError,
    onReconnect
  } = callbacks

  // 构建 WebSocket URL
  // 开发环境：使用当前页面的主机名，让 Vite 代理处理
  // 生产环境：使用完整 URL
  let wsUrl
  if (API_BASE_URL && API_BASE_URL.trim() !== '') {
    // 如果配置了完整的 API_BASE_URL，直接使用
    wsUrl = `${API_BASE_URL.replace(/^http/, 'ws')}/api/v1/writing-tasks/${taskId}/ws`
  } else {
    // 否则使用当前页面的主机名
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    wsUrl = `${protocol}//${host}/api/v1/writing-tasks/${taskId}/ws`
  }
  
  console.log('[WritingTask WS] 连接URL:', wsUrl)
  const ws = new WebSocket(wsUrl)

  ws.onopen = (event) => {
    console.log('[WritingTask WS] 连接成功')
    if (onOpen) onOpen(event)
  }

  ws.onmessage = (event) => {
    try {
      const message = JSON.parse(event.data)
      if (onMessage) onMessage(message)
    } catch (e) {
      console.error('[WritingTask WS] 解析消息失败:', e)
    }
  }

  ws.onclose = (event) => {
    console.log('[WritingTask WS] 连接关闭')
    if (onClose) onClose(event)
  }

  ws.onerror = (error) => {
    console.error('[WritingTask WS] 连接错误:', error)
    if (onError) onError(error)
  }

  return ws
}

export default writingTaskApi
