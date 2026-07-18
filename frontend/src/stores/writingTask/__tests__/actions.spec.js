/**
 * 写作任务动作与 WebSocket 所有权测试。
 */
import { describe, expect, it, vi } from 'vitest'
import { useWritingTaskState } from '../state'

const listTasksMock = vi.hoisted(() => vi.fn())

vi.mock('@/api/writing-task', () => ({
  writingTaskApi: {
    listTasks: listTasksMock
  }
}))

import { useWritingTaskActions } from '../actions'

describe('fetchCurrentTask', () => {
  it('切换到没有任务的项目时关闭上一任务的 WebSocket', async () => {
    listTasksMock
      .mockResolvedValueOnce({ data: { items: [] } })
      .mockResolvedValueOnce({ data: { items: [] } })

    const state = useWritingTaskState()
    state.currentTask.value = { id: 11, project_id: 1, status: 'running' }
    const connectWS = vi.fn()
    const disconnectWS = vi.fn()
    const actions = useWritingTaskActions(state, connectWS, disconnectWS)

    await actions.fetchCurrentTask(2)

    expect(disconnectWS).toHaveBeenCalledTimes(1)
    expect(connectWS).not.toHaveBeenCalled()
    expect(state.currentTask.value).toBeNull()
  })
})
