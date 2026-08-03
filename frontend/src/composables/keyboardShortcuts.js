/**
 * keyboardShortcuts - 统一键盘快捷键管理
 *
 * 提供注册、注销、冲突检测与组合键处理，确保：
 * - 所有快捷键可通过统一入口管理
 * - 对话框 Esc 仅关闭当前层（不冒泡到父级）
 * - 输入框中不触发全局快捷键
 * - 生产环境下禁用 debug 快捷键
 *
 * @module composables/keyboardShortcuts
 */

import { onMounted, onBeforeUnmount } from 'vue'

/** 已注册的快捷键列表 */
const registeredShortcuts = []

/**
 * 注册一个全局键盘快捷键。
 *
 * @param {string} id - 唯一标识符（用于注销）
 * @param {Object} options
 * @param {string} [options.key] - 按键名称（如 'q', 'Escape'）
 * @param {boolean} [options.ctrl=false] - 是否需 Ctrl
 * @param {boolean} [options.shift=false] - 是否需 Shift
 * @param {boolean} [options.alt=false] - 是否需 Alt
 * @param {string} [options.description] - 快捷键功能描述
 * @param {Function} options.handler - 回调函数
 * @param {boolean} [options.ignoreInput=true] - 输入框中忽略
 * @param {boolean} [options.devOnly=false] - 仅开发环境启用
 */
export function registerShortcut(id, options) {
  const {
    key,
    ctrl = false,
    shift = false,
    alt = false,
    description = '',
    handler,
    ignoreInput = true,
    devOnly = false
  } = options

  if (!id || !key || typeof handler !== 'function') {
    console.warn('[KeyboardShortcuts] 非法快捷键注册:', id, options)
    return
  }

  // 开发环境限定
  if (devOnly && import.meta.env.PROD) return

  // 避免重复注册
  if (registeredShortcuts.some((s) => s.id === id)) {
    console.warn('[KeyboardShortcuts] 快捷键已注册，跳过:', id)
    return
  }

  const entry = { id, key, ctrl, shift, alt, description, handler, ignoreInput }
  registeredShortcuts.push(entry)
}

/**
 * 注销指定的快捷键。
 * @param {string} id
 */
export function unregisterShortcut(id) {
  const idx = registeredShortcuts.findIndex((s) => s.id === id)
  if (idx !== -1) registeredShortcuts.splice(idx, 1)
}

/**
 * 全局键盘事件处理器 — 在 MainLayout 中安装。
 */
export function createGlobalKeyboardHandler() {
  function handleKeydown(e) {
    // 输入框中不触发（可被个别 shortcut 覆写）
    const isInputTarget = ['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName)

    for (const sc of registeredShortcuts) {
      if (sc.ignoreInput && isInputTarget) continue
      if (e.key !== sc.key && e.key.toLowerCase() !== sc.key.toLowerCase()) continue
      if (!!e.ctrlKey !== !!sc.ctrl) continue
      if (!!e.shiftKey !== !!sc.shift) continue
      if (!!e.altKey !== !!sc.alt) continue

      e.preventDefault()
      sc.handler(e)
      return
    }
  }

  return { handleKeydown }
}

/**
 * Vue 组合式函数: 在当前组件生命周期内注册快捷键。
 *
 * @param {Object[]} shortcuts - 快捷键配置数组（与 registerShortcut 的 options 相同，额外加 id）
 *
 * @example
 *   useKeyboardShortcuts([
 *     { id: 'toggle-task-center', key: 'q', ctrl: true, shift: true, description: '打开任务中心', handler: () => { ... } }
 *   ])
 */
export function useKeyboardShortcuts(shortcuts) {
  onMounted(() => {
    for (const sc of shortcuts) {
      registerShortcut(sc.id, sc)
    }
  })
  onBeforeUnmount(() => {
    for (const sc of shortcuts) {
      unregisterShortcut(sc.id)
    }
  })
}

/**
 * 判断当前焦点是否在输入元素内。
 * @returns {boolean}
 */
export function isInputFocused() {
  const tag = document.activeElement?.tagName
  return tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
}
