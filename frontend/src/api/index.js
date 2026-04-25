import axios from 'axios'
import { API_BASE_URL } from '@/config'
import { ElMessage } from 'element-plus'
import router from '@/router'

// 创建axios实例
const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000, // 默认30秒超时（普通API请求）
  maxContentLength: 200 * 1024 * 1024, // 200MB
  maxBodyLength: 200 * 1024 * 1024, // 200MB
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器 - 添加Token
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response.data
  },
  (error) => {
    const status = error.response?.status
    const message = error.response?.data?.detail || '请求失败'
    
    // 401 未授权 - 跳转登录页
    if (status === 401) {
      // 检查是否已经是登录页，避免重复跳转
      const currentPath = router.currentRoute.value.path
      if (currentPath !== '/login' && currentPath !== '/register') {
        localStorage.removeItem('token')
        localStorage.removeItem('userInfo')
        console.warn('[API] 401 未授权，跳转登录页')
        router.push({ path: '/login', query: { redirect: currentPath } })
      }
      return Promise.reject(error)
    }
    
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

// 认证API
export const authApi = {
  // 登录
  login: (data) => api.post('/api/v1/auth/login', data),
  // 注册
  register: (data) => api.post('/api/v1/auth/register', data),
  // 获取当前用户信息
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
  
  // 提示词优化（需要较长超时时间，因为需要调用LLM）
  optimize: (data) => api.post('/api/v1/generate/optimize', data, { timeout: 120000 }),
  
  // 获取支持的优化模块列表
  getOptimizeModules: () => api.get('/api/v1/generate/optimize/modules'),

  // ==================== 两阶段大纲生成 API ====================

  // 生成全局大纲（第一阶段）
  generateGlobalOutline: (data) => api.post('/api/v1/generate/outline/global', data),

  // 流式生成全局大纲（第一阶段）- v2.3新增质控回调
  generateGlobalOutlineStream: (data, onMessage, onStreamStart, onWorkflow, onReplaceContent, onQCReport) => {
    return streamGenerateSimple('/api/v1/generate/outline/global/stream', data, onMessage, onStreamStart, null, onWorkflow, onReplaceContent, onQCReport)
  },

  // 对全局大纲执行知识库修正（用户确认后调用）
  reviseGlobalOutlineWithKnowledge: (data) => api.post('/api/v1/generate/outline/global/revise', data),

  // 流式修订全局大纲（多轮对话）
  reviseGlobalOutlineStream: (data, onMessage, onDone, onError) => {
    // streamGenerate的参数: (endpoint, data, onMessage, onWorkflow, onStreamStart, sessionId)
    return new Promise((resolve, reject) => {
      streamGenerate(
        '/api/v1/generate/outline/global/revise-stream',
        data,
        onMessage,
        () => {},  // onWorkflow - 修订不需要
        () => {},  // onStreamStart - 修订不需要
        null       // sessionId - 修订不需要
      ).then(resolve).catch(reject)
    })
  },

  // 获取最近的生成记录(用于恢复)
  getLatestGeneration: (module) => api.get(`/api/v1/generate/latest/${module}`),
  
  // 恢复指定的生成记录
  restoreGeneration: (generationId) => api.get(`/api/v1/generate/${generationId}/restore`),

  // 生成单元概述（第二阶段）
  generateUnitSummaries: (data) => api.post('/api/v1/generate/outline/units', data),

  // 流式生成单元概述(第二阶段) - v2.3新增质控回调
  generateUnitSummariesStream: (data, onMessage, onStreamStart, sessionId, onWorkflow, onReplaceContent, onQCReport) => {
    return streamGenerateSimple('/api/v1/generate/outline/units/stream', data, onMessage, onStreamStart, sessionId, onWorkflow, onReplaceContent, onQCReport)
  },
    
  // 接续生成单元概述(新增) - 用于处理截断内容
  continueUnitSummaries: (data, onMessage, onStreamStart, sessionId, onWorkflow) => {
    return streamGenerateSimple('/api/v1/generate/outline/units/continue', data, onMessage, onStreamStart, sessionId, onWorkflow)
  },
  
  // 取消生成任务
  cancelGeneration: (sessionId) => api.post(`/api/v1/generate/cancel/${sessionId}`),

  // 获取单元概述断点续生成信息
  getUnitSummariesResumeInfo: (projectId) => api.get(`/api/v1/generate/outline/units/resume-info/${projectId}`),

  // 逻辑检测（独立API，需要较长超时时间）
  checkOutlineLogic: (data) => api.post('/api/v1/generate/outline/logic-check', data, { timeout: 120000 }),


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
    
    // 调试日志：输出完整的请求参数
    if (import.meta.env.DEV) {
      console.log('[API] Request URL:', url)
      console.log('[API] Query Params:', Object.fromEntries(params))
      console.log('[API] Request Body:', requestBody)
    }
    
    // 获取认证 token
    const token = localStorage.getItem('token')
    const fetchHeaders = { 'Content-Type': 'application/json' }
    if (token) {
      fetchHeaders['Authorization'] = `Bearer ${token}`
    }
    
    // 使用 POST 请求发送 JSON 数据
    fetch(url, {
      method: 'POST',
      headers: fetchHeaders,
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
                    console.log('[SSE] 收到 workflow 事件:', eventData)
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
                  
                  // 处理 content 事件（text字段存在时）
                  if (eventData.text) {
                    fullContent += eventData.text
                    onMessage(fullContent, eventData.text)
                  }
                  if (eventData.generation_id) {
                    generationId = eventData.generation_id
                  }
                }
                // 重置事件类型，避免影响下一个事件
                currentEventType = ''
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
// 支持 workflow 事件、replace_content 事件、qc_report 事件
function streamGenerateSimple(endpoint, data, onMessage, onStreamStart, sessionId, onWorkflow, onReplaceContent, onQCReport) {
  return new Promise((resolve, reject) => {
    let url = `${API_BASE_URL}${endpoint}`
    if (sessionId) {
      url += `?session_id=${sessionId}`
    }

    // 获取认证 token
    const token = localStorage.getItem('token')
    const headers = { 'Content-Type': 'application/json' }
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    fetch(url, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(data)
    }).then(response => {
      if (!response.ok) {
        response.json().then(errData => {
          reject(new Error(errData?.detail || `请求失败: ${response.status}`))
        }).catch(() => reject(new Error(`请求失败: ${response.status}`)))
        return
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let fullContent = ''
      let currentEventType = ''
      let pendingData = ''

      const abortController = { reader, abort: () => reader.cancel() }
      if (onStreamStart) onStreamStart(abortController)

      function readChunk() {
        reader.read().then(({ done, value }) => {
          if (done) {
            resolve({ content: fullContent })
            return
          }

          const text = decoder.decode(value, { stream: true })
          pendingData += text
          const lines = pendingData.split('\n')
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
                  if (currentEventType === 'workflow' && onWorkflow) onWorkflow(eventData)
                  if (currentEventType === 'replace_content' && onReplaceContent) {
                    fullContent = eventData.content || ''
                    // v2.3新增：传递质控相关字段
                    onReplaceContent(eventData.content, eventData.message, eventData)
                  }
                  // v2.3新增：处理qc_report事件
                  if (currentEventType === 'qc_report' && onQCReport) {
                    onQCReport(eventData)
                  }
                  if (currentEventType === 'content' && eventData.text) {
                    fullContent += eventData.text
                    if (onMessage) onMessage(eventData.text, fullContent)
                  }
                  currentEventType = ''
                }
              } catch (e) { console.warn('[SSE] JSON解析失败:', e.message) }
            }
          }
          readChunk()
        }).catch(error => {
          if (error.name === 'AbortError') resolve({ content: fullContent, cancelled: true })
          else reject(error)
        })
      }
      readChunk()
    }).catch(error => reject(error))
  })
}


// 知识库API
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

  // 单元概述质控检测
  triggerUnitSummariesQualityControl: (id, data = {}) => api.post(`/api/v1/novel-writer/projects/${id}/unit-summaries/quality-control`, data, {
    timeout: 600000  // 10分钟超时 - 质控检测可能需要较长时间
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

  // 进度获取
  // TODO: 已迁移到新的Writing Task系统

  // 导出
  exportProject: (projectId, data) => api.post(`/api/v1/novel-writer/projects/${projectId}/export`, data, {
    responseType: 'blob'
  }),

  // ==================== 分集详细大纲 API ====================
  // TODO: 大纲生成已迁移到新的Writing Task系统

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
  // TODO: 正文生成已迁移到新的Writing Task系统

  // ==================== 章节详细大纲 API ====================
  // TODO: 大纲生成已迁移到新的Writing Task系统

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

  // 生成章节详细大纲
  generateChapterOutlines: (projectId, data = {}) =>
    api.post(`/api/v1/novel-writer/projects/${projectId}/generate-chapter-outlines`, data),

  // 异步生成章节详细大纲（支持中断）
  generateChapterOutlinesAsync: (projectId, data = {}) =>
    api.post(`/api/v1/novel-writer/projects/${projectId}/generate-chapter-outlines-async`, data),

  // 中断章节大纲生成
  interruptChapterOutlines: (projectId) =>
    api.post(`/api/v1/novel-writer/projects/${projectId}/interrupt-chapter-outlines`),

  // 获取章节大纲生成进度
  getChapterOutlinesProgress: (projectId) =>
    api.get(`/api/v1/novel-writer/projects/${projectId}/chapter-outlines-progress`),

  // 获取章节大纲生成SSE事件流
  getChapterOutlinesEventsUrl: (projectId, token) =>
    `/api/v1/novel-writer/projects/${projectId}/chapter-outlines-events?token=${token}`,

  // ==================== 章节正文生成 API ====================
  // TODO: 正文生成已迁移到新的Writing Task系统

  // ==================== 场景详细大纲 API ====================
  // TODO: 大纲生成已迁移到新的Writing Task系统

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
  // TODO: 正文生成已迁移到新的Writing Task系统

  // ==================== 批量正文生成 API ====================
  // TODO: 批量正文生成已迁移到新的Writing Task系统

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
  // TODO: 用户干预机制已迁移到新的Writing Task系统

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

  // ==================== 风格文档 API ====================

  // 获取风格文档信息
  getStyleDocument: (projectId) =>
    api.get(`/api/v1/novel-writer/projects/${projectId}/style-document`),

  // 上传风格文档
  uploadStyleDocument: (projectId, formData) =>
    api.post(`/api/v1/novel-writer/projects/${projectId}/style-document`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    }),

  // 删除风格文档
  deleteStyleDocument: (projectId) =>
    api.delete(`/api/v1/novel-writer/projects/${projectId}/style-document`),

  // 更新风格文档设置（AI消除开关和阈值）
  updateStyleDocumentSettings: (projectId, data) =>
    api.put(`/api/v1/novel-writer/projects/${projectId}/style-document`, data),

  // ==================== 文风知识库 API ====================

  // 获取文风知识库列表
  getStyleLibrary: (category = null) => {
    const params = category ? { category } : {}
    return api.get('/api/v1/novel-writer/style-library', { params })
  },

  // 获取单个文风详情
  getStyleDetail: (styleId) =>
    api.get(`/api/v1/novel-writer/style-library/${styleId}`),

  // 融合多个文风
  blendStyles: (styleIds, intensity = 0.7) =>
    api.post('/api/v1/novel-writer/style-library/blend', {
      style_ids: styleIds,
      intensity
    }),

  // ==================== 项目专属知识库 API ====================

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
    api.post(`/api/v1/novel-writer/projects/${projectId}/knowledge-base/reset-status`),

  // ==================== 一致性检查报告 API ====================

  // 获取一致性检查报告
  getConsistencyReport: (projectId, unitNumber = null) => {
    const params = unitNumber !== null ? { unit_number: unitNumber } : {}
    return api.get(`/api/v1/novel-writer/projects/${projectId}/consistency-report`, { params })
  },

  // 获取人物状态详情
  getCharacterStates: (projectId, unitNumber = null, characterName = null) => {
    const params = {}
    if (unitNumber !== null) params.unit_number = unitNumber
    if (characterName) params.character_name = characterName
    return api.get(`/api/v1/novel-writer/projects/${projectId}/character-states`, { params })
  },

  // 获取扩展实体状态
  getExtendedEntities: (projectId, unitNumber = null, entityType = null) => {
    const params = {}
    if (unitNumber !== null) params.unit_number = unitNumber
    if (entityType) params.entity_type = entityType
    return api.get(`/api/v1/novel-writer/projects/${projectId}/extended-entities`, { params })
  },

  // 检查内容一致性
  checkContentConsistency: (projectId, content, unitNumber = null) => {
    const params = { content }
    if (unitNumber !== null) params.unit_number = unitNumber
    return api.post(`/api/v1/novel-writer/projects/${projectId}/check-content-consistency`, null, { params })
  }

}

// 修订相关API
export const revisionApi = {
  // 提交修订请求(流式)
  revise: (generationId, data, onMessage, onDone, onError) => {
    return streamGenerate(
      `/api/v1/generate/revision/${generationId}/stream`,
      data,
      onMessage,
      null,  // onWorkflow
      null,  // onStreamStart
      null   // sessionId
    )
  },
  
  // 最终确认
  finalize: (generationId, data) => 
    api.post(`/api/v1/generate/finalize/${generationId}`, data),
  
  // 获取修订历史
  getHistory: (generationId) => 
    api.get(`/api/v1/generate/revision/${generationId}/history`)
}

// 质量管控 v2.0 API
export const qualityControlApi = {
  // 应用自动修正
  applyFix: (data) => api.post('/api/v1/novel-writer/quality-control/apply-fix', data, { timeout: 300000 }),
  
  // 提交用户反馈
  submitFeedback: (data) => api.post('/api/v1/novel-writer/quality-control/feedback', data),
  
  // v2.1新增: LLM生成修正方案（需要较长超时，因为LLM调用可能很慢）
  generateFix: (data) => api.post('/api/v1/novel-writer/quality-control/generate-fix', data, { timeout: 300000 }),
  
  // v2.1新增: 重新分析质量
  reAnalyze: (data) => api.post('/api/v1/novel-writer/quality-control/re-analyze', data, { timeout: 300000 })
}

// 全局大纲质控 API (v1.0新增)
// 注意: 全局大纲内容较长(10000-20000字),LLM分析需要10-20分钟
export const globalOutlineQCApi = {
  // 质量检测 - 超时1200000ms(20分钟)
  analyze: (projectId, data) => api.post(`/api/v1/novel-writer/quality-control/global-outline/${projectId}`, data, {
    timeout: 1200000  // 20分钟超时 - 避免LLM长耗时导致超时
  }),
  
  // 修正大纲 - 超时1200000ms(20分钟)
  revise: (projectId, data) => api.post(`/api/v1/novel-writer/quality-control/global-outline/${projectId}/revise`, data, {
    timeout: 1200000  // 20分钟超时 - 避免LLM长耗时导致超时
  }),
  
  // v2.3新增: 导入大纲自动质控修正 - 超时1200000ms(20分钟)
  autoReviseImported: (data) => api.post('/api/v1/novel-writer/quality-control/imported-outline/auto-revise', data, {
    timeout: 1200000  // 20分钟超时 - 避免LLM长耗时导致超时
  })
}

// 单元概述质控 API (手动触发)
export const unitSummariesQCApi = {
  // 质量检测与修正 - 超时600000ms(10分钟)
  analyzeAndRevise: (data) => api.post('/api/v1/generate/outline/units/quality-control', data, {
    timeout: 600000  // 10分钟超时
  })
}

export default api
