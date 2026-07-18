/**
 * WritingWorkbench 生命周期资源清理测试。
 */
import { defineComponent, h } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

describe('useWorkbenchLifecycle', () => {
  it('轻量组件卸载时恰好断开一次工作台 WebSocket', async () => {
    const { useWorkbenchLifecycle } = await import('../useWorkbenchLifecycle')
    const writingStore = { disconnectWebSocket: vi.fn() }
    const Harness = defineComponent({
      setup() {
        useWorkbenchLifecycle(writingStore)
        return () => h('div')
      }
    })

    const wrapper = mount(Harness)
    wrapper.unmount()

    expect(writingStore.disconnectWebSocket).toHaveBeenCalledTimes(1)
  })
})
