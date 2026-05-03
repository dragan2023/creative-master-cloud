/**
 * 多Agent协作文学作品生成系统 - 写作任务状态管理（主入口）
 * 
 * 模块: writing-engine
 * 文件: writingTask.js
 * 功能: 写作任务的Pinia状态管理，组合各子模块
 * 
 * 依赖关系:
 *   - state.js: 状态和计算属性
 *   - actions.js: 操作方法
 *   - websocket.js: WebSocket连接管理
 * 
 * 创建时间: 2026-03-27
 * 最后修改: 2026-04-26
 * 
 * 版本: 2.0.0 (已拆分为子模块)
 */

import { defineStore } from 'pinia'
import { useWritingTaskState } from './writingTask/state'
import { useWritingTaskActions } from './writingTask/actions'
import { useWritingTaskWebSocket } from './writingTask/websocket'

export const useWritingTaskStore = defineStore('writingTask', () => {
  // 初始化状态模块
  const state = useWritingTaskState()
  
  // 初始化WebSocket模块（需要状态引用）
  const { connectWS, disconnectWS } = useWritingTaskWebSocket(state)
  
  // 初始化动作模块（需要状态和WebSocket方法）
  const actions = useWritingTaskActions(state, connectWS, disconnectWS)
  
  return {
    // 状态（从state模块展开）
    ...Object.fromEntries(
      Object.entries(state)
        .filter(([_, v]) => typeof v !== 'function')
        .map(([k, v]) => [k, v])
    ),
    // 计算属性（从state模块展开）
    ...Object.fromEntries(
      Object.entries(state)
        .filter(([_, v]) => typeof v !== 'function' && v?.__v_isRef === undefined)
        .map(([k, v]) => [k, v])
    ),
    // 动作（从actions模块展开）
    ...actions,
    // WebSocket方法
    connectWS,
    disconnectWS,
    disconnectWebSocket: disconnectWS
  }
})
