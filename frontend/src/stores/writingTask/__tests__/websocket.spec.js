/**
 * WebSocket生命周期确定性单元测试（阶段03 §3.4）
 *
 * 使用可控FakeWebSocket与假定时器覆盖七类场景：
 * 1. 主动disconnectWS后触发close，不创建新WebSocket
 * 2. 非主动断开按指数退避重连，最大延迟不超过30000ms（random=1）
 * 3. 离线15秒期间不重连，online事件只创建一个连接
 * 4. 旧连接晚到的message/close不覆盖新连接状态
 * 5. 任务切换、主动断开、终态完成都清理timer/listener/socket
 * 6. 两个终态来源同时到达只处理一次（终态锁）
 * 7. 手动重试从failed进入connecting，成功后connected且重试计数清零
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { useWritingTaskState, WS_STATUS } from '../state'
import {
  useWritingTaskWebSocket,
  MAX_RECONNECT_ATTEMPTS,
  MAX_RECONNECT_DELAY
} from '../websocket'
import { createWSMessageHandler } from '../messageHandlers'

/** 可控的假WebSocket：手动触发open/message/close/error回调 */
class FakeWebSocket {
  constructor(taskId, callbacks) {
    this.taskId = taskId
    this.callbacks = callbacks
    this.closed = false
  }

  close() {
    this.closed = true
  }

  fireOpen() {
    this.callbacks.onOpen?.()
  }

  fireMessage(msg) {
    this.callbacks.onMessage?.(msg)
  }

  fireClose() {
    this.callbacks.onClose?.()
  }

  fireError(error) {
    this.callbacks.onError?.(error)
  }
}

/** 可控的假window：online/offline事件与navigator.onLine */
function createFakeWindow({ onLine = true } = {}) {
  const listeners = { online: new Set(), offline: new Set() }
  return {
    navigator: { onLine },
    addEventListener(type, handler) {
      listeners[type]?.add(handler)
    },
    removeEventListener(type, handler) {
      listeners[type]?.delete(handler)
    },
    dispatch(type) {
      listeners[type]?.forEach((handler) => handler())
    },
    listenerCount(type) {
      return listeners[type]?.size ?? 0
    },
    setOnline(isOnline) {
      this.navigator.onLine = isOnline
    }
  }
}

/** 构造被测环境：真实state + 注入FakeWebSocket工厂/假window/固定random */
function createHarness({ random = () => 0.5, onLine = true } = {}) {
  const state = useWritingTaskState()
  state.currentTask.value = { id: 1, status: 'running' }
  const fakeWindow = createFakeWindow({ onLine })
  const sockets = []
  const wsFactory = vi.fn((taskId, callbacks) => {
    const socket = new FakeWebSocket(taskId, callbacks)
    sockets.push(socket)
    return socket
  })
  const ws = useWritingTaskWebSocket(state, {
    wsFactory,
    randomFn: random,
    windowRef: fakeWindow
  })
  return { state, ws, sockets, wsFactory, fakeWindow }
}

beforeEach(() => {
  vi.useFakeTimers()
  vi.spyOn(console, 'log').mockImplementation(() => {})
  vi.spyOn(console, 'warn').mockImplementation(() => {})
  vi.spyOn(console, 'error').mockImplementation(() => {})
})

afterEach(() => {
  vi.useRealTimers()
  vi.restoreAllMocks()
})

describe('场景1：主动断开', () => {
  it('主动disconnectWS后触发close，不创建新WebSocket且状态为closed', () => {
    const { ws, sockets, wsFactory, state } = createHarness()
    ws.connectWS(1)
    sockets[0].fireOpen()
    expect(state.wsStatus.value).toBe(WS_STATUS.CONNECTED)
    expect(state.wsConnected.value).toBe(true)

    ws.disconnectWS()
    expect(sockets[0].closed).toBe(true)
    // 主动关闭后socket的close事件晚到
    sockets[0].fireClose()
    vi.advanceTimersByTime(120000)

    expect(wsFactory).toHaveBeenCalledTimes(1)
    expect(state.wsStatus.value).toBe(WS_STATUS.CLOSED)
    expect(state.wsConnected.value).toBe(false)
  })
})

describe('场景2：指数退避与延迟封顶', () => {
  it('非主动断开按指数退避重连，random=1时每档延迟严格≤30000ms', () => {
    const { ws, sockets, state } = createHarness({ random: () => 1 })
    ws.connectWS(1)
    sockets[0].fireOpen()

    // base=3000*2^n，抖动系数1.2：3600/7200/14400/28800/57600→封顶30000
    const expectedDelays = [3600, 7200, 14400, 28800, 30000]
    expectedDelays.forEach((delay, index) => {
      expect(delay).toBeLessThanOrEqual(MAX_RECONNECT_DELAY)
      sockets[index].fireClose()
      expect(state.wsStatus.value).toBe(WS_STATUS.RECONNECTING)
      // 到点前1ms不建连
      vi.advanceTimersByTime(delay - 1)
      expect(sockets.length).toBe(index + 1)
      // 到点后恰好新建一个连接
      vi.advanceTimersByTime(1)
      expect(sockets.length).toBe(index + 2)
    })
  })

  it('random=1时getReconnectDelay任意次数都不超过30000ms', () => {
    const { ws } = createHarness({ random: () => 1 })
    for (let attempts = 0; attempts < 12; attempts++) {
      expect(ws.getReconnectDelay(attempts)).toBeLessThanOrEqual(30000)
    }
  })
})

describe('场景3：浏览器离线与恢复', () => {
  it('离线15秒期间不重连，online事件只创建一个连接', () => {
    const { ws, sockets, wsFactory, fakeWindow, state } = createHarness()
    ws.connectWS(1)
    sockets[0].fireOpen()

    fakeWindow.setOnline(false)
    fakeWindow.dispatch('offline')
    expect(state.wsStatus.value).toBe(WS_STATUS.OFFLINE)

    // 断网导致socket关闭：保持offline，不调度重连
    sockets[0].fireClose()
    expect(state.wsStatus.value).toBe(WS_STATUS.OFFLINE)
    vi.advanceTimersByTime(15000)
    expect(wsFactory).toHaveBeenCalledTimes(1)

    // 恢复在线：只创建一个新连接
    fakeWindow.setOnline(true)
    fakeWindow.dispatch('online')
    expect(wsFactory).toHaveBeenCalledTimes(2)
    vi.advanceTimersByTime(60000)
    expect(wsFactory).toHaveBeenCalledTimes(2)

    sockets[1].fireOpen()
    expect(state.wsStatus.value).toBe(WS_STATUS.CONNECTED)
  })

  it('重连等待期间离线会取消定时重连，交由online恢复', () => {
    const { ws, sockets, wsFactory, fakeWindow, state } = createHarness({ random: () => 0 })
    ws.connectWS(1)
    sockets[0].fireOpen()
    sockets[0].fireClose() // 进入reconnecting，定时器已调度
    expect(state.wsStatus.value).toBe(WS_STATUS.RECONNECTING)

    fakeWindow.setOnline(false)
    fakeWindow.dispatch('offline')
    expect(state.wsStatus.value).toBe(WS_STATUS.OFFLINE)
    // 原定时器已被清除：等待任意时长都不建连
    vi.advanceTimersByTime(120000)
    expect(wsFactory).toHaveBeenCalledTimes(1)

    fakeWindow.setOnline(true)
    fakeWindow.dispatch('online')
    expect(wsFactory).toHaveBeenCalledTimes(2)
  })
})

describe('场景4：过期连接回调', () => {
  it('旧连接晚到的message/close不覆盖新连接状态', () => {
    const { ws, sockets, state } = createHarness()
    ws.connectWS(1)
    const oldSocket = sockets[0]
    oldSocket.fireOpen()

    // 任务切换到新连接
    ws.connectWS(2)
    const newSocket = sockets[1]
    newSocket.fireOpen()
    expect(state.wsStatus.value).toBe(WS_STATUS.CONNECTED)
    const messageCountBefore = state.progressMessages.value.length

    // 旧连接晚到的消息与close被代次守卫丢弃
    oldSocket.fireMessage({ type: 'task_progress', data: { completed_units: 99 } })
    oldSocket.fireClose()

    expect(state.progressMessages.value.length).toBe(messageCountBefore)
    expect(state.currentTask.value.completed_units).not.toBe(99)
    expect(state.wsStatus.value).toBe(WS_STATUS.CONNECTED)
  })
})

describe('场景5：资源清理', () => {
  it('任务切换关闭旧socket并清理待执行的重连定时器', () => {
    const { ws, sockets } = createHarness()
    ws.connectWS(1)
    sockets[0].fireOpen()

    // 任务切换：旧socket被关闭
    ws.connectWS(2)
    expect(sockets[0].closed).toBe(true)

    // 新连接断开进入重连等待，再次任务切换应清理定时器
    sockets[1].fireClose()
    ws.connectWS(3)
    const socketCountAfterSwitch = sockets.length
    vi.advanceTimersByTime(120000)
    expect(sockets.length).toBe(socketCountAfterSwitch)
  })

  it('终态完成断开连接并移除online/offline监听，5秒观察期无新连接', () => {
    const { ws, sockets, wsFactory, fakeWindow, state } = createHarness()
    ws.connectWS(1)
    sockets[0].fireOpen()
    expect(fakeWindow.listenerCount('online')).toBe(1)
    expect(fakeWindow.listenerCount('offline')).toBe(1)

    sockets[0].fireMessage({ type: 'task_complete', data: { total_word_count: 888 } })

    expect(state.currentTask.value.status).toBe('completed')
    expect(state.wsStatus.value).toBe(WS_STATUS.CLOSED)
    expect(sockets[0].closed).toBe(true)
    expect(fakeWindow.listenerCount('online')).toBe(0)
    expect(fakeWindow.listenerCount('offline')).toBe(0)

    const callsBefore = wsFactory.mock.calls.length
    vi.advanceTimersByTime(5000)
    fakeWindow.dispatch('online')
    expect(wsFactory.mock.calls.length).toBe(callsBefore)
  })

  it('主动断开后online事件不再触发重连（监听器已移除）', () => {
    const { ws, sockets, wsFactory, fakeWindow } = createHarness()
    ws.connectWS(1)
    sockets[0].fireOpen()
    ws.disconnectWS()

    fakeWindow.setOnline(false)
    fakeWindow.dispatch('offline')
    fakeWindow.setOnline(true)
    fakeWindow.dispatch('online')
    vi.advanceTimersByTime(60000)
    expect(wsFactory).toHaveBeenCalledTimes(1)
  })
})

describe('场景6：终态锁', () => {
  it('生产status_change进入终态时断开连接并移除网络监听', () => {
    const { ws, sockets, state, fakeWindow } = createHarness()
    ws.connectWS(1)
    sockets[0].fireOpen()

    sockets[0].fireMessage({
      type: 'status_change',
      task_id: 1,
      old_status: 'running',
      new_status: 'completed'
    })

    expect(state.currentTask.value.status).toBe('completed')
    expect(sockets[0].closed).toBe(true)
    expect(state.wsStatus.value).toBe(WS_STATUS.CLOSED)
    expect(fakeWindow.listenerCount('online')).toBe(0)
    expect(fakeWindow.listenerCount('offline')).toBe(0)
  })

  it('status_change终态后晚到的task_complete不会重复触发断连', () => {
    const state = useWritingTaskState()
    state.currentTask.value = { id: 1, status: 'running' }
    const onTerminal = vi.fn()
    const { handleMessage } = createWSMessageHandler(state, { onTerminal })

    handleMessage({ type: 'status_change', old_status: 'running', new_status: 'completed' })
    handleMessage({ type: 'task_complete', data: { total_word_count: 500 } })

    expect(onTerminal).toHaveBeenCalledTimes(1)
    expect(state.currentTask.value.status).toBe('completed')
  })

  it('两个终态消息同时到达只处理一次状态写入与连接关闭', () => {
    const { ws, sockets, state } = createHarness()
    ws.connectWS(1)
    sockets[0].fireOpen()

    sockets[0].fireMessage({ type: 'task_complete', data: { total_word_count: 1000 } })
    // 第二个终态消息（竞态来源）不得覆盖首个终态
    sockets[0].fireMessage({ type: 'task_failed', data: { error: '重复终态' } })

    expect(state.currentTask.value.status).toBe('completed')
    expect(state.currentTask.value.total_word_count).toBe(1000)
    expect(state.currentTask.value.error).toBeUndefined()
  })

  it('终态锁独立于代次守卫：同一处理器重复终态只回调一次onTerminal', () => {
    const state = useWritingTaskState()
    state.currentTask.value = { id: 1, status: 'running' }
    const onTerminal = vi.fn()
    const { handleMessage } = createWSMessageHandler(state, { onTerminal })

    handleMessage({ type: 'task_complete', data: { total_word_count: 500 } })
    handleMessage({ type: 'task_failed', data: { error: 'boom' } })

    expect(onTerminal).toHaveBeenCalledTimes(1)
    expect(state.currentTask.value.status).toBe('completed')
  })
})

describe('场景7：手动重试', () => {
  it('达到最大重连次数进入failed，手动重试进入connecting，成功后connected且计数清零', () => {
    const { ws, sockets, state } = createHarness({ random: () => 0 })
    ws.connectWS(1)
    sockets[0].fireOpen()

    // 连续失败MAX_RECONNECT_ATTEMPTS次后进入failed
    sockets[0].fireClose()
    for (let attempt = 1; attempt <= MAX_RECONNECT_ATTEMPTS; attempt++) {
      vi.advanceTimersByTime(MAX_RECONNECT_DELAY)
      sockets[sockets.length - 1].fireClose()
    }
    expect(state.wsStatus.value).toBe(WS_STATUS.FAILED)

    // failed后不再自动重连
    const socketCountAtFailed = sockets.length
    vi.advanceTimersByTime(300000)
    expect(sockets.length).toBe(socketCountAtFailed)

    // 手动重试：计数清零，状态为connecting（而非reconnecting）
    ws.retryConnection()
    expect(state.wsStatus.value).toBe(WS_STATUS.CONNECTING)
    sockets[sockets.length - 1].fireOpen()
    expect(state.wsStatus.value).toBe(WS_STATUS.CONNECTED)

    // 计数已清零：再次断开后第一档延迟即可重连（random=0 → 3000*0.8=2400ms）
    const socketCountBeforeDrop = sockets.length
    sockets[sockets.length - 1].fireClose()
    expect(state.wsStatus.value).toBe(WS_STATUS.RECONNECTING)
    vi.advanceTimersByTime(2400)
    expect(sockets.length).toBe(socketCountBeforeDrop + 1)
  })
})

describe('连接状态派生与消息时间', () => {
  it('wsConnected仅在connected状态为true，收到消息更新wsLastMessageAt', () => {
    const { ws, sockets, state } = createHarness()
    expect(state.wsConnected.value).toBe(false)
    ws.connectWS(1)
    expect(state.wsStatus.value).toBe(WS_STATUS.CONNECTING)
    expect(state.wsConnected.value).toBe(false)

    sockets[0].fireOpen()
    expect(state.wsConnected.value).toBe(true)

    expect(state.wsLastMessageAt.value).toBeNull()
    sockets[0].fireMessage({ type: 'task_progress', data: { completed_units: 1 } })
    expect(state.wsLastMessageAt.value).not.toBeNull()
  })
})
