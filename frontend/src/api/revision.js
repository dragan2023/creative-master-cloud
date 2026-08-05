/**
 * revisionApi - API 模块
 *
 * [2026-08-04] 修订流式接口改为“全文流式”方案（与大纲模块一致）：
 * LLM 直接输出修订后的完整内容，前端整段替换，避免 diff 匹配失败导致修订不生效。
 * SSE 事件格式: event: content / diff_complete / error
 */
import { api } from './_axios'
import { API_BASE_URL } from '@/config'
import { getToken } from '@/utils/authStorage'

export const revisionApi = {
  // 提交修订请求(流式) - 全文修订
  // onContent(fullContent, chunkText): 修订后完整内容（实时累积）
  // onDone({type: 'diff_complete', data}): 修订完成（data.summary 为修改概述）
  // onError(Error): 后端返回 error 事件
  revise: (generationId, data, onContent, onDone, onError) => {
    return new Promise((resolve, reject) => {
      const url = `${API_BASE_URL}/api/v1/generate/revision/${generationId}/stream`
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

            pendingData += decoder.decode(value, { stream: true })
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
                  if (!jsonStr.trim()) continue
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
                } catch (e) {
                  console.warn('[RevisionStream] JSON parse failed:', e.message)
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

  // 最终确认
  finalize: (generationId, data) =>
    api.post(`/api/v1/generate/finalize/${generationId}`, data),

  // 获取修订历史
  getHistory: (generationId) =>
    api.get(`/api/v1/generate/revision/${generationId}/history`)
}
