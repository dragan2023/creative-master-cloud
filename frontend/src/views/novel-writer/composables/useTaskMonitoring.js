/**
 * useTaskMonitoring - 任务状态监控（SSE + 轮询）
 * 
 * 从 useProjectDetailState.js 提取，封装 SSE 连接、HTTP 轮询、任务刷新等逻辑。
 */
import { ref } from 'vue'
import { useTaskStore } from '@/stores/task'

export function useTaskMonitoring(projectId, refreshCallbacks = {}) {
  const taskStore = useTaskStore()

  // ==================== 状态 ====================

  const taskPollingTimer = ref(null)
  const TASK_POLLING_INTERVAL = 2000
  const sseConnection = ref(null)
  const sseReconnectTimer = ref(null)
  const SSE_RECONNECT_DELAY = 3000

  // ==================== SSE 连接 ====================

  function startSSEConnection() {
    if (!projectId.value) return

    stopSSEConnection()

    const baseUrl = import.meta.env.VITE_API_BASE_URL || window.location.origin
    const url = `${baseUrl}/api/v1/novel-writer/tasks/${projectId.value}/stream`

    const eventSource = new EventSource(url)
    sseConnection.value = eventSource

    eventSource.onopen = () => {
      console.log('[SSE] 连接已建立')
      // SSE 连接成功后停止 HTTP 轮询
      stopTaskPolling()
    }

    eventSource.onmessage = (event) => {
      try {
        const taskData = event.data === 'null' ? null : JSON.parse(event.data)
        
        if (taskData) {
          taskStore.setTask(taskData)
          refreshListByTaskType(taskData.task_type)
          
          if (taskData.status !== 'running') {
            setTimeout(() => {
              if (taskStore.currentTask?.status !== 'running') {
                stopSSEConnection()
              }
            }, 1000)
          }
        } else {
          taskStore.clearTask()
          stopSSEConnection()
        }
      } catch (e) {
        console.error('[SSE] 解析消息失败:', e)
      }
    }
    
    eventSource.onerror = (error) => {
      console.warn('[SSE] 连接错误，准备重连', error)
      eventSource.close()
      sseConnection.value = null
      
      sseReconnectTimer.value = setTimeout(() => {
        if (!sseConnection.value) {
          console.log('[SSE] 尝试重连...')
          startSSEConnection()
        }
      }, SSE_RECONNECT_DELAY)
      
      // 降级到 HTTP 轮询
      startTaskPolling()
    }
  }

  function stopSSEConnection() {
    if (sseReconnectTimer.value) {
      clearTimeout(sseReconnectTimer.value)
      sseReconnectTimer.value = null
    }
    
    if (sseConnection.value) {
      sseConnection.value.close()
      sseConnection.value = null
      console.log('[SSE] 连接已关闭')
    }
  }

  // ==================== HTTP 轮询 ====================

  function startTaskPolling() {
    stopTaskPolling()
    console.log('[轮询] 启动任务状态轮询')
    
    taskPollingTimer.value = setInterval(async () => {
      const task = await taskStore.fetchTaskStatus(projectId.value)
      
      if (!task) {
        stopTaskPolling()
        return
      }
      
      await refreshListByTaskType(task.task_type)
      
      if (task.status !== 'running') {
        stopTaskPolling()
      }
    }, TASK_POLLING_INTERVAL)
  }

  function stopTaskPolling() {
    if (taskPollingTimer.value) {
      clearInterval(taskPollingTimer.value)
      taskPollingTimer.value = null
    }
  }

  // ==================== 列表刷新 ====================

  async function refreshListByTaskType(taskType) {
    if (!taskType) return
    const { loadEpisodeOutlines, loadChapterOutlines, loadSceneOutlines } = refreshCallbacks
    try {
      if (taskType === 'episode_outline' || taskType === 'episode_content') {
        if (loadEpisodeOutlines) await loadEpisodeOutlines()
      } else if (taskType === 'chapter_outline' || taskType === 'chapter_content') {
        if (loadChapterOutlines) await loadChapterOutlines()
      } else if (taskType === 'scene_outline' || taskType === 'scene_content') {
        if (loadSceneOutlines) await loadSceneOutlines()
      }
    } catch (error) {
      console.error('刷新列表失败:', error)
    }
  }

  // ==================== 统一接口 ====================

  function startTaskMonitoring() {
    if (typeof EventSource !== 'undefined') {
      startSSEConnection()
    } else {
      startTaskPolling()
    }
  }

  function stopTaskMonitoring() {
    stopSSEConnection()
    stopTaskPolling()
  }

  return {
    sseConnection,
    sseReconnectTimer,
    taskPollingTimer,
    startSSEConnection,
    stopSSEConnection,
    startTaskPolling,
    stopTaskPolling,
    refreshListByTaskType,
    startTaskMonitoring,
    stopTaskMonitoring
  }
}
