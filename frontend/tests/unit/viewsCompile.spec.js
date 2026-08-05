/**
 * 视图组件编译冒烟测试
 *
 * 确保改动过的 .vue 页面能通过 Vue SFC 编译（语法、导入路径正确）。
 */
import { describe, it, expect } from 'vitest'

describe('视图组件可编译', () => {
  it('历史页、首页、生成页 SFC 编译通过', async () => {
    const HistoryIndex = (await import('@/views/history/Index.vue')).default
    const HomeIndex = (await import('@/views/home/Index.vue')).default
    const GenerateForm = (await import('@/views/generate/GenerateForm.vue')).default

    expect(HistoryIndex).toBeTruthy()
    expect(HomeIndex).toBeTruthy()
    expect(GenerateForm).toBeTruthy()
  })
})
