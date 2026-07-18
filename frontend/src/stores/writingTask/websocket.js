/**
 * 多Agent协作文学作品生成系统 - 写作任务状态管理（WebSocket生命周期部分）
 *
 * 模块: writing-engine
 * 文件: writingTask/websocket.js
 * 功能: 管理WebSocket连接生命周期：连接、主动断开、指数退避重连、
 *       浏览器离线/恢复感知与连接状态机（WS_STATUS）
 *
 * 生命周期规则（阶段03修复）:
 * - manualClose: 主动断开后close回调不得调度重连
 * - connectionGeneration: 每次connect递增，过期连接的open/message/error/close回调不得改变当前状态
 * - 重连延迟: 指数退避加0.8~1.2抖动，最终值封顶 MAX_RECONNECT_DELAY(30秒)
 * - offline/online: 离线立即进入offline状态并暂停重连；恢复在线且任务运行中时只调度一次立即重连
 * - 消息处理逻辑见 messageHandlers.js / qcMessageHandlers.js
 *
 * 创建时间: 2026-03-27
 * 最后修改: 2026-07-18
 */

import { connectWritingTaskWS } from '@/api/writing-task'
import { WS_STATUS } from './state'
import { createWSMessageHandler } from './messageHandlers'

/** 基础重连延迟（毫秒） */
export const BASE_RECONNECT_DELAY = 3000

/** 重连延迟上限（毫秒），任何抖动后的延迟不得超过该值 */
export const MAX_RECONNECT_DELAY = 30000

/** 最大重连次数，超过后进入failed状态等待手动重试 */
export const MAX_RECONNECT_ATTEMPTS = 5

/**
 * WebSocket连接生命周期管理
 * @param {Object} state - useWritingTaskState() 返回的状态引用集合
 * @param {Object} dependencies - 可注入依赖（单元测试用）:
 *   wsFactory(taskId, callbacks) / setTimeoutFn / clearTimeoutFn / randomFn / windowRef
 */
export function useWritingTaskWebSocket(state, dependencies = {}) {
  const {
    wsFactory = connectWritingTaskWS,
    setTimeoutFn = (...args) => setTimeout(...args),
    clearTimeoutFn = (timerId) => clearTimeout(timerId),
    randomFn = Math.random,
    windowRef = typeof window !== 'undefined' ? window : null
  } = dependencies

  /** WebSocket重连定时器 */
  let reconnectTimer = null

  /** 当前重连次数 */
  let reconnectAttempts = 0

  /** 主动关闭标记：置位后close回调不得调度重连 */
  let manualClose = false

  /** 连接代次：每次connect递增，过期回调按代次丢弃 */
  let connectionGeneration = 0

  /** 最近一次连接的任务ID（离线恢复与手动重试使用） */
  let lastTaskId = null

  /** online/offline监听是否已注册 */
  let networkListenersAttached = false

  const { handleMessage } = createWSMessageHandler(state, {
    onTerminal: () => disconnectWS()
  })

  // ==================== 重连延迟 ====================

  /**
   * 计算第attempts次重连的延迟：指数退避加0.8~1.2抖动，封顶30秒
   * @param {number} attempts - 已重连次数（从0开始）
   * @returns {number} 延迟毫秒数（严格小于等于 MAX_RECONNECT_DELAY）
   */
  function getReconnectDelay(attempts) {
    const baseDelay = BASE_RECONNECT_DELAY * Math.pow(2, attempts)
    const jittered = baseDelay * (0.8 + randomFn() * 0.4)
    return Math.min(MAX_RECONNECT_DELAY, Math.round(jittered))
  }

  // ==================== 内部判定 ====================

  function isStaleGeneration(generation) {
    return generation !== connectionGeneration
  }

  function isTaskRunning() {
    return state.currentTask.value?.status === 'running'
  }

  function isBrowserOffline() {
    return windowRef?.navigator?.onLine === false
  }

  // ==================== 浏览器网络事件 ====================

  function handleBrowserOffline() {
    // 离线立即暂停重连，等待online事件恢复
    clearReconnectTimer()
    const status = state.wsStatus.value
    if (status === WS_STATUS.IDLE || status === WS_STATUS.CLOSED) return
    state.wsStatus.value = WS_STATUS.OFFLINE
  }

  function handleBrowserOnline() {
    if (manualClose || !lastTaskId) return
    if (state.wsStatus.value !== WS_STATUS.OFFLINE) return
    if (!isTaskRunning()) {
      state.wsStatus.value = WS_STATUS.CLOSED
      return
    }
    // 恢复在线且任务仍运行：只调度一次立即重连
    reconnectAttempts = 0
    connectWS(lastTaskId)
  }

  function attachNetworkListeners() {
    if (!windowRef || networkListenersAttached) return
    windowRef.addEventListener('offline', handleBrowserOffline)
    windowRef.addEventListener('online', handleBrowserOnline)
    networkListenersAttached = true
  }

  function removeNetworkListeners() {
    if (!windowRef || !networkListenersAttached) return
    windowRef.removeEventListener('offline', handleBrowserOffline)
    windowRef.removeEventListener('online', handleBrowserOnline)
    networkListenersAttached = false
  }

  // ==================== 连接管理 ====================

  function clearReconnectTimer() {
    if (reconnectTimer) {
      clearTimeoutFn(reconnectTimer)
      reconnectTimer = null
    }
  }

  /** 关闭并释放当前socket（先摘除引用，旧socket回调由代次守卫丢弃） */
  function closeActiveSocket() {
    const socket = state.wsConnection.value
    state.wsConnection.value = null
    if (socket) {
      try {
        socket.close()
      } catch (closeError) {
        console.warn('[WritingTask Store] 关闭WebSocket异常:', closeError)
      }
    }
  }

  /**
   * 连接WebSocket
   * @param {string|number} taskId - 任务ID
   */
  function connectWS(taskId) {
    // 任务ID改变时视为全新连接：重置重试计数与终态锁
    if (lastTaskId !== null && lastTaskId !== taskId) {
      reconnectAttempts = 0
    }
    // 先完整清理旧连接：代次递增使旧回调全部过期
    connectionGeneration += 1
    const generation = connectionGeneration
    clearReconnectTimer()
    closeActiveSocket()

    manualClose = false
    lastTaskId = taskId
    attachNetworkListeners()

    state.wsStatus.value = reconnectAttempts > 0 ? WS_STATUS.RECONNECTING : WS_STATUS.CONNECTING

    state.wsConnection.value = wsFactory(taskId, {
      onOpen: () => {
        if (isStaleGeneration(generation)) return
        console.log('[WritingTask Store] WebSocket连接成功')
        // 连接成功后重置重试次数
        reconnectAttempts = 0
        state.wsStatus.value = WS_STATUS.CONNECTED
      },
      onMessage: (msg) => {
        if (isStaleGeneration(generation)) return
        state.wsLastMessageAt.value = Date.now()
        handleMessage(msg)
      },
      onError: (error) => {
        if (isStaleGeneration(generation)) return
        // 状态迁移交由随后的close事件统一处理
        console.error('[WritingTask Store] WebSocket错误:', error)
      },
      onClose: () => {
        if (isStaleGeneration(generation)) return
        handleWSClose(taskId)
      }
    })
  }

  /**
   * 处理非过期连接的close事件：
   * 按 manualClose → 浏览器离线 → 任务非运行 → 重试上限 的顺序决定去向
   */
  function handleWSClose(taskId) {
    state.wsConnection.value = null

    if (manualClose) {
      state.wsStatus.value = WS_STATUS.CLOSED
      return
    }
    if (isBrowserOffline()) {
      // 离线由online事件负责恢复，不做定时重连
      state.wsStatus.value = WS_STATUS.OFFLINE
      return
    }
    if (!isTaskRunning()) {
      state.wsStatus.value = WS_STATUS.CLOSED
      return
    }
    if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
      console.warn('[WritingTask Store] 达到最大重连次数，等待手动重试')
      state.wsStatus.value = WS_STATUS.FAILED
      return
    }
    scheduleReconnect(taskId)
  }

  /** 调度一次指数退避重连（已有定时器时跳过，防重复调度） */
  function scheduleReconnect(taskId) {
    if (reconnectTimer) return
    const delay = getReconnectDelay(reconnectAttempts)
    reconnectAttempts += 1
    state.wsStatus.value = WS_STATUS.RECONNECTING
    console.log(`[WritingTask Store] 将在 ${delay}ms 后尝试第 ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS} 次重连`)
    reconnectTimer = setTimeoutFn(() => {
      reconnectTimer = null
      connectWS(taskId)
    }, delay)
  }

  /**
   * 主动断开WebSocket
   * 顺序：置manualClose → 代次过期 → 清重连定时器 → 移除网络监听 → 关闭socket
   */
  function disconnectWS() {
    manualClose = true
    connectionGeneration += 1
    clearReconnectTimer()
    removeNetworkListeners()
    closeActiveSocket()
    reconnectAttempts = 0
    if (state.wsStatus.value !== WS_STATUS.IDLE) {
      state.wsStatus.value = WS_STATUS.CLOSED
    }
  }

  /**
   * 手动重试：failed/offline/closed状态下重新建立连接并清零重试计数
   */
  function retryConnection() {
    if (!lastTaskId) return
    reconnectAttempts = 0
    connectWS(lastTaskId)
  }

  return {
    connectWS,
    disconnectWS,
    retryConnection,
    getReconnectDelay
  }
}
