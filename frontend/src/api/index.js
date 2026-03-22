import axios from 'axios'
import { API_BASE_URL } from '@/config'
import { ElMessage } from 'element-plus'

// 创建axios实例
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 1800000, // 30分钟超时，用于大文件上传和文档处理
  maxContentLength: 200 * 1024 * 1024, // 200MB
  maxBodyLength: 200 * 1024 * 1024, // 200MB
  headers: {
    'Content-Type': 'application/json'
  }
})

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    const status = error.response?.status
    const message = error.response?.data?.detail || '请求失败'
    
    // 499 表示请求被取消（客户端断开连接）
    if (status === 499) {
      // 请求被取消，不显示错误消息（静默处理）
      console.log('[API] 请求被取消:', message)
      return Promise.reject({ cancelled: true, message })
    }
    
    ElMessage.error(message)
    return Promise.reject(error)
  }
)

// 认证API（已简化，仅保留获取用户信息）
export const authApi = {
  getProfile: () => api.get('/api/v1/auth/me')
}

// API Key管理
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

// 创意生成API
export const generateApi = {
  // 短视频脚本
  shortVideo: (data, onMessage, onWorkflow, onStreamStart, sessionId) => streamGenerate('/api/v1/generate/short-video/stream', data, onMessage, onWorkflow, onStreamStart, sessionId),
  
  // 剧本大纲
  script: (data, onMessage, onWorkflow, onStreamStart, sessionId) => streamGenerate('/api/v1/generate/script/stream', data, onMessage, onWorkflow, onStreamStart, sessionId),
  
  // 小说大纲
  novel: (data, onMessage, onWorkflow, onStreamStart, sessionId) => streamGenerate('/api/v1/generate/novel/stream', data, onMessage, onWorkflow, onStreamStart, sessionId),
  
  // 平面广告
  printAd: (data, onMessage, onWorkflow, onStreamStart, sessionId) => streamGenerate('/api/v1/generate/print-ad/stream', data, onMessage, onWorkflow, onStreamStart, sessionId),
  
  // TVC广告
  tvc: (data, onMessage, onWorkflow, onStreamStart, sessionId) => streamGenerate('/api/v1/generate/tvc/stream', data, onMessage, onWorkflow, onStreamStart, sessionId),
  
  // 原创IP计划
  originalIp: (data, onMessage, onWorkflow, onStreamStart, sessionId) => streamGenerate('/api/v1/generate/original-ip/stream', data, onMessage, onWorkflow, onStreamStart, sessionId),
  
  // 提示词优化
  optimize: (data) => api.post('/api/v1/generate/optimize', data),
  
  // 获取支持的优化模块列表
  getOptimizeModules: () => api.get('/api/v1/generate/optimize/modules'),

  // ==================== 两阶段大纲生成 API ====================

  // 生成全局大纲（第一阶段）
  generateGlobalOutline: (data) => api.post('/api/v1/generate/outline/global', data),

  // 流式生成全局大纲（第一阶段）
  generateGlobalOutlineStream: (data, onMessage, onStreamStart) => {
    return streamGenerateSimple('/api/v1/generate/outline/global/stream', data, onMessage, onStreamStart)
  },

  // 生成单元概述（第二阶段）
  generateUnitSummaries: (data) => api.post('/api/v1/generate/outline/units', data),

  // 流式生成单元概述（第二阶段）
  generateUnitSummariesStream: (data, onMessage, onStreamStart, sessionId) => {
    return streamGenerateSimple('/api/v1/generate/outline/units/stream', data, onMessage, onStreamStart, sessionId)
  },

  // 取消生成任务
  cancelGeneration: (sessionId) => api.post(`/api/v1/generate/cancel/${sessionId}`),

  // 逻辑检测（独立API）
  checkOutlineLogic: (data) => api.post('/api/v1/generate/outline/logic-check', data),


  // 下载大纲文件
  downloadOutline: (content, filename) => {
    return api.post('/api/v1/generate/outline/download', 
      { content, filename },
      { responseType: 'blob' }
    )
  }
}

// SSE流式生成
function streamGenerate(endpoint, data, onMessage, onWorkflow, onStreamStart, sessionId) {
  return new Promise((resolve, reject) => {
    // 构建 URL 查询参数
    const params = new URLSearchParams()
    
    // 如果提供了sessionId，添加到参数中
    if (sessionId) {
      params.append('session_id', sessionId)
    }
    
    // 复制 data 对象，避免修改原始对象
    const requestBody = { ...data }
    
    // 从 requestBody 中提取 enable_knowledge 并作为查询参数传递
    // 后端期望这个参数在 URL 查询参数中，而不是请求体中
    if (requestBody.enable_knowledge !== undefined) {
      params.append('enable_knowledge', requestBody.enable_knowledge)
      // 从请求体中移除，避免重复
      delete requestBody.enable_knowledge
    }
    
    // enable_creative_search 和 enable_search 参数
    // 前端使用 enable_creative_search，后端使用 enable_search，需要映射
    if (requestBody.enable_creative_search !== undefined) {
      params.append('enable_search', requestBody.enable_creative_search)
      delete requestBody.enable_creative_search
    }
    if (requestBody.enable_search !== undefined) {
      params.append('enable_search', requestBody.enable_search)
      delete requestBody.enable_search
    }
    
    // enable_trending 参数
    if (requestBody.enable_trending !== undefined) {
      params.append('enable_trending', requestBody.enable_trending)
      delete requestBody.enable_trending
    }
    
    // 从 requestBody 中提取 enable_mcp 并作为查询参数传递
    if (requestBody.enable_mcp !== undefined) {
      params.append('enable_mcp', requestBody.enable_mcp)
      delete requestBody.enable_mcp
    }
    
    // 知识库类别选择参数
    const kbParams = ['kb_vertical', 'kb_user_specific', 'kb_manual', 
                      'kb_vertical_ids', 'kb_user_specific_ids', 'kb_manual_ids']
    kbParams.forEach(param => {
      // 只有当值存在且不为null时才添加参数，避免将'null'字符串传递给后端
      if (requestBody[param] !== undefined && requestBody[param] !== null && requestBody[param] !== '') {
        params.append(param, requestBody[param])
        delete requestBody[param]
      }
    })
    
    // 搜索关键词参数（数组类型）
    if (requestBody.search_keywords && Array.isArray(requestBody.search_keywords) && requestBody.search_keywords.length > 0) {
      // FastAPI Query 参数格式：search_keywords=keyword1&search_keywords=keyword2
      requestBody.search_keywords.forEach(keyword => {
        params.append('search_keywords', keyword)
      })
      delete requestBody.search_keywords
    } else if (requestBody.search_keywords !== undefined) {
      // 空数组或null，从请求体中移除
      delete requestBody.search_keywords
    }
    
    // 构建完整 URL
    let url = `${API_BASE_URL}${endpoint}`
    const paramString = params.toString()
    if (paramString) {
      url += `?${paramString}`
    }
    
    console.log('[API] Request URL:', url)  // 调试日志
    
    // 使用 POST 请求发送 JSON 数据
    fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(requestBody)
    }).then(response => {
      // 检查 HTTP 状态码
      if (!response.ok) {
        // 尝试解析错误信息
        response.json().then(errData => {
          const errorMsg = errData?.detail || `请求失败: ${response.status}`
          reject(new Error(errorMsg))
        }).catch(() => {
          reject(new Error(`请求失败: ${response.status}`))
        })
        return
      }
      
      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let fullContent = ''
      let generationId = null
      let currentEventType = ''
      let durationMs = null
      let pendingData = ''  // 缓存不完整的SSE数据
      
      // 创建一个可中断的对象
      const abortController = {
        reader,
        abort: () => {
          reader.cancel()
        }
      }
      
      // 通知外部可以中断
      if (onStreamStart) {
        onStreamStart(abortController)
      }
      
      function readChunk() {
        reader.read().then(({ done, value }) => {
          if (done) {
            // 处理剩余的不完整数据
            if (pendingData.trim()) {
              console.warn('[SSE] 流结束时有未处理的数据:', pendingData)
            }
            resolve({ content: fullContent, generation_id: generationId, duration_ms: durationMs })
            return
          }
          
          const text = decoder.decode(value, { stream: true })
          // 将新数据追加到待处理数据中
          pendingData += text
          const lines = pendingData.split('\n')
          
          // 保留最后一个可能不完整的行
          pendingData = lines.pop() || ''
          
          for (const line of lines) {
            if (line.startsWith('event: ')) {
              currentEventType = line.slice(7).trim()
              continue
            }
            if (line.startsWith('data: ')) {
              try {
                const jsonStr = line.slice(6)
                if (jsonStr.trim()) {
                  const eventData = JSON.parse(jsonStr)
                  
                  // 处理 workflow 事件
                  if (currentEventType === 'workflow' && onWorkflow) {
                    onWorkflow(eventData)
                  }
                  
                  // 处理 done 事件 - 获取耗时
                  if (currentEventType === 'done') {
                    if (eventData.duration_ms) {
                      durationMs = eventData.duration_ms
                    }
                    if (eventData.generation_id) {
                      generationId = eventData.generation_id
                    }
                  }
                  
                  // 处理 content 事件
                  if (eventData.text) {
                    fullContent += eventData.text
                    onMessage(fullContent, eventData.text)
                  }
                  if (eventData.generation_id) {
                    generationId = eventData.generation_id
                  }
                }
              } catch (e) {
                // JSON 解析失败，可能是数据不完整
                console.warn('[SSE] JSON解析失败:', e.message, '数据:', line.slice(6))
              }
            }
          }
          
          readChunk()
        })
      }
      
      readChunk()
    }).catch(error => {
      reject(error)
    })
  })
}

// 简化版SSE流式生成（用于两阶段大纲生成）
function streamGenerateSimple(endpoint, data, onMessage, onStreamStart, sessionId) {
  return new Promise((resolve, reject) => {
    // 如果有 sessionId，添加到请求参数中
    let url = `${API_BASE_URL}${endpoint}`
    if (sessionId) {
      url += `?session_id=${sessionId}`
    }

    fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(data)
    }).then(response => {
      if (!response.ok) {
        response.json().then(errData => {
          const errorMsg = errData?.detail || `请求失败: ${response.status}`
          reject(new Error(errorMsg))
        }).catch(() => {
          reject(new Error(`请求失败: ${response.status}`))
        })
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let fullContent = ''

      const abortController = {
        reader,
        abort: () => {
          reader.cancel()
        }
      }

      if (onStreamStart) {
        onStreamStart(abortController)
      }

      function readChunk() {
        reader.read().then(({ done, value }) => {
          if (done) {
            resolve({ content: fullContent })
            return
          }

          const chunk = decoder.decode(value, { stream: true })
          fullContent += chunk

          if (onMessage) {
            onMessage(chunk, fullContent)
          }

          readChunk()
        }).catch(error => {
          if (error.name === 'AbortError') {
            resolve({ content: fullContent, cancelled: true })
          } else {
            reject(error)
          }
        })
      }

      readChunk()
    }).catch(error => {
      reject(error)
    })
  })
}

// 知识库API
export const knowledgeApi = {
  list: (params) => api.get('/api/v1/knowledge', { params }),
  upload: (formData) => api.post('/api/v1/knowledge/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  update: (id, data) => api.put(`/api/v1/knowledge/${id}`, data),
  delete: (id) => api.delete(`/api/v1/knowledge/${id}`),
  getProgress: (id) => api.get(`/api/v1/knowledge/${id}/progress`),
  getAllProcessing: () => api.get('/api/v1/knowledge/processing/all'),
  stopProcessing: (id) => api.post(`/api/v1/knowledge/${id}/stop`),
  getGraph: (id, maxNodes = 100) => api.get(`/api/v1/knowledge/${id}/graph`, { params: { max_nodes: maxNodes } }),
  getGlobalGraph: (maxNodes = 100) => api.get('/api/v1/knowledge/graph/global', { params: { max_nodes: maxNodes } })
}

// 历史记录API
export const historyApi = {
  list: (params) => api.get('/api/v1/generate/history', { params }),
  get: (id) => api.get(`/api/v1/generate/history/${id}`),
  delete: (id) => api.delete(`/api/v1/generate/history/${id}`)
}

// 用户行为追踪API
export const actionApi = {
  // 记录行为
  track: (data) => api.post('/api/v1/generate/action', data),
  // 获取行为统计
  getStats: () => api.get('/api/v1/generate/action/stats')
}

// 用户个人配置API（普通用户可用）
export const userConfigApi = {
  // 代理配置（用户级别）
  getProxyConfig: () => api.get('/api/v1/auth/config/proxy'),
  setProxyConfig: (data) => api.post('/api/v1/auth/config/proxy', data),
  testProxy: () => api.post('/api/v1/auth/config/proxy/test'),

  // 文档预处理配置（用户级别）
  getPreprocessorConfig: () => api.get('/api/v1/auth/config/preprocessor'),
  setPreprocessorConfig: (data) => api.post('/api/v1/auth/config/preprocessor', data)
}

// 软件更新API
export const updateApi = {
  // 检查更新
  check: (currentVersion) => api.post('/api/v1/update/check', { current_version: currentVersion, platform: 'windows' }),
  // 获取下载信息
  getDownloadInfo: () => api.get('/api/v1/update/download'),
  // 获取更新日志
  getChangelog: () => api.get('/api/v1/update/changelog'),
  // 获取当前版本
  getCurrentVersion: () => api.get('/api/v1/update/current-version')
}

// 系统API
export const systemApi = {
  // 退出程序
  exit: () => api.post('/api/v1/system/exit')
}

// MCP服务API
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

// 小说/剧本生成API
export const novelWriterApi = {
  // 项目管理
  getProjects: (params) => api.get('/api/v1/novel-writer/projects', { params }),
  getProject: (id) => api.get(`/api/v1/novel-writer/projects/${id}`),
  createProject: (data) => api.post('/api/v1/novel-writer/projects', data),
  updateProject: (id, data) => api.put(`/api/v1/novel-writer/projects/${id}`, data),
  deleteProject: (id) => api.delete(`/api/v1/novel-writer/projects/${id}`),

  // 大纲上传
  uploadOutline: (id, formData) => api.post(`/api/v1/novel-writer/projects/${id}/upload-outline`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),

  // 单元概述上传
  uploadUnitSummaries: (id, data) => api.post(`/api/v1/novel-writer/projects/${id}/upload-unit-summaries`, data),

  // 单元概述文件上传
  uploadUnitSummariesFile: (id, formData) => api.post(`/api/v1/novel-writer/projects/${id}/upload-unit-summaries-file`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),

  // 目录生成
  generateDirectory: (id, data) => api.post(`/api/v1/novel-writer/projects/${id}/generate-directory`, data),
  getDirectory: (id) => api.get(`/api/v1/novel-writer/projects/${id}/directory`),
  updateDirectory: (id, data) => api.put(`/api/v1/novel-writer/projects/${id}/directory`, data),

  // 章节名称管理
  regenerateChapterNames: (projectId) => api.post(`/api/v1/novel-writer/projects/${projectId}/regenerate-chapter-names`),
  updateChapterTitle: (projectId, chapterNum, title) => api.put(`/api/v1/novel-writer/projects/${projectId}/chapters/${chapterNum}/title`, null, {
    params: { title }
  }),

  // 章节管理
  getChapters: (projectId) => api.get(`/api/v1/novel-writer/projects/${projectId}/chapters`),
  getChapter: (projectId, chapterNum) => api.get(`/api/v1/novel-writer/projects/${projectId}/chapters/${chapterNum}`),
  updateChapter: (projectId, chapterNum, data) => api.put(`/api/v1/novel-writer/projects/${projectId}/chapters/${chapterNum}`, data),
  deleteChapter: (projectId, chapterNum) => api.delete(`/api/v1/novel-writer/projects/${projectId}/chapters/${chapterNum}`),

  // 章节生成
  generateChapter: (projectId, chapterNum) => api.post(`/api/v1/novel-writer/projects/${projectId}/generate-chapter/${chapterNum}`),
  generateAll: (projectId, data) => api.post(`/api/v1/novel-writer/projects/${projectId}/generate-all`, data),

  // 进度获取
  getProgress: (projectId) => api.get(`/api/v1/novel-writer/projects/${projectId}/progress`),

  // 导出
  exportProject: (projectId, data) => api.post(`/api/v1/novel-writer/projects/${projectId}/export`, data, {
    responseType: 'blob'
  }),

  // ==================== 分集详细大纲 API ====================

  // 生成分集详细大纲（单集）
  generateEpisodeOutline: (projectId, episode) => 
    api.post(`/api/v1/novel-writer/projects/${projectId}/generate-episode-outline/${episode}`),

  // 批量生成分集详细大纲
  generateAllEpisodeOutlines: (projectId, data, signal) => 
    api.post(`/api/v1/novel-writer/projects/${projectId}/generate-all-episode-outlines`, data, { signal }),

  // 获取分集大纲列表
  getEpisodeOutlines: (projectId) => 
    api.get(`/api/v1/novel-writer/projects/${projectId}/episode-outlines`),

  // 获取单集大纲
  getEpisodeOutline: (projectId, episode) => 
    api.get(`/api/v1/novel-writer/projects/${projectId}/episode-outlines/${episode}`),

  // 更新分集大纲
  updateEpisodeOutline: (projectId, episode, data) => 
    api.put(`/api/v1/novel-writer/projects/${projectId}/episode-outlines/${episode}`, data),

  // 删除分集大纲
  deleteEpisodeOutline: (projectId, episode) => 
    api.delete(`/api/v1/novel-writer/projects/${projectId}/episode-outlines/${episode}`),

  // ==================== 单集正文生成 API ====================

  // 生成单集正文（完整单集，包含所有场景）
  generateEpisodeContent: (projectId, episode, signal) =>
    api.post(`/api/v1/novel-writer/projects/${projectId}/generate-episode-content/${episode}`, {}, { signal }),

  // ==================== 章节详细大纲 API ====================

  // 生成章节详细大纲（单章）
  generateChapterOutline: (projectId, chapter) =>
    api.post(`/api/v1/novel-writer/projects/${projectId}/generate-chapter-outline/${chapter}`),

  // 批量生成章节详细大纲
  generateAllChapterOutlines: (projectId, data, signal) =>
    api.post(`/api/v1/novel-writer/projects/${projectId}/generate-all-chapter-outlines`, data, { signal }),

  // 获取章节大纲列表
  getChapterOutlines: (projectId) =>
    api.get(`/api/v1/novel-writer/projects/${projectId}/chapter-outlines`),

  // 获取单章大纲
  getChapterOutline: (projectId, chapter) =>
    api.get(`/api/v1/novel-writer/projects/${projectId}/chapter-outlines/${chapter}`),

  // 更新章节大纲
  updateChapterOutline: (projectId, chapter, data) =>
    api.put(`/api/v1/novel-writer/projects/${projectId}/chapter-outlines/${chapter}`, data),

  // 删除章节大纲
  deleteChapterOutline: (projectId, chapter) =>
    api.delete(`/api/v1/novel-writer/projects/${projectId}/chapter-outlines/${chapter}`),

  // ==================== 章节正文生成 API ====================

  // 生成小说章节正文
  generateChapterContent: (projectId, chapter, signal) =>
    api.post(`/api/v1/novel-writer/projects/${projectId}/generate-chapter-content/${chapter}`, {}, { signal }),

  // ==================== 场景详细大纲 API ====================

  // 生成场景详细大纲（单场景）
  generateSceneOutline: (projectId, scene) =>
    api.post(`/api/v1/novel-writer/projects/${projectId}/generate-scene-outline/${scene}`),

  // 批量生成场景详细大纲
  generateAllSceneOutlines: (projectId, data, signal) =>
    api.post(`/api/v1/novel-writer/projects/${projectId}/generate-all-scene-outlines`, data, { signal }),

  // 获取场景大纲列表
  getSceneOutlines: (projectId) =>
    api.get(`/api/v1/novel-writer/projects/${projectId}/scene-outlines`),

  // 获取单场景大纲
  getSceneOutline: (projectId, scene) =>
    api.get(`/api/v1/novel-writer/projects/${projectId}/scene-outlines/${scene}`),

  // 更新场景大纲
  updateSceneOutline: (projectId, scene, data) =>
    api.put(`/api/v1/novel-writer/projects/${projectId}/scene-outlines/${scene}`, data),

  // 删除场景大纲
  deleteSceneOutline: (projectId, scene) =>
    api.delete(`/api/v1/novel-writer/projects/${projectId}/scene-outlines/${scene}`),

  // ==================== 场景正文生成 API ====================

  // 生成电影场景正文
  generateSceneContent: (projectId, scene, signal) =>
    api.post(`/api/v1/novel-writer/projects/${projectId}/generate-scene-content/${scene}`, {}, { signal }),

  // ==================== 批量正文生成 API ====================

  // 批量生成剧集正文
  generateAllEpisodeContent: (projectId, data, signal) =>
    api.post(`/api/v1/novel-writer/projects/${projectId}/generate-all-episode-content`, data, { signal }),

  // 批量生成小说正文
  generateAllChapterContent: (projectId, data, signal) =>
    api.post(`/api/v1/novel-writer/projects/${projectId}/generate-all-chapter-content`, data, { signal }),

  // 批量生成电影正文
  generateAllSceneContent: (projectId, data, signal) =>
    api.post(`/api/v1/novel-writer/projects/${projectId}/generate-all-scene-content`, data, { signal }),

  // ==================== 批量获取正文内容 API ====================

  // 获取全部剧集正文内容
  getAllEpisodeContent: (projectId) =>
    api.get(`/api/v1/novel-writer/projects/${projectId}/all-episode-content`),

  // 获取全部小说章节正文内容
  getAllChapterContent: (projectId) =>
    api.get(`/api/v1/novel-writer/projects/${projectId}/all-chapter-content`),

  // 获取全部电影场景正文内容
  getAllSceneContent: (projectId) =>
    api.get(`/api/v1/novel-writer/projects/${projectId}/all-scene-content`),

  // ==================== 任务状态管理 API ====================

  // 获取任务状态
  getTaskStatus: (projectId) =>
    api.get(`/api/v1/novel-writer/projects/${projectId}/task-status`),

  // 取消生成任务
  cancelTask: (projectId) =>
    api.post(`/api/v1/novel-writer/projects/${projectId}/cancel-task`),

  // SSE 任务事件流 URL（用于 EventSource）
  // 系统已无需认证，直接返回URL
  getTaskEventsURL: (projectId) => {
    const baseURL = api.defaults.baseURL || ''
    return `${baseURL}/api/v1/novel-writer/projects/${projectId}/task-events`
  },

  // ==================== 用户干预机制 API ====================

  // 带用户干预选项的详细大纲生成
  generateOutlineWithIntervention: (projectId, unitNumber, data) =>
    api.post(`/api/v1/novel-writer/projects/${projectId}/outline-intervention/${unitNumber}`, data),

  // 校验详细大纲一致性
  validateOutlineConsistency: (projectId, unitNumber, contentType = 'novel') =>
    api.post(`/api/v1/novel-writer/projects/${projectId}/validate-outline-consistency/${unitNumber}`, {
      content_type: contentType
    }),

  // 获取位置感知上下文
  getPositionAwareContext: (projectId, unitNumber, contentType = 'novel') =>
    api.get(`/api/v1/novel-writer/projects/${projectId}/position-aware-context/${unitNumber}`, {
      params: { content_type: contentType }
    }),

  // ==================== 删除内容 API ====================

  // 删除小说章节正文
  deleteChapterContent: (projectId, chapterNum) =>
    api.delete(`/api/v1/novel-writer/projects/${projectId}/chapter-content/${chapterNum}`),

  // 删除剧集正文
  deleteEpisodeContent: (projectId, episodeNum) =>
    api.delete(`/api/v1/novel-writer/projects/${projectId}/episode-content/${episodeNum}`),

  // 删除电影场景正文
  deleteSceneContent: (projectId, sceneNum) =>
    api.delete(`/api/v1/novel-writer/projects/${projectId}/scene-content/${sceneNum}`),

  // 一键清空所有大纲和正文
  deleteAllContent: (projectId) =>
    api.delete(`/api/v1/novel-writer/projects/${projectId}/all-content`),

  // 一键清空所有大纲
  deleteAllOutlines: (projectId) =>
    api.delete(`/api/v1/novel-writer/projects/${projectId}/all-outlines`),

  // 一键清空所有正文
  deleteAllChapterContent: (projectId) =>
    api.delete(`/api/v1/novel-writer/projects/${projectId}/all-chapter-content`),

  // 同步章节正文状态（修复历史数据）
  syncContentStatus: (projectId) =>
    api.post(`/api/v1/novel-writer/projects/${projectId}/sync-content-status`),

  // ==================== 项目专属知识库 API ====================

  // 构建项目知识库
  buildKnowledgeBase: (projectId) =>
    api.post(`/api/v1/novel-writer/projects/${projectId}/build-knowledge-base`),

  // 获取知识库状态
  getKnowledgeBaseStatus: (projectId) =>
    api.get(`/api/v1/novel-writer/projects/${projectId}/knowledge-base-status`),

  // 获取知识图谱数据
  getKnowledgeGraph: (projectId, unitNumber = null) => {
    const params = unitNumber !== null ? { unit_number: unitNumber } : {}
    return api.get(`/api/v1/novel-writer/projects/${projectId}/knowledge-graph`, { params })
  },

  // 构建单元知识图谱
  buildUnitKnowledgeGraph: (projectId, unitNumber) =>
    api.post(`/api/v1/novel-writer/projects/${projectId}/build-unit-knowledge-graph`, null, {
      params: { unit_number: unitNumber }
    }),

  // 批量构建单元知识图谱
  buildAllUnitKnowledgeGraphs: (projectId, unitNumbers = null) => {
    const params = unitNumbers ? { unit_numbers: unitNumbers.join(',') } : {}
    return api.post(`/api/v1/novel-writer/projects/${projectId}/build-all-unit-graphs`, null, { params })
  },

  // 获取单元图谱状态
  getUnitGraphsStatus: (projectId) =>
    api.get(`/api/v1/novel-writer/projects/${projectId}/unit-graphs-status`),

  // 更新知识库配置
  updateKnowledgeBaseConfig: (projectId, data) =>
    api.put(`/api/v1/novel-writer/projects/${projectId}/knowledge-base-config`, data),

  // 删除项目知识库
  deleteKnowledgeBase: (projectId) =>
    api.delete(`/api/v1/novel-writer/projects/${projectId}/knowledge-base`),

  // 重置知识库构建状态（用于清除幽灵状态）
  resetKnowledgeBaseStatus: (projectId) =>
    api.post(`/api/v1/novel-writer/projects/${projectId}/knowledge-base/reset-status`)

}

export default api
