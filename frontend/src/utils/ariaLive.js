/**
 * ariaLive - 无障碍状态播报工具
 *
 * 将状态变更写入全局 #global-aria-live 区域，
 * 确保屏幕阅读器能播报 UI 变化，而不只依赖颜色和 Toast。
 *
 * @module utils/ariaLive
 */

/**
 * 向全局无障碍播报区域写入状态文本。
 * 屏幕阅读器将自动朗读此变更。
 *
 * @param {string} text - 要播报的状态文本
 * @param {'polite'|'assertive'} [priority='polite'] - 播报优先级
 *   - 'polite': 等待当前朗读完成后再播报
 *   - 'assertive': 立即打断并播报
 */
export function announceToScreenReader(text, priority = 'polite') {
  const region = document.getElementById('global-aria-live')
  if (!region) {
    console.warn('[ariaLive] 找不到 #global-aria-live 元素，请确认 MainLayout 已渲染')
    return
  }

  // 更新 aria-live 属性以匹配优先级
  region.setAttribute('aria-live', priority)

  // 清空内容（屏幕阅读器对相同文本不会重复播报，先清空再写入）
  region.textContent = ''
  // 使用 requestAnimationFrame 确保 DOM 已更新
  requestAnimationFrame(() => {
    region.textContent = text
  })
}

/**
 * 播报生成状态变更。
 * 用于生成按钮禁用/启用时告知原因。
 *
 * @param {'generating'|'completed'|'error'|'idle'} status
 * @param {Object} [options]
 * @param {string} [options.moduleName] - 当前模块名称
 */
export function announceGenerationStatus(status, options = {}) {
  const { moduleName = '' } = options
  const prefix = moduleName ? `【${moduleName}】` : ''

  switch (status) {
    case 'generating':
      announceToScreenReader(`${prefix}正在生成内容，请稍候。生成按钮已禁用，避免重复提交。`, 'polite')
      break
    case 'completed':
      announceToScreenReader(`${prefix}内容生成完成，可以查看结果。`, 'polite')
      break
    case 'error':
      announceToScreenReader(`${prefix}生成出错，请查看错误信息后重试。`, 'assertive')
      break
    case 'idle':
      announceToScreenReader(`${prefix}准备就绪，可以开始生成。`, 'polite')
      break
    default:
      break
  }
}
