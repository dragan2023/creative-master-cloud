import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { debounce } from '../debounce'

describe('debounce 可刷新防抖工具', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('连续调用只执行最后一次', () => {
    const spy = vi.fn()
    const debounced = debounce(spy, 400)

    debounced('第一次')
    debounced('第二次')
    debounced('第三次')

    vi.advanceTimersByTime(400)

    expect(spy).toHaveBeenCalledTimes(1)
    expect(spy).toHaveBeenCalledWith('第三次')
  })

  it('399ms 时不执行，400ms 时执行', () => {
    const spy = vi.fn()
    const debounced = debounce(spy, 400)

    debounced()

    vi.advanceTimersByTime(399)
    expect(spy).not.toHaveBeenCalled()

    vi.advanceTimersByTime(1)
    expect(spy).toHaveBeenCalledTimes(1)
  })

  it('flush() 立即执行待处理调用', () => {
    const spy = vi.fn()
    const debounced = debounce(spy, 400)

    debounced('待保存数据')
    expect(spy).not.toHaveBeenCalled()

    debounced.flush()

    expect(spy).toHaveBeenCalledTimes(1)
    expect(spy).toHaveBeenCalledWith('待保存数据')

    // flush 后不应再有残留的定时执行
    vi.advanceTimersByTime(400)
    expect(spy).toHaveBeenCalledTimes(1)
  })

  it('没有待处理调用时 flush() 不执行', () => {
    const spy = vi.fn()
    const debounced = debounce(spy, 400)

    debounced.flush()

    expect(spy).not.toHaveBeenCalled()
  })

  it('cancel() 丢弃待处理调用', () => {
    const spy = vi.fn()
    const debounced = debounce(spy, 400)

    debounced('将被丢弃')
    debounced.cancel()

    vi.advanceTimersByTime(400)
    expect(spy).not.toHaveBeenCalled()

    // cancel 后 flush 也不应执行已丢弃的调用
    debounced.flush()
    expect(spy).not.toHaveBeenCalled()
  })

  it('执行后可以再次防抖调用', () => {
    const spy = vi.fn()
    const debounced = debounce(spy, 400)

    debounced('第一轮')
    vi.advanceTimersByTime(400)
    expect(spy).toHaveBeenCalledTimes(1)

    debounced('第二轮')
    vi.advanceTimersByTime(400)
    expect(spy).toHaveBeenCalledTimes(2)
    expect(spy).toHaveBeenLastCalledWith('第二轮')
  })
})
