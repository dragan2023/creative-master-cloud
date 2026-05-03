/**
 * revisionApi - API 模块
 */
import { api } from './_axios'
import { streamGenerate } from './generate'

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
