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
  it('同一任务的重复终态只刷新一次内容', async () => {
    const writingStore = reactive({
      currentTask: { id: 7, status: 'running' },
      fetchUnits: vi.fn().mockResolvedValue([]),
      disconnectWebSocket: vi.fn()
    })
    useTaskTerminalRefresh(writingStore)

    writingStore.currentTask.status = 'completed'
    await nextTick()
    await Promise.resolve()

    // 第二个终态来源晚到，不得覆盖首个终态或重复刷新。
    writingStore.currentTask.status = 'failed'
    await nextTick()
    await Promise.resolve()

    expect(writingStore.fetchUnits).toHaveBeenCalledTimes(1)
    expect(writingStore.fetchUnits).toHaveBeenCalledWith(7)
    expect(writingStore.disconnectWebSocket).toHaveBeenCalledTimes(1)
  })
})
