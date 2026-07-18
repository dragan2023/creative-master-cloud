/**
 * 可刷新防抖工具
 * 用于收敛高频触发的副作用（如表单自动保存），支持离开页面前立即落盘。
 *
 * @param {Function} fn 需要防抖的函数
 * @param {number} delay 防抖延迟（毫秒），默认 400
 * @returns {Function} 防抖后的函数，附带 flush() 与 cancel() 方法
 *   - flush(): 立即执行待处理调用（无待处理调用时不执行）
 *   - cancel(): 丢弃待处理调用
 */
export function debounce(fn, delay = 400) {
  let timer = null
  let lastArgs = null

  const invoke = () => {
    if (!lastArgs) return
    const args = lastArgs
    lastArgs = null
    timer = null
    fn(...args)
  }

  const debounced = (...args) => {
    lastArgs = args
    if (timer) clearTimeout(timer)
    timer = setTimeout(invoke, delay)
  }

  debounced.flush = () => {
    if (timer) clearTimeout(timer)
    invoke()
  }

  debounced.cancel = () => {
    if (timer) clearTimeout(timer)
    timer = null
    lastArgs = null
  }

  return debounced
}
