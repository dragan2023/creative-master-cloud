/**
 * 多Agent协作文学作品生成系统 - 写作任务状态管理（WebSocket部分）
 * 
 * 模块: writing-engine
 * 文件: writingTask/websocket.js
 * 功能: 管理WebSocket连接、消息处理和重连逻辑
 * 
 * 创建时间: 2026-03-27
 * 最后修改: 2026-04-26
 */

import { connectWritingTaskWS } from '@/api/writing-task'

export function useWritingTaskWebSocket(state) {
  /** WebSocket重连定时器 */
  let reconnectTimer = null
  
  /** 基础重连延迟（毫秒） */
  const BASE_RECONNECT_DELAY = 3000
  
  /** 最大重连延迟（毫秒） */
  const MAX_RECONNECT_DELAY = 60000
  
  /** 最大重连次数 */
  const MAX_RECONNECT_ATTEMPTS = 5
  
  /** 当前重连次数 */
  let reconnectAttempts = 0
  
  /** 防止重复重连的锁 */
  let isReconnecting = false

  // ==================== WebSocket管理 ====================
  
  /**
   * 连接WebSocket
   * @param {string} taskId - 任务ID
   */
  function connectWS(taskId) {
    // 先断开现有连接
    disconnectWS()

    // 重置重连计数（仅在首次连接时）
    if (reconnectAttempts === 0) {
      isReconnecting = false
    }

    state.wsConnection.value = connectWritingTaskWS(taskId, {
      onOpen: () => {
        console.log('[WritingTask Store] WebSocket连接成功')
        state.wsConnected.value = true
      },
      onMessage: handleMessage,
      onError: (error) => {
        console.error('[WritingTask Store] WebSocket错误:', error)
        state.wsConnected.value = false
      },
      onClose: () => {
        state.wsConnected.value = false
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
    state.progressMessages.value.push({
      ...msg,
      timestamp: Date.now()
    })
    
    // 限制消息队列长度
    if (state.progressMessages.value.length > 100) {
      state.progressMessages.value.shift()
    }
    
    // 根据消息类型更新状态
    switch (msg.type) {
      case 'status_change':
        // 状态变更
        if (state.currentTask.value) {
          // 支持两种消息格式
          const newStatus = msg.new_status || msg.data?.new_status
          state.currentTask.value.status = newStatus
          // 如果变为中断状态，断开WebSocket
          if (newStatus === 'interrupted') {
            console.log('[WritingTask Store] 任务已被中断')
          }
        }
        break
        
      case 'task_progress':
        // 整体任务进度
        if (state.currentTask.value) {
          state.currentTask.value.completed_units = msg.data?.completed_units ?? state.currentTask.value.completed_units
          state.currentTask.value.current_unit = msg.data?.current_unit ?? state.currentTask.value.current_unit
          state.currentTask.value.current_scene = msg.data?.current_scene ?? state.currentTask.value.current_scene
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
            const existingUnit = state.units.value.find(u => u.unit_index === unitIndex)
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
              state.units.value.push({
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
            if (!state.scenes.value[unitIdx]) {
              state.scenes.value[unitIdx] = []
            }
            
            // 更新或添加场景
            const existingScene = state.scenes.value[unitIdx].find(s => s.scene_index === sceneIdx)
            if (existingScene) {
              existingScene.status = sceneStatus || existingScene.status
            } else {
              state.scenes.value[unitIdx].push({
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
          state.stats.value = {
            ...state.stats.value,
            ...statsData,
            // 确保 _summary 存在
            _summary: statsData._summary || statsData
          }
          // 同步更新currentTask中的统计数据（使用累计值）
          if (state.currentTask.value) {
            state.currentTask.value.total_tokens = statsData._summary?.total_tokens || statsData.total_tokens || state.currentTask.value.total_tokens || 0
            state.currentTask.value.total_cost = statsData._summary?.total_cost || statsData.total_cost || state.currentTask.value.total_cost || 0
          }
        }
        break
        
      case 'task_complete':
        // 任务完成
        if (state.currentTask.value) {
          state.currentTask.value.status = 'completed'
          state.currentTask.value.completed_at = new Date().toISOString()
          if (msg.data) {
            state.currentTask.value.total_word_count = msg.data.total_word_count
            state.currentTask.value.total_tokens = msg.data.total_tokens
            state.currentTask.value.total_cost = msg.data.total_cost
          }
        }
        disconnectWS()
        break
        
      case 'task_failed':
        // 任务失败
        if (state.currentTask.value) {
          state.currentTask.value.status = 'failed'
          state.currentTask.value.error = msg.data?.error || '未知错误'
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
          console.log('[WritingTask Store] 工作流步骤:', msg.data.step, msg.data.status, msg.data.message)
          // 如果步骤状态是error，可能是中断导致的
          if (msg.data.status === 'error' && msg.data.message?.includes('中断')) {
            if (state.currentTask.value) {
              state.currentTask.value.status = 'interrupted'
            }
          }
        }
        break
        
      case 'unit_quality_control':
        // 单元质控状态更新（v2.0新增 - 实时质控）
        console.log('[WritingTask Store] 收到unit_quality_control消息:', JSON.stringify(msg.data).substring(0, 200))
        
        if (msg.data) {
          const unitIndex = msg.data.unit_index
          const qcData = msg.data
          
          // 更新单元的质控信息
          const unitIdx = state.units.value.findIndex(u => u.unit_index === unitIndex)
          console.log('[WritingTask Store] 查找单元:', unitIndex, '找到索引:', unitIdx)
          
          if (unitIdx !== -1) {
            // 使用splice替换整个对象，确保Vue响应式系统能可靠检测到变化
            const oldUnit = state.units.value[unitIdx]
            const updatedUnit = {
              ...oldUnit,
              quality_control: {
                status: qcData.status,
                score: qcData.score || 0,
                issues_count: qcData.issues_count || 0,
                fixed_count: qcData.fixed_count || 0,
                message: qcData.message || '',
                report: qcData.report || null,
                issues: qcData.issues || [],
                fixes_applied: qcData.fixes_applied || [],
                original_content: qcData.original_content || null,
                fixed_content: qcData.fixed_content || null,
                updated_at: Date.now(),
                _from_ws: true  // 标记数据来自WebSocket，优先级高于API数据
              }
            }
            state.units.value.splice(unitIdx, 1, updatedUnit)
            console.log('[WritingTask Store] 单元质控信息已更新(splice):', updatedUnit.quality_control)
          } else {
            // 单元尚未在列表中(可能unit_progress消息还未到达)，创建一个带质控信息的单元
            console.log('[WritingTask Store] 单元未找到，创建带质控信息的新单元:', unitIndex)
            state.units.value.push({
              unit_index: unitIndex,
              unit_title: qcData.unit_title || `第${unitIndex}章`,
              status: qcData.status === 'running' ? 'processing' : 'completed',
              progress: qcData.status === 'running' ? 0 : 100,
              word_count: 0,
              quality_control: {
                status: qcData.status,
                score: qcData.score || 0,
                issues_count: qcData.issues_count || 0,
                fixed_count: qcData.fixed_count || 0,
                message: qcData.message || '',
                report: qcData.report || null,
                issues: qcData.issues || [],
                fixes_applied: qcData.fixes_applied || [],
                original_content: qcData.original_content || null,
                fixed_content: qcData.fixed_content || null,
                updated_at: Date.now(),
                _from_ws: true  // 标记数据来自WebSocket
              }
            })
          }
          
          console.log(
            `[WritingTask Store] 单元质控更新完成: unit=${unitIndex}, ` +
            `status=${qcData.status}, score=${qcData.score || 0}, ` +
            `units总数=${state.units.value.length}`
          )
        }
        break
        
      // ==================== v2.2新增：批量质控进度消息 ====================
      case 'content_qc_started':
        // 批量质控开始
        console.log('[WritingTask Store] 批量质控开始:', msg.data)
        if (msg.data && state.batchQCProgress) {
          state.batchQCProgress.value = {
            status: 'running',
            current: 0,
            total: msg.data.total || 0,
            currentUnit: null,
            startedAt: Date.now()
          }
        }
        break
        
      case 'content_qc_progress':
        // 批量质控进度更新
        console.log('[WritingTask Store] 批量质控进度:', msg.data)
        if (msg.data && state.batchQCProgress) {
          const progressData = msg.data
          state.batchQCProgress.value = {
            status: 'running',
            current: progressData.current || 0,
            total: progressData.total || state.batchQCProgress.value?.total || 0,
            currentUnit: progressData.current_unit,
            percent: progressData.progress || Math.round((progressData.current / progressData.total) * 100)
          }
          
          // 更新当前单元的质控状态为running
          if (progressData.current_unit) {
            const unitIdx = state.units.value.findIndex(u => u.unit_index === progressData.current_unit)
            if (unitIdx !== -1) {
              const oldUnit = state.units.value[unitIdx]
              state.units.value.splice(unitIdx, 1, {
                ...oldUnit,
                quality_control: {
                  ...oldUnit.quality_control,
                  status: 'running',
                  updated_at: Date.now(),
                  _from_ws: true
                }
              })
            }
          }
        }
        break
        
      case 'content_qc_unit_complete':
        // 单单元质控完成（批量任务中的单个单元）
        console.log('[WritingTask Store] 批量任务单元质控完成:', msg.data)
        if (msg.data) {
          const unitIndex = msg.data.unit_index || msg.data.data?.unit_index
          const status = msg.data.status || 'success'
          
          const unitIdx = state.units.value.findIndex(u => u.unit_index === unitIndex)
          if (unitIdx !== -1) {
            const oldUnit = state.units.value[unitIdx]
            const qcUpdate = {
              status: status === 'success' ? 'completed' : 'failed',
              updated_at: Date.now(),
              _from_ws: true
            }
            
            if (status === 'success') {
              qcUpdate.score = msg.data.score || msg.data.data?.score || 0
              qcUpdate.issues_count = msg.data.issues_count || msg.data.data?.issues_count || 0
              qcUpdate.fixed_count = msg.data.fixed_count || msg.data.data?.fixed_count || 0
            }
            
            state.units.value.splice(unitIdx, 1, {
              ...oldUnit,
              quality_control: {
                ...oldUnit.quality_control,
                ...qcUpdate
              }
            })
          }
        }
        break
        
      case 'content_qc_batch_complete':
        // 批量质控完成
        console.log('[WritingTask Store] 批量质控完成:', msg.data)
        if (state.batchQCProgress) {
          const summaryData = msg.data || msg.data?.data || {}
          state.batchQCProgress.value = {
            status: 'completed',
            current: summaryData.completed || summaryData.total || 0,
            total: summaryData.total || 0,
            currentUnit: null,
            completedUnits: summaryData.completed_units || [],
            failedUnits: summaryData.failed_units || [],
            avgScore: summaryData.avg_score || 0,
            completedAt: Date.now()
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
    state.wsConnection.value = null
    
    // 防止重复重连
    if (isReconnecting) {
      console.log('[WritingTask Store] 已在重连中，跳过重复请求')
      return
    }
    
    // 检查是否需要重连
    if (state.currentTask.value?.status === 'running' && reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
      isReconnecting = true
      
      // 清除旧的重连定时器
      if (reconnectTimer) {
        clearTimeout(reconnectTimer)
        reconnectTimer = null
      }
      
      // 指数退避策略: 3s, 6s, 12s, 24s, 48s（最大60s）
      const delay = Math.min(
        BASE_RECONNECT_DELAY * Math.pow(2, reconnectAttempts),
        MAX_RECONNECT_DELAY
      )
      
      console.log(`[WritingTask Store] 将在 ${delay/1000}秒后尝试重连 (${reconnectAttempts + 1}/${MAX_RECONNECT_ATTEMPTS})...`)
      
      // 设置重连定时器
      reconnectTimer = setTimeout(() => {
        reconnectAttempts++
        isReconnecting = false
        reconnectTimer = null
        connectWS(taskId)
      }, delay)
    } else if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      console.warn('[WritingTask Store] 达到最大重连次数，停止重连')
      isReconnecting = false
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
    
    if (state.wsConnection.value) {
      state.wsConnection.value.close()
      state.wsConnection.value = null
    }
  }

  return {
    connectWS,
    disconnectWS
  }
}
