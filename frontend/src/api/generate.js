/**
 * generateApi - API 模块
 */
import { api } from './_axios'
import { API_BASE_URL } from '@/config'
import { getToken } from '@/utils/authStorage'

export const generateApi = {
  // 短视频脚本
  shortVideo: (data, onMessage, onWorkflow, onStreamStart, sessionId) => streamGenerate('/api/v1/generate/short-video/stream', data, onMessage, onWorkflow, onStreamStart, sessionId),
  
  // 电影大纲
  movieOutline: (data, onMessage, onWorkflow, onStreamStart, sessionId) => streamGenerate('/api/v1/generate/movie-outline/stream', data, onMessage, onWorkflow, onStreamStart, sessionId),
  
  // 剧集大纲
  seriesOutline: (data, onMessage, onWorkflow, onStreamStart, sessionId) => streamGenerate('/api/v1/generate/series-outline/stream', data, onMessage, onWorkflow, onStreamStart, sessionId),
  
  // 小说大纲
  novel: (data, onMessage, onWorkflow, onStreamStart, sessionId) => streamGenerate('/api/v1/generate/novel/stream', data, onMessage, onWorkflow, onStreamStart, sessionId),
  
  // 平面广告
  printAd: (data, onMessage, onWorkflow, onStreamStart, sessionId) => streamGenerate('/api/v1/generate/print-ad/stream', data, onMessage, onWorkflow, onStreamStart, sessionId),
  
  // TVC广告
  tvc: (data, onMessage, onWorkflow, onStreamStart, sessionId) => streamGenerate('/api/v1/generate/tvc/stream', data, onMessage, onWorkflow, onStreamStart, sessionId),
  
  // 原创IP计划
  originalIp: (data, onMessage, onWorkflow, onStreamStart, sessionId) => streamGenerate('/api/v1/generate/original-ip/stream', data, onMessage, onWorkflow, onStreamStart, sessionId),
  
  // 应用文写作
  practicalWriting: (data, onMessage, onWorkflow, onStreamStart, sessionId) => streamGenerate('/api/v1/generate/practical-writing/stream', data, onMessage, onWorkflow, onStreamStart, sessionId),
  
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
  // [2026-05-12 修复] 改为自定义 SSE 解析器，支持 diff_complete/error 事件
  reviseGlobalOutlineStream: (data, onMessage, onDone, onError) => {
    return new Promise((resolve, reject) => {
      const url = `${API_BASE_URL}/api/v1/generate/outline/global/revise-stream`
      const token = getToken()
      const headers = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`

      fetch(url, {
        method: 'POST',
        headers,
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

        function readChunk() {
          reader.read().then(({ done, value }) => {
            if (done) {
              resolve({ content: fullContent, success: true })
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

                    if (currentEventType === 'content' && eventData.text) {
                      fullContent += eventData.text
                      if (onMessage) onMessage(fullContent, eventData.text)
                    } else if (currentEventType === 'diff_complete') {
                      if (onDone) onDone({ type: 'diff_complete', data: eventData })
                    } else if (currentEventType === 'error') {
                      const errMsg = eventData.data || eventData.message || '修订失败'
                      // 同时通知 onDone（兼容旧回调统一处理）和 onError
                      if (onDone) onDone({ type: 'error', data: eventData })
                      if (onError) onError(new Error(errMsg))
                    }
                    currentEventType = ''
                  }
                } catch (e) {
                  console.warn('[ReviseStream] JSON parse failed:', e.message)
                }
              }
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
      }).catch(error => reject(error))
    })
  },

  // 单元概述流式对话修订
  reviseUnitSummariesStream: (data, onContent, onDone, onError) => {
    return new Promise((resolve, reject) => {
      const url = `${API_BASE_URL}/api/v1/generate/outline/units/revise-stream`
      const token = getToken()
      const headers = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`

      fetch(url, {
        method: 'POST',
        headers,
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

        function readChunk() {
          reader.read().then(({ done, value }) => {
            if (done) {
              resolve({ content: fullContent, success: true })
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

                    if (currentEventType === 'content' && eventData.text) {
                      fullContent += eventData.text
                      if (onContent) onContent(fullContent, eventData.text)
                    } else if (currentEventType === 'diff_complete') {
                      if (onDone) onDone({ type: 'diff_complete', data: eventData })
                    } else if (currentEventType === 'error') {
                      const errMsg = eventData.data || eventData.message || '修订失败'
                      if (onDone) onDone({ type: 'error', data: eventData })
                      if (onError) onError(new Error(errMsg))
                    }
                    currentEventType = ''
                  }
                } catch (e) {
                  console.warn('[UnitSummariesReviseStream] JSON parse failed:', e.message)
                }
              }
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
      }).catch(error => reject(error))
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
  cancelGeneration: (sessionId) => api.post(`/api/v1/generate/cancel/${sessionId}`, {}, { timeout: 10000 }),

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
  },

  // ==================== v4.2 知识图谱构建 API ====================

  // 构建知识图谱（二阶段流程内建）
  buildKnowledgeGraph: (data) => api.post('/api/v1/generate/outline/build-knowledge-graph', data),

  // 查询知识图谱构建状态
  getKnowledgeBaseStatus: (projectId) => api.get(`/api/v1/novel-writer/projects/${projectId}/knowledge-base-status`)
}


export function streamGenerate(endpoint, data, onMessage, onWorkflow, onStreamStart, sessionId) {
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
    const token = getToken()
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


export function streamGenerateSimple(endpoint, data, onMessage, onStreamStart, sessionId, onWorkflow, onReplaceContent, onQCReport) {
  return new Promise((resolve, reject) => {
    let url = `${API_BASE_URL}${endpoint}`
    if (sessionId) {
      url += `?session_id=${sessionId}`
    }

    // 获取认证 token
    const token = getToken()
    const headers = { 'Content-Type': 'application/json' }
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    fetch(url, {
      method: 'POST',
      headers: headers,
      body: JSON.stringify(data)
    }).then(response => {
      // [2026-05-05] 从响应头中捕获generation_id
      const generationId = response.headers.get('X-Generation-ID')
      const generationIdNum = generationId ? parseInt(generationId) : null

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
            resolve({ content: fullContent, generation_id: generationIdNum })
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
          if (error.name === 'AbortError') resolve({ content: fullContent, cancelled: true, generation_id: generationIdNum })
          else reject(error)
        })
      }
      readChunk()
    }).catch(error => reject(error))
  })
}


// 知识库API
