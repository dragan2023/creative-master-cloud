/**
 * 统一响应式布局组合式函数
 *
 * 全站唯一的 JavaScript 断点来源，页面不得自行定义第二套断点。
 * 断点与 styles/responsive.scss 中的媒体查询保持一致：
 * - <=768px  移动端（isMobile）
 * - 769-1200px 平板（isTablet）
 * - >1200px  桌面端
 */
import { ref, watch, getCurrentScope, onScopeDispose } from 'vue'

/** 移动端断点（px），与 responsive.scss 的 max-width: 768px 对应 */
export const MOBILE_BREAKPOINT = 768
/** 平板断点（px），与 responsive.scss 的 max-width: 1200px 对应 */
export const TABLET_BREAKPOINT = 1200

export function useResponsiveLayout() {
  const mobileQuery = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT}px)`)
  const tabletQuery = window.matchMedia(`(max-width: ${TABLET_BREAKPOINT}px)`)

  const isMobile = ref(mobileQuery.matches)
  const isTablet = ref(!mobileQuery.matches && tabletQuery.matches)
  const mobileMenuVisible = ref(false)

  /** 视口尺寸变化时同步移动端/平板状态 */
  function syncViewportState() {
    isMobile.value = mobileQuery.matches
    isTablet.value = !mobileQuery.matches && tabletQuery.matches
  }

  mobileQuery.addEventListener('change', syncViewportState)
  tabletQuery.addEventListener('change', syncViewportState)

  // 离开移动端视口时自动关闭抽屉，避免桌面端残留遮罩
  watch(isMobile, (isNowMobile) => {
    if (!isNowMobile) {
      mobileMenuVisible.value = false
    }
  })

  function openMobileMenu() {
    mobileMenuVisible.value = true
  }

  function closeMobileMenu() {
    mobileMenuVisible.value = false
  }

  // 在组件/作用域内使用时自动清理监听，防止内存泄漏
  if (getCurrentScope()) {
    onScopeDispose(() => {
      mobileQuery.removeEventListener('change', syncViewportState)
      tabletQuery.removeEventListener('change', syncViewportState)
    })
  }

  return {
    isMobile,
    isTablet,
    mobileMenuVisible,
    openMobileMenu,
    closeMobileMenu
  }
}
