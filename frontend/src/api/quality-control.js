/**
 * qualityControlApi - API 模块
 */
import { api } from './_axios'

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


export const unitSummariesQCApi = {
  // 质量检测与修正 - 超时600000ms(10分钟)
  analyzeAndRevise: (data) => api.post('/api/v1/generate/outline/units/quality-control', data, {
    timeout: 600000  // 10分钟超时
  })
}
