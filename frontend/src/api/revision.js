/**
 * revisionApi - API 模块
 *
 * 注意：修订流式接口的 SSE 事件格式为 data: {"event":"diff_chunk"|"diff_complete"|"error","data":...}
 * 事件名在 JSON 内部（而非 SSE event: 行），因此使用独立解析器按 payload.event 分发。
 */
import { api } from './_axios'
import { API_BASE_URL } from '@/config'
import { getToken } from '@/utils/authStorage'

export const revisionApi = {
  // 提交修订请求(流式)
  // onDiffChunk(text): LLM 输出的 diff 指令文本片段
  // onDiffComplete(diffInstructions): 解析完成的差异指令 JSON 对象
  // onError(Error): 后端返回 error 事件
  revise: (generationId, data, onDiffChunk, onDiffComplete, onError) => {
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
        let pendingData = ''

        function readChunk() {
          reader.read().then(({ done, value }) => {
            if (done) {
              resolve({ success: true })
              return
            }

            pendingData += decoder.decode(value, { stream: true })
            const lines = pendingData.split('\n')
            pendingData = lines.pop() || ''

            for (const line of lines) {
              if (!line.startsWith('data: ')) continue
              const jsonStr = line.slice(6)
              if (!jsonStr.trim()) continue
              try {
                const payload = JSON.parse(jsonStr)
                if (payload.event === 'diff_chunk') {
                  if (onDiffChunk) onDiffChunk(payload.data)
                } else if (payload.event === 'diff_complete') {
                  if (onDiffComplete) onDiffComplete(payload.data)
                } else if (payload.event === 'error') {
                  const errMsg = typeof payload.data === 'string'
                    ? payload.data
                    : (payload.data?.message || '修订失败')
                  if (onError) onError(new Error(errMsg))
                }
              } catch (e) {
                console.warn('[RevisionStream] JSON parse failed:', e.message)
              }
            }
            readChunk()
          }).catch(error => {
            if (error.name === 'AbortError') {
              resolve({ cancelled: true })
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
