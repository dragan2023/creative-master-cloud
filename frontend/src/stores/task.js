import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { novelWriterApi } from '@/api'

// 任务类型标签映射
const TASK_TYPE_LABELS = {
  'episode_outline': '分集大纲生成',
  'chapter_outline': '章节大纲生成',
  'scene_outline': '场景大纲生成',
  'episode_content': '分集正文生成',
  'chapter_content': '章节正文生成',
  'scene_content': '场景正文生成'
}

export const useTaskStore = defineStore('task', () => {
  // 当前任务状态
  const currentTask = ref(null)
  
  // 正在检查任务状态
  const checkingTask = ref(false)
  
  // 是否有运行中的任务
  const isRunning = computed(() => {
    return currentTask.value && currentTask.value.status === 'running'
  })
  
  // 是否有任务（用于控制进度条显示，无论是否运行中）
  const hasTask = computed(() => {
    return currentTask.value !== null
  })
  
  // 任务进度信息
  const progress = computed(() => {
    if (!currentTask.value) return null
    return {
      completed: currentTask.value.completed_count || 0,
      failed: currentTask.value.failed_count || 0,
      skipped: currentTask.value.skipped_count || 0,
      total: currentTask.value.total_count || 0,
      current: currentTask.value.current_item
    }
  })
  
  // 任务类型标签
  const taskTypeLabel = computed(() => {
    if (!currentTask.value) return ''
    return TASK_TYPE_LABELS[currentTask.value.task_type] || '生成任务'
  })
  
  // 当前步骤信息
  const currentStep = computed(() => {
    if (!currentTask.value) return null
    return currentTask.value.current_step || null
  })
  
  // 步骤历史记录
  const stepsHistory = computed(() => {
    if (!currentTask.value) return []
    return currentTask.value.steps_history || []
  })
  
  // 当前处理项名称
  const currentItemName = computed(() => {
    if (!currentTask.value) return ''
    return currentTask.value.current_item_name || ''
  })
  
  /**
   * 获取项目任务状态
   * 注意：当后端返回 null 时，说明任务不存在，将清除当前任务
   * 这样可以确保任务完成后进度条正确消失
   */
  async function fetchTaskStatus(projectId) {
    checkingTask.value = true
    try {
      const res = await novelWriterApi.getTaskStatus(projectId)
      // 添加空值检查，防止 res 或 res.data 为 null 时报错
      if (res && res.data && res.data.success) {
        // data 为 null 表示后端确认无任务，清除当前状态
        // data 非 null 时才更新（防止网络中断时错误清除运行中的任务）
        currentTask.value = res.data.data
      }
      return currentTask.value
    } catch (error) {
      // 网络错误时不清除任务状态，保持原有显示
      console.error('获取任务状态失败:', error)
      return currentTask.value
    } finally {
      checkingTask.value = false
    }
  }
  
  /**
   * 取消当前任务
   */
  async function cancelTask(projectId) {
    try {
      const res = await novelWriterApi.cancelTask(projectId)
      // 添加空值检查
      if (res && res.data && res.data.success) {
        // 不立即清除任务，保留状态让UI显示已取消
        if (currentTask.value) {
          currentTask.value.status = 'cancelled'
        }
        return true
      }
      return false
    } catch (error) {
      console.error('取消任务失败:', error)
      return false
    }
  }
  
  /**
   * 设置任务（供批量生成开始时调用）
   */
  function setTask(task) {
    currentTask.value = task
  }
  
  /**
   * 清除任务（供任务完成时调用）
   */
  function clearTask() {
    currentTask.value = null
  }
  
  /**
   * 判断是否有运行中的任务
   * @param {string} taskType - 可选，指定任务类型
   */
  function isTaskRunning(taskType = null) {
    if (!currentTask.value) return false
    if (currentTask.value.status !== 'running') return false
    if (taskType) {
      return currentTask.value.task_type === taskType
    }
    return true
  }
  
  /**
   * 判断是否为大纲生成任务
   */
  function isOutlineTask() {
    if (!currentTask.value) return false
    return ['episode_outline', 'chapter_outline', 'scene_outline'].includes(
      currentTask.value.task_type
    )
  }
  
  /**
   * 判断是否为正文生成任务
   */
  function isContentTask() {
    if (!currentTask.value) return false
    return ['episode_content', 'chapter_content', 'scene_content'].includes(
      currentTask.value.task_type
    )
  }
  
  return {
    currentTask,
    checkingTask,
    isRunning,
    hasTask,
    progress,
    taskTypeLabel,
    currentStep,
    stepsHistory,
    currentItemName,
    fetchTaskStatus,
    cancelTask,
    setTask,
    clearTask,
    isTaskRunning,
    isOutlineTask,
    isContentTask
  }
})
