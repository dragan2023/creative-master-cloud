/**
 * 工作台终态内容校准测试。
 *
 * 终态可能由实时消息、手动刷新或状态请求近同时到达；同一任务只允许首个
 * running -> terminal 迁移触发一次 fetchUnits。
 */
import { nextTick, reactive } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import { useTaskTerminalRefresh } from '../useTaskTerminalRefresh'

describe('useTaskTerminalRefresh', () => {
  it('同一任务interrupted→running→completed的两个运行代次各校准一次', async () => {
    const writingStore = reactive({
      currentTask: { id: 7, status: 'running' },
      fetchUnits: vi.fn().mockResolvedValue([])
    })
    useTaskTerminalRefresh(writingStore)

    writingStore.currentTask.status = 'interrupted'
    await nextTick()
    await Promise.resolve()

    writingStore.currentTask.status = 'running'
    await nextTick()
    writingStore.currentTask.status = 'completed'
    await nextTick()
    await Promise.resolve()

    expect(writingStore.fetchUnits).toHaveBeenCalledTimes(2)
    expect(writingStore.fetchUnits).toHaveBeenNthCalledWith(1, 7)
    expect(writingStore.fetchUnits).toHaveBeenNthCalledWith(2, 7)
  })

  it('同一运行代次的重复completed只校准一次且组件不负责断连', async () => {
    const writingStore = reactive({
      currentTask: { id: 7, status: 'running' },
      fetchUnits: vi.fn().mockResolvedValue([]),
      disconnectWebSocket: vi.fn()
    })
    useTaskTerminalRefresh(writingStore)

    writingStore.currentTask.status = 'completed'
    await nextTick()
    await Promise.resolve()
    writingStore.currentTask.status = 'completed'
    await nextTick()

    expect(writingStore.fetchUnits).toHaveBeenCalledTimes(1)
    expect(writingStore.disconnectWebSocket).not.toHaveBeenCalled()
  })
})
