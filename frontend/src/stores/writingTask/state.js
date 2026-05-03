/**
 * 多Agent协作文学作品生成系统 - 写作任务状态管理（状态部分）
 * 
 * 模块: writing-engine
 * 文件: writingTask/state.js
 * 功能: 定义写作任务的状态和计算属性
 * 
 * 创建时间: 2026-03-27
 * 最后修改: 2026-04-26
 */

import { ref, computed } from 'vue'

export function useWritingTaskState() {
  // ==================== 状态 ====================
  
  /** 当前任务 */
  const currentTask = ref(null)
  
  /** 任务列表 */
  const taskList = ref([])
  
  /** 任务单元列表 */
  const units = ref([])
  
  /** 场景缓存 { unitIndex: scenes[] } */
  const scenes = ref({})
  
  /** 任务统计信息 */
  const stats = ref(null)
  
  /** Agent配置 */
  const agentConfig = ref(null)
  
  /** 加载状态 */
  const loading = ref(false)
  
  /** WebSocket连接实例 */
  const wsConnection = ref(null)

  /** WebSocket连接状态 */
  const wsConnected = ref(false)

  /** WebSocket消息队列 */
  const progressMessages = ref([])

  /** 批量质控进度状态（v2.2新增） */
  const batchQCProgress = ref({
    status: 'idle',
    current: 0,
    total: 0,
    currentUnit: null,
    startedAt: null,
    completedAt: null
  })

  // ==================== 计算属性 ====================
  
  /** 任务是否运行中 */
  const isRunning = computed(() => currentTask.value?.status === 'running')
  
  /** 任务是否待执行 */
  const isPending = computed(() => currentTask.value?.status === 'pending')
  
  /** 任务是否已完成 */
  const isCompleted = computed(() => currentTask.value?.status === 'completed')
  
  /** 任务是否已中断 */
  const isInterrupted = computed(() => currentTask.value?.status === 'interrupted')
  
  /** 任务是否失败 */
  const isFailed = computed(() => currentTask.value?.status === 'failed')
  
  /** 任务是否可以续传（中断或失败状态都可以续传） */
  const canResume = computed(() => {
    const status = currentTask.value?.status
    return status === 'interrupted' || status === 'failed'
  })
  
  /** 任务进度百分比 */
  const progress = computed(() => {
    if (!currentTask.value) return 0
    const { total_units, completed_units } = currentTask.value
    return total_units > 0 ? Math.round((completed_units / total_units) * 100) : 0
  })
  
  /** 进度详情 */
  const progressDetail = computed(() => {
    if (!currentTask.value) return null
    const task = currentTask.value
    return {
      total: task.total_units || 0,
      completed: task.completed_units || 0,
      failed: task.failed_units || 0,
      skipped: task.skipped_units || 0,
      current: task.current_unit || null,
      currentScene: task.current_scene || null,
      percentage: progress.value
    }
  })
  
  /** 最新消息 */
  const latestMessage = computed(() => {
    const messages = progressMessages.value
    return messages.length > 0 ? messages[messages.length - 1] : null
  })

  /** 当前正在处理的单元 */
  const currentUnit = computed(() => {
    if (!currentTask.value || !Array.isArray(units.value)) return null
    return units.value.find(u => u.status === 'processing' || u.status === 'structuring') || null
  })

  /** 格式化任务持续时间 */
  const formattedDuration = computed(() => {
    if (!currentTask.value?.start_time) return '0秒'
    const start = new Date(currentTask.value.start_time)
    const end = currentTask.value.end_time ? new Date(currentTask.value.end_time) : new Date()
    const seconds = Math.floor((end - start) / 1000)
    if (seconds < 60) return `${seconds}秒`
    if (seconds < 3600) return `${Math.floor(seconds / 60)}分${seconds % 60}秒`
    return `${Math.floor(seconds / 3600)}时${Math.floor((seconds % 3600) / 60)}分`
  })

  return {
    // 状态
    currentTask,
    taskList,
    units,
    scenes,
    stats,
    agentConfig,
    loading,
    wsConnection,
    wsConnected,
    progressMessages,
    batchQCProgress,  // v2.2新增
    // 计算属性
    isRunning,
    isPending,
    isCompleted,
    isInterrupted,
    isFailed,
    canResume,
    progress,
    progressDetail,
    latestMessage,
    currentUnit,
    formattedDuration
  }
}
