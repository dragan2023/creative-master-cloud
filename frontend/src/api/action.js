/**
 * actionApi - 用户行为与体验事件追踪 API
 *
 * 提供 UI 行为追踪（复制/下载等）和体验事件追踪（阶段04新增）。
 */
import { api } from './_axios'

export const actionApi = {
  // ---- 原有 UI 行为 ----

  /** 记录 UI 行为（复制、下载、重新生成等） */
  track: (data) => api.post('/api/v1/generate/action', data),

  /** 获取行为统计 */
  getStats: () => api.get('/api/v1/generate/action/stats'),

  // ---- 体验事件（阶段04新增） ----

  /**
   * 记录体验事件
   *
   * @param {string} eventType - 事件类型: creation_started/completed/cancelled/task_restored/revision_applied/revision_reverted/error_recovered
   * @param {Object} [options]
   * @param {string} [options.module] - 模块名称
   * @param {number} [options.generationId] - 生成记录ID
   * @param {string} [options.phase] - 创作阶段
   * @param {string} [options.durationBucket] - 时长分桶
   * @param {string} [options.errorCategory] - 错误类别
   * @param {boolean} [options.isRetry=false] - 是否重试
   * @param {boolean} [options.isFirstUse=false] - 是否首次使用
   */
  trackExperienceEvent: (eventType, options = {}) => {
    // 静默发送，不阻塞主流程
    return api.post('/api/v1/generate/experience-event', {
      event_type: eventType,
      module: options.module || '',
      generation_id: options.generationId || null,
      phase: options.phase || null,
      duration_bucket: options.durationBucket || null,
      error_category: options.errorCategory || null,
      is_retry: options.isRetry || false,
      is_first_use: options.isFirstUse || false,
    }).catch((err) => {
      // 埋点失败不应影响用户体验，仅静默记录
      console.warn('[actionApi] 体验事件上报失败:', eventType, err?.message || err)
    })
  }
}

/**
 * 便捷函数：计算时长分桶。
 *
 * @param {number} startTimeMs - 开始时间戳（毫秒）
 * @param {number} [endTimeMs] - 结束时间戳（默认 now）
 * @returns {string}
 */
export function computeDurationBucket(startTimeMs, endTimeMs = Date.now()) {
  const seconds = Math.round((endTimeMs - startTimeMs) / 1000)
  if (seconds < 10) return '<10s'
  if (seconds < 30) return '10-30s'
  if (seconds < 60) return '30-60s'
  if (seconds < 300) return '1-5min'
  if (seconds < 900) return '5-15min'
  return '>15min'
}

export default actionApi
