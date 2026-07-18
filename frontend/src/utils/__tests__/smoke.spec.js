import { describe, expect, it } from 'vitest'

describe('前端测试环境', () => {
  it('提供 jsdom 环境', () => {
    expect(document.createElement('div')).toBeInstanceOf(HTMLElement)
  })
})
