/**
 * 多Agent协作文学作品生成系统 - 写作任务状态管理
 * 
 * 模块: writing-engine
 * 文件: writingTask.js
 * 功能: 写作任务的Pinia状态管理，包含WebSocket实时更新
 * 
 * 依赖关系:
 *   - API: @/api/writing-task (writingTaskApi, connectWritingTaskWS)
 *   - Store: 独立状态管理
 * 
 * 创建时间: 2026-03-27
 * 最后修改: 2026-03-27
 * 版本: 1.0.0
 * 
 * [2026-03-28] 多Agent重构: 统一WebSocket消息type处理，添加unit_progress/scene_progress/statistics分支
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { writingTaskApi, connectWritingTaskWS } from '@/api/writing-task'

export const useWritingTaskStore = defineStore('writingTask', () => {
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
  
  /** WebSocket重连定时器 */
  let reconnectTimer = null
  
  /** 重连延迟（毫秒） */
  const RECONNECT_DELAY = 3000
  
  /** 最大重连次数 */
  const MAX_RECONNECT_ATTEMPTS = 5
  
  /** 当前重连次数 */
  let reconnectAttempts = 0

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

  // ==================== Actions ====================
  
  /**
   * 创建写作任务
   * @param {string} projectId - 项目ID
   * @param {Object} payload - 任务配置
   * @returns {Promise<Object>} 创建的任务
   */
  async function createTask(projectId, payload = {}) {
    loading.value = true
    try {
      const res = await writingTaskApi.createTask({
        project_id: projectId,
        start_from: payload.start_from || 1,
        unit_count: payload.unit_count || null,
        config: payload.config || {}
      })
      currentTask.value = res.data
      // 创建成功后连接WebSocket
      connectWS(res.data.id)
      return res.data
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 获取任务详情
   * @param {string} taskId - 任务ID
   * @returns {Promise<Object>} 任务详情
   */
  async function fetchTask(taskId) {
    try {
      const res = await writingTaskApi.getTask(taskId)
      currentTask.value = res.data
      return res.data
    } catch (error) {
      console.error('[WritingTask Store] 获取任务失败:', error)
      throw error
    }
  }
  
  /**
   * 获取项目的当前任务（用于组件初始化）
   * @param {number} projectId - 项目ID
   * @returns {Promise<Object|null>} 当前任务或null
   */
  async function fetchCurrentTask(projectId) {
    try {
      // 先尝试获取运行中的任务
      const res = await writingTaskApi.listTasks({ status: 'running', page: 1, page_size: 10 })
      if (res.data?.items) {
        const task = res.data.items.find(t => t.project_id === projectId)
        if (task) {
          currentTask.value = task
          // 连接WebSocket
          connectWS(task.id)
          // 加载单元列表
          await fetchUnits(task.id)
          return task
        }
      }
      
      // 如果没有运行中的任务，获取最近的一个任务
      const listRes = await writingTaskApi.listTasks({ page: 1, page_size: 1 })
      if (listRes.data?.items) {
        const task = listRes.data.items.find(t => t.project_id === projectId)
        if (task) {
          currentTask.value = task
          await fetchUnits(task.id)
          return task
        }
      }
      
      currentTask.value = null
      return null
    } catch (error) {
      console.error('[WritingTask Store] 获取当前任务失败:', error)
      return null
    }
  }
  
  /**
   * 获取任务列表
   * @param {Object} params - 查询参数
   * @returns {Promise<Array>} 任务列表
   */
  async function fetchTaskList(params = {}) {
    loading.value = true
    try {
      const res = await writingTaskApi.listTasks(params)
      const listData = res.data || { items: [], total: 0 }
      taskList.value = listData.items || []
      return listData
    } finally {
      loading.value = false
    }
  }
  
  /**
   * 中断任务
   * @param {string} taskId - 任务ID
   * @returns {Promise} 操作结果
   */
  async function interruptTask(taskId) {
    try {
      const res = await writingTaskApi.interruptTask(taskId)
      if (currentTask.value?.id === taskId) {
        // 不立即更新状态，等待WebSocket推送状态变更
        // currentTask.value.status = 'interrupted'
      }
      // 不立即断开WebSocket，等待服务器推送最终状态
      // disconnectWS()
      return res
    } catch (error) {
      console.error('[WritingTask Store] 中断任务失败:', error)
      throw error
    }
  }
  
  /**
   * 恢复任务
   * @param {string} taskId - 任务ID
   * @returns {Promise} 操作结果
   */
  async function resumeTask(taskId) {
    try {
      const res = await writingTaskApi.resumeTask(taskId)
      if (currentTask.value?.id === taskId) {
        currentTask.value.status = 'running'
        // 重新连接WebSocket
        connectWS(taskId)
      }
      return res
    } catch (error) {
      console.error('[WritingTask Store] 恢复任务失败:', error)
      throw error
    }
  }
  
  /**
   * 继续生成任务
   * @param {string} taskId - 任务ID
   * @param {number} unitCount - 继续生成的单元数量
   * @returns {Promise} 操作结果
   */
  async function continueTask(taskId, unitCount) {
    try {
      const res = await writingTaskApi.continueTask(taskId, unitCount)
      if (currentTask.value?.id === taskId) {
        currentTask.value.status = 'running'
        // 重新连接WebSocket
        connectWS(taskId)
      }
      return res
    } catch (error) {
      console.error('[WritingTask Store] 继续生成任务失败:', error)
      throw error
    }
  }
  
  /**
   * 获取任务单元列表
   * @param {string} taskId - 任务ID
   * @returns {Promise<Array>} 单元列表
   */
  async function fetchUnits(taskId) {
    try {
      const res = await writingTaskApi.getTaskUnits(taskId)
      units.value = res.data
      return res.data
    } catch (error) {
      console.error('[WritingTask Store] 获取单元失败:', error)
      throw error
    }
  }
  
  /**
   * 获取单元场景列表
   * @param {string} taskId - 任务ID
   * @param {number} unitIndex - 单元索引
   * @returns {Promise<Array>} 场景列表
   */
  async function fetchScenes(taskId, unitIndex) {
    try {
      const res = await writingTaskApi.getUnitScenes(taskId, unitIndex)
      scenes.value[unitIndex] = res.data
      return res.data
    } catch (error) {
      console.error('[WritingTask Store] 获取场景失败:', error)
      throw error
    }
  }
  
  /**
   * 获取任务统计信息
   * @param {string} taskId - 任务ID
   * @returns {Promise<Object>} 统计信息
   */
  async function fetchStats(taskId) {
    try {
      const res = await writingTaskApi.getTaskStats(taskId)
      stats.value = res.data
      return res.data
    } catch (error) {
      console.error('[WritingTask Store] 获取统计失败:', error)
      throw error
    }
  }
  
  /**
   * 删除任务
   * @param {string} taskId - 任务ID
   * @returns {Promise} 操作结果
   */
  async function deleteTask(taskId) {
    try {
      const res = await writingTaskApi.deleteTask(taskId)
      // 如果删除的是当前任务，清除状态
      if (currentTask.value?.id === taskId) {
        disconnectWS()
        currentTask.value = null
        units.value = []
        scenes.value = {}
        stats.value = null
        progressMessages.value = []
      }
      // 从列表中移除
      const index = taskList.value.findIndex(t => t.id === taskId)
      if (index !== -1) {
        taskList.value.splice(index, 1)
      }
      return res
    } catch (error) {
      console.error('[WritingTask Store] 删除任务失败:', error)
      throw error
    }
  }
  
  // ==================== Agent配置 ====================
  
  /**
   * 获取Agent配置
   * @returns {Promise<Object>} 配置信息
   */
  async function fetchAgentConfig() {
    try {
      const res = await writingTaskApi.getAgentConfig()
      agentConfig.value = res.data
      return res.data
    } catch (error) {
      console.error('[WritingTask Store] 获取Agent配置失败:', error)
      throw error
    }
  }
  
  /**
   * 更新Agent配置
   * @param {Object} config - 配置数据
   * @returns {Promise<Object>} 更新后的配置
   */
  async function updateAgentConfig(config) {
    try {
      const res = await writingTaskApi.updateAgentConfig(config)
      agentConfig.value = res.data
      return res.data
    } catch (error) {
      console.error('[WritingTask Store] 更新Agent配置失败:', error)
      throw error
    }
  }
  
  /**
   * 重置Agent配置
   * @returns {Promise<Object>} 重置后的配置
   */
  async function resetAgentConfig() {
    try {
      const res = await writingTaskApi.resetAgentConfig()
      agentConfig.value = res.data
      return res.data
    } catch (error) {
      console.error('[WritingTask Store] 重置Agent配置失败:', error)
      throw error
    }
  }

  /**
   * 测试Agent模型连接
   * @param {Object} config - 测试配置 { model_id, provider }
   * @returns {Promise<Object>} 测试结果
   */
  async function testConnection(config) {
    try {
      const res = await writingTaskApi.testAgentConnection(config)
      // 后端返回格式: { data: { success: boolean, max_tokens: number, message: string }, message: "..." }
      return res.data?.data || res.data
    } catch (error) {
      console.error('[WritingTask Store] 测试连接失败:', error)
      throw error
    }
  }

  // ==================== WebSocket管理 ====================
  
  /**
   * 连接WebSocket
   * @param {string} taskId - 任务ID
   */
  function connectWS(taskId) {
    // 先断开现有连接
    disconnectWS()

    // 重置重连计数
    reconnectAttempts = 0

    wsConnection.value = connectWritingTaskWS(taskId, {
      onOpen: () => {
        console.log('[WritingTask Store] WebSocket连接成功')
        wsConnected.value = true
      },
      onMessage: handleMessage,
      onError: (error) => {
        console.error('[WritingTask Store] WebSocket错误:', error)
        wsConnected.value = false
      },
      onClose: () => {
        wsConnected.value = false
        handleWSClose(taskId)
      }
    })
  }

  /**
   * 处理WebSocket消息
   * @param {Object} msg - 消息数据
   * 
   * 消息类型(type)说明:
   * - status_change: 任务状态变更
   * - task_progress: 整体任务进度
   * - unit_progress: 单元进度
   * - scene_progress: 场景进度
   * - task_complete: 任务完成
   * - task_failed: 任务失败
   * - error: 错误消息
   * - statistics: 统计数据更新
   */
  function handleMessage(msg) {
    // 添加到消息队列
    progressMessages.value.push({
      ...msg,
      timestamp: Date.now()
    })
    
    // 限制消息队列长度
    if (progressMessages.value.length > 100) {
      progressMessages.value.shift()
    }
    
    // 根据消息类型更新状态
    switch (msg.type) {
      case 'status_change':
        // 状态变更
        if (currentTask.value) {
          // 支持两种消息格式
          const newStatus = msg.new_status || msg.data?.new_status
          currentTask.value.status = newStatus
          // 如果变为中断状态，断开WebSocket
          if (newStatus === 'interrupted') {
            console.log('[WritingTask Store] 任务已被中断')
            // 不立即断开，让用户有机会查看最终状态
          }
        }
        break
        
      case 'task_progress':
        // 整体任务进度
        if (currentTask.value) {
          currentTask.value.completed_units = msg.data?.completed_units ?? currentTask.value.completed_units
          currentTask.value.current_unit = msg.data?.current_unit ?? currentTask.value.current_unit
          currentTask.value.current_scene = msg.data?.current_scene ?? currentTask.value.current_scene
        }
        break
        
      case 'unit_progress':
        // 单元进度更新
        if (msg.data) {
          const unitIndex = msg.data.unit_index || msg.unit_index
          const unitStatus = msg.data.status || msg.status
          const unitProgress = msg.data.progress || msg.progress
          const unitWordCount = msg.data.word_count || msg.word_count
          
          // 更新或添加单元
          if (unitIndex !== undefined) {
            const existingUnit = units.value.find(u => u.unit_index === unitIndex)
            if (existingUnit) {
              existingUnit.status = unitStatus || existingUnit.status
              existingUnit.progress = unitProgress || existingUnit.progress
              if (unitWordCount !== undefined) {
                existingUnit.word_count = unitWordCount
              }
              // 更新单元标题
              if (msg.data.unit_title) {
                existingUnit.unit_title = msg.data.unit_title
              }
            } else {
              // 添加新单元
              units.value.push({
                unit_index: unitIndex,
                unit_title: msg.data.unit_title || msg.unit_title,
                status: unitStatus || 'processing',
                progress: unitProgress || 0,
                word_count: unitWordCount || 0
              })
            }
          }
        }
        break
        
      case 'scene_progress':
        // 场景进度更新
        if (msg.data) {
          const unitIdx = msg.data.unit_index || msg.unit_index
          const sceneIdx = msg.data.scene_index || msg.scene_index
          const sceneStatus = msg.data.status || msg.status
          
          if (unitIdx !== undefined && sceneIdx !== undefined) {
            // 确保该单元的场景数组存在
            if (!scenes.value[unitIdx]) {
              scenes.value[unitIdx] = []
            }
            
            // 更新或添加场景
            const existingScene = scenes.value[unitIdx].find(s => s.scene_index === sceneIdx)
            if (existingScene) {
              existingScene.status = sceneStatus || existingScene.status
            } else {
              scenes.value[unitIdx].push({
                scene_index: sceneIdx,
                scene_title: msg.data.scene_title || msg.scene_title,
                status: sceneStatus || 'pending'
              })
            }
          }
        }
        break
        
      case 'statistics':
        // 统计数据更新
        if (msg.stats || msg.data?.stats) {
          const statsData = msg.stats || msg.data.stats
          // 使用累加方式更新统计数据
          stats.value = {
            ...stats.value,
            ...statsData,
            // 确保 _summary 存在
            _summary: statsData._summary || statsData
          }
          // 同步更新currentTask中的统计数据（使用累计值）
          if (currentTask.value) {
            currentTask.value.total_tokens = statsData._summary?.total_tokens || statsData.total_tokens || currentTask.value.total_tokens || 0
            currentTask.value.total_cost = statsData._summary?.total_cost || statsData.total_cost || currentTask.value.total_cost || 0
          }
        }
        break
        
      case 'task_complete':
        // 任务完成
        if (currentTask.value) {
          currentTask.value.status = 'completed'
          currentTask.value.completed_at = new Date().toISOString()
          if (msg.data) {
            currentTask.value.total_word_count = msg.data.total_word_count
            currentTask.value.total_tokens = msg.data.total_tokens
            currentTask.value.total_cost = msg.data.total_cost
          }
        }
        disconnectWS()
        break
        
      case 'task_failed':
        // 任务失败
        if (currentTask.value) {
          currentTask.value.status = 'failed'
          currentTask.value.error = msg.data?.error || '未知错误'
        }
        disconnectWS()
        break
        
      case 'error':
        // 错误消息
        console.error('[WritingTask Store] 任务错误:', msg.data || msg.error_message)
        break
      
      case 'workflow_step':
        // 工作流步骤更新
        if (msg.data) {
          // 工作流步骤消息已经通过 progressMessages 记录
          // 这里可以添加额外的处理逻辑
          console.log('[WritingTask Store] 工作流步骤:', msg.data.step, msg.data.status, msg.data.message)
          // 如果步骤状态是error，可能是中断导致的
          if (msg.data.status === 'error' && msg.data.message?.includes('中断')) {
            if (currentTask.value) {
              currentTask.value.status = 'interrupted'
            }
          }
        }
        break
        
      default:
        // 未知消息类型，记录但不处理
        console.warn('[WritingTask Store] 未知消息类型:', msg.type, msg)
    }
  }
  
  /**
   * 处理WebSocket关闭
   * @param {string} taskId - 任务ID
   */
  function handleWSClose(taskId) {
    // 清除连接引用
    wsConnection.value = null
    
    // 检查是否需要重连
    if (currentTask.value?.status === 'running' && reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
      console.log(`[WritingTask Store] 尝试重连 (${reconnectAttempts + 1}/${MAX_RECONNECT_ATTEMPTS})...`)
      
      // 清除旧的重连定时器
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
      }
      
      // 设置重连定时器
      reconnectTimer = setTimeout(() => {
        reconnectAttempts++
        connectWS(taskId)
      }, RECONNECT_DELAY)
    } else if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      console.warn('[WritingTask Store] 达到最大重连次数，停止重连')
    }
  }
  
  /**
   * 断开WebSocket连接
   */
  function disconnectWS() {
    // 清除重连定时器
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    
    if (wsConnection.value) {
      wsConnection.value.close()
      wsConnection.value = null
    }
  }
  
  /**
   * 清除进度消息
   */
  function clearProgress() {
    progressMessages.value = []
  }
  
  /**
   * 重置Store状态
   */
  function $reset() {
    currentTask.value = null
    taskList.value = []
    units.value = []
    scenes.value = {}
    stats.value = null
    progressMessages.value = []
    reconnectAttempts = 0
    disconnectWS()
  }
  
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
    formattedDuration,

    // Actions
    createTask,
    fetchTask,
    fetchCurrentTask,
    fetchTaskList,
    interruptTask,
    resumeTask,
    continueTask,
    fetchUnits,
    fetchScenes,
    fetchStats,
    deleteTask,
    fetchAgentConfig,
    updateAgentConfig,
    resetAgentConfig,
    testConnection,
    connectWS,
    disconnectWS,
    disconnectWebSocket: disconnectWS,
    clearProgress,
    $reset
  }
})
