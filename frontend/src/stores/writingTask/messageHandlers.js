/**
 * 多Agent协作文学作品生成系统 - 写作任务状态管理（WebSocket消息处理部分）
 *
 * 模块: writing-engine
 * 文件: writingTask/messageHandlers.js
 * 功能: 按消息类型分发处理WebSocket消息并更新任务状态，
 *       从websocket.js拆分而来，业务逻辑保持一致
 *
 * 消息类型(type)说明:
 * - status_change: 任务状态变更
 * - task_progress: 整体任务进度
 * - unit_progress: 单元进度
 * - scene_progress: 场景进度
 * - task_complete: 任务完成（终态，带终态锁只处理一次）
 * - task_failed: 任务失败（终态，带终态锁只处理一次）
 * - error: 错误消息
 * - statistics: 统计数据更新
 * - workflow_step: 工作流步骤更新
 * - unit_quality_control / content_qc_*: 质控消息（见qcMessageHandlers.js）
 * - consistency_report_update: 一致性报告实时更新
 * - writing_hints: 规则引擎实时提示
 *
 * 创建时间: 2026-07-18（自websocket.js拆分）
 */

import {
  applyUnitQualityControl,
  applyContentQcStarted,
  applyContentQcProgress,
  applyContentQcUnitComplete,
  applyContentQcBatchComplete
} from './qcMessageHandlers'

/** 消息队列长度上限 */
const PROGRESS_MESSAGE_LIMIT = 100

/**
 * 创建WebSocket消息处理器
 * @param {Object} state - 写作任务状态引用集合
 * @param {Object} hooks - { onTerminal: 终态时回调（负责断开连接） }
 * @returns {{ handleMessage: Function, resetTerminalLock: Function }}
 */
export function createWSMessageHandler(state, hooks = {}) {
  const { onTerminal = () => {} } = hooks

  /**
   * 终态锁：task_complete/task_failed 只处理第一个到达的终态消息，
   * 后续终态消息直接丢弃，保证终态只触发一次状态写入与连接关闭
   */
  let terminalHandled = false

  function resetTerminalLock() {
    terminalHandled = false
  }

  function handleMessage(msg) {
    appendProgressMessage(msg)
    dispatchMessage(msg)
  }

  function appendProgressMessage(msg) {
    state.progressMessages.value.push({
      ...msg,
      timestamp: Date.now()
    })
    if (state.progressMessages.value.length > PROGRESS_MESSAGE_LIMIT) {
      state.progressMessages.value.shift()
    }
  }

  function dispatchMessage(msg) {
    switch (msg.type) {
      case 'status_change':
        applyStatusChange(msg)
        break
      case 'task_progress':
        applyTaskProgress(msg)
        break
      case 'unit_progress':
        applyUnitProgress(msg)
        break
      case 'scene_progress':
        applySceneProgress(msg)
        break
      case 'statistics':
        applyStatistics(msg)
        break
      case 'task_complete':
        applyTaskComplete(msg)
        break
      case 'task_failed':
        applyTaskFailed(msg)
        break
      case 'error':
        console.error('[WritingTask Store] 任务错误:', msg.data || msg.error_message)
        break
      case 'workflow_step':
        applyWorkflowStep(msg)
        break
      case 'unit_quality_control':
        applyUnitQualityControl(state, msg.data)
        break
      case 'content_qc_started':
        applyContentQcStarted(state, msg.data)
        break
      case 'content_qc_progress':
        applyContentQcProgress(state, msg.data)
        break
      case 'content_qc_unit_complete':
        applyContentQcUnitComplete(state, msg.data)
        break
      case 'content_qc_batch_complete':
        applyContentQcBatchComplete(state, msg.data)
        break
      case 'consistency_report_update':
        applyConsistencyReport(msg)
        break
      case 'writing_hints':
        applyWritingHints(msg)
        break
      default:
        // 未知消息类型，记录但不处理
        console.warn('[WritingTask Store] 未知消息类型:', msg.type, msg)
    }
  }

  function applyStatusChange(msg) {
    if (!state.currentTask.value) return
    // 支持两种消息格式
    const newStatus = msg.new_status || msg.data?.new_status
    state.currentTask.value.status = newStatus
    if (newStatus === 'interrupted') {
      console.log('[WritingTask Store] 任务已被中断')
    }
  }

  function applyTaskProgress(msg) {
    if (!state.currentTask.value) return
    state.currentTask.value.completed_units = msg.data?.completed_units ?? state.currentTask.value.completed_units
    state.currentTask.value.current_unit = msg.data?.current_unit ?? state.currentTask.value.current_unit
    state.currentTask.value.current_scene = msg.data?.current_scene ?? state.currentTask.value.current_scene
  }

  function applyUnitProgress(msg) {
    if (!msg.data) return
    const unitIndex = msg.data.unit_index || msg.unit_index
    const unitStatus = msg.data.status || msg.status
    const unitProgress = msg.data.progress || msg.progress
    const unitWordCount = msg.data.word_count || msg.word_count
    if (unitIndex === undefined) return

    const existingUnit = state.units.value.find(u => u.unit_index === unitIndex)
    if (existingUnit) {
      existingUnit.status = unitStatus || existingUnit.status
      existingUnit.progress = unitProgress || existingUnit.progress
      if (unitWordCount !== undefined) {
        existingUnit.word_count = unitWordCount
      }
      if (msg.data.unit_title) {
        existingUnit.unit_title = msg.data.unit_title
      }
    } else {
      state.units.value.push({
        unit_index: unitIndex,
        unit_title: msg.data.unit_title || msg.unit_title,
        status: unitStatus || 'processing',
        progress: unitProgress || 0,
        word_count: unitWordCount || 0
      })
    }
  }

  function applySceneProgress(msg) {
    if (!msg.data) return
    const unitIdx = msg.data.unit_index || msg.unit_index
    const sceneIdx = msg.data.scene_index || msg.scene_index
    const sceneStatus = msg.data.status || msg.status
    if (unitIdx === undefined || sceneIdx === undefined) return

    if (!state.scenes.value[unitIdx]) {
      state.scenes.value[unitIdx] = []
    }
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

  function applyStatistics(msg) {
    if (!(msg.stats || msg.data?.stats)) return
    const statsData = msg.stats || msg.data.stats
    // 使用累加方式更新统计数据
    state.stats.value = {
      ...state.stats.value,
      ...statsData,
      _summary: statsData._summary || statsData
    }
    // 同步更新currentTask中的统计数据（使用累计值）
    if (state.currentTask.value) {
      state.currentTask.value.total_tokens = statsData._summary?.total_tokens || statsData.total_tokens || state.currentTask.value.total_tokens || 0
      state.currentTask.value.total_cost = statsData._summary?.total_cost || statsData.total_cost || state.currentTask.value.total_cost || 0
    }
  }

  function applyTaskComplete(msg) {
    if (terminalHandled) {
      console.log('[WritingTask Store] 终态已处理，丢弃重复的task_complete消息')
      return
    }
    terminalHandled = true
    if (state.currentTask.value) {
      state.currentTask.value.status = 'completed'
      state.currentTask.value.completed_at = new Date().toISOString()
      if (msg.data) {
        state.currentTask.value.total_word_count = msg.data.total_word_count
        state.currentTask.value.total_tokens = msg.data.total_tokens
        state.currentTask.value.total_cost = msg.data.total_cost
      }
    }
    onTerminal()
  }

  function applyTaskFailed(msg) {
    if (terminalHandled) {
      console.log('[WritingTask Store] 终态已处理，丢弃重复的task_failed消息')
      return
    }
    terminalHandled = true
    if (state.currentTask.value) {
      state.currentTask.value.status = 'failed'
      state.currentTask.value.error = msg.data?.error || '未知错误'
    }
    onTerminal()
  }

  function applyWorkflowStep(msg) {
    if (!msg.data) return
    console.log('[WritingTask Store] 工作流步骤:', msg.data.step, msg.data.status, msg.data.message)
    // 如果步骤状态是error，可能是中断导致的
    if (msg.data.status === 'error' && msg.data.message?.includes('中断')) {
      if (state.currentTask.value) {
        state.currentTask.value.status = 'interrupted'
      }
    }
  }

  function applyConsistencyReport(msg) {
    if (!msg.data) return
    state.consistencyReport.value = {
      ...msg.data,
      _updatedAt: Date.now()
    }
    console.log(
      '[WritingTask Store] 一致性报告实时更新: chapter=%d, events=%d, items=%d, facilities=%d',
      msg.data.chapter_num,
      Object.keys(msg.data.events || {}).length,
      Object.keys(msg.data.items || {}).length,
      Object.keys(msg.data.facilities || {}).length
    )
  }

  function applyWritingHints(msg) {
    if (!msg.data) return
    const unitIndex = msg.data.unit_index
    const hints = msg.data.hints || []
    console.log('[WritingTask Store] 写作提示: unit=%d, hints=%d', unitIndex, hints.length)

    const unitIdx = state.units.value.findIndex(u => u.unit_index === unitIndex)
    if (unitIdx !== -1) {
      const oldUnit = state.units.value[unitIdx]
      state.units.value.splice(unitIdx, 1, {
        ...oldUnit,
        writing_hints: hints,
        _hints_updated_at: Date.now()
      })
    }
  }

  return {
    handleMessage,
    resetTerminalLock
  }
}
