/**
 * novelWriterApi - API 模块
 */
import { api } from './_axios'
import { API_BASE_URL } from '@/config'
import { getToken } from '@/utils/authStorage'

export const novelWriterApi = {
  // 项目管理
  // getProjects 透传请求配置（如 { silent: true, signal }），避免把 silent 混入查询参数
  getProjects: (params, requestConfig = {}) =>
    api.get('/api/v1/novel-writer/projects', { ...requestConfig, params }),
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

  // 获取全部剧本正文+AI资源内容（剧集/电影类型专用，用于下载全文）
  // 正文内容优先级: content_after_self_revise > content_after_qc_fix > content_after_generation
  getAllScriptContent: (projectId) =>
    api.get(`/api/v1/novel-writer/projects/${projectId}/all-script-content`),

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
  },

  // ==================== AI视觉资源 API ====================

  // 获取AI视觉资源内容
  getAIResource: (projectId, unitIndex) =>
    api.get(`/api/v1/novel-writer/projects/${projectId}/units/${unitIndex}/ai-resource`),

  // 手动保存AI视觉资源内容
  saveAIResource: (projectId, unitIndex, content) =>
    api.put(`/api/v1/novel-writer/projects/${projectId}/units/${unitIndex}/ai-resource`, { content }),

  // 流式生成AI视觉资源(SSE)
  // sourceVersion: "draft" | "qc_fix" | "self_revise"
  generateAIResource: (projectId, unitIndex, sourceVersion, onChunk, onDone, onError) => {
    const abortController = new AbortController()

    const promise = new Promise((resolve, reject) => {
      const url = `${API_BASE_URL}/api/v1/novel-writer/projects/${projectId}/units/${unitIndex}/generate-ai-resource`
      const token = getToken()
      const headers = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`

      fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify({ source_version: sourceVersion }),
        signal: abortController.signal
      }).then(response => {
        if (!response.ok) {
          response.json().then(errData => {
            reject(new Error(errData?.detail || `请求失败: ${response.status}`))
          }).catch(() => reject(new Error(`请求失败: ${response.status}`)))
          return
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let currentEventType = ''
        let pendingData = ''
        let cachedCompleteResult = null  // v2.7: 缓存complete事件数据，等待saved确认

        function readChunk() {
          reader.read().then(({ done, value }) => {
            if (done) {
              // 连接关闭时，如果complete事件已收到但saved未到，仍触发onDone
              if (cachedCompleteResult) {
                if (onDone) onDone(cachedCompleteResult)
              }
              resolve()
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
                    if (currentEventType === 'chunk') {
                      if (onChunk) onChunk(eventData)
                    } else if (currentEventType === 'complete') {
                      // v2.7: 缓存结果，等待saved事件确认保存成功后再触发onDone
                      cachedCompleteResult = eventData
                    } else if (currentEventType === 'saved') {
                      // v2.7: 保存成功，使用saved事件数据（含content）触发onDone
                      if (onDone) onDone(cachedCompleteResult || eventData)
                      cachedCompleteResult = null
                    } else if (currentEventType === 'error') {
                      const errMsg = eventData.message || 'AI资源生成失败'
                      cachedCompleteResult = null  // 清除缓存，防止连接关闭时误触发onDone
                      if (onError) onError(new Error(errMsg))
                    }
                    currentEventType = ''
                  }
                } catch (e) {
                  console.warn('[GenerateAIResource] JSON parse failed:', e.message)
                }
              }
            }
            readChunk()
          }).catch(error => {
            if (error.name === 'AbortError') {
              resolve()
            } else {
              reject(error)
            }
          })
        }
        readChunk()
      }).catch(error => {
        if (error.name === 'AbortError') {
          resolve()
        } else {
          reject(error)
        }
      })
    })

    return { promise, abort: () => abortController.abort() }
  },

  // ==================== 单元内容编辑 API ====================

  // 更新单元正文内容
  updateUnitContent: (data) => {
    const { unit_index, content, project_id, save_as } = data
    const params = project_id ? { project_id } : {}
    return api.put(`/api/v1/novel-writer/units/${unit_index}/content`, { content, save_as }, { params })
  },

  // 单元对话修正（流式）
  // 使用原生 fetch + ReadableStream 自解析 SSE，支持 done/error 事件 + AbortController 中断
  // 通过 POST JSON body 传输大字段，避免 URL 超长触发 HTTP 431
  reviseUnitContent: (unitIndex, data, onMessage, onDone, onError) => {
    const requestBody = {
      project_id: data.project_id,
      user_feedback: data.user_feedback,
      current_content: data.current_content
    }
    if (data.revision_history && data.revision_history.length > 0) {
      requestBody.revision_history = data.revision_history
    }

    const abortController = new AbortController()

    const promise = new Promise((resolve, reject) => {
      const url = `${API_BASE_URL}/api/v1/novel-writer/units/${unitIndex}/revision/stream`
      const token = getToken()
      const headers = { 'Content-Type': 'application/json' }
      if (token) headers['Authorization'] = `Bearer ${token}`

      fetch(url, {
        method: 'POST',
        headers,
        body: JSON.stringify(requestBody),
        signal: abortController.signal
      }).then(response => {
        if (!response.ok) {
          response.json().then(errData => {
            reject(new Error(errData?.detail || `请求失败: ${response.status}`))
          }).catch(() => reject(new Error(`请求失败: ${response.status}`)))
          return
        }

        const reader = response.body.getReader()
        const decoder = new TextDecoder()
        let currentEventType = ''
        let pendingData = ''

        function readChunk() {
          reader.read().then(({ done, value }) => {
            if (done) {
              resolve()
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

                    // event: content / data: {"text": "..."}
                    if (currentEventType === 'content') {
                      if (onMessage) onMessage(eventData)
                    }
                    // event: done / data: {"content": "..."}
                    else if (currentEventType === 'done') {
                      if (onDone) onDone(eventData)
                    }
                    // event: error / data: {"message": "..."}
                    else if (currentEventType === 'error') {
                      const errMsg = eventData.message || eventData.data?.message || '修订失败'
                      if (onError) onError(new Error(errMsg))
                    }
                    // 兼容无 event: 前缀的 data: {"event": "error", "data": {...}} 格式
                    else if (eventData.event === 'error') {
                      const errMsg = eventData.data?.message || eventData.message || '修订失败'
                      if (onError) onError(new Error(errMsg))
                    }
                    // 兼容无 event: 前缀的 data: {"event": "done", ...} 格式
                    else if (eventData.event === 'done') {
                      if (onDone) onDone(eventData.data || eventData)
                    }
                    currentEventType = ''
                  }
                } catch (e) {
                  console.warn('[UnitReviseStream] JSON parse failed:', e.message)
                }
              }
            }
            readChunk()
          }).catch(error => {
            if (error.name === 'AbortError') {
              resolve()
            } else {
              reject(error)
            }
          })
        }
        readChunk()
      }).catch(error => {
        if (error.name === 'AbortError') {
          resolve()
        } else {
          reject(error)
        }
      })
    })

    return { promise, abort: () => abortController.abort() }
  }

}
