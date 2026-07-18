/**
 * useResponsiveLayout 单元测试
 * 断点约定：<=768px 移动端；769-1200px 平板；>1200px 桌面端
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { nextTick } from 'vue'
import { useResponsiveLayout, MOBILE_BREAKPOINT, TABLET_BREAKPOINT } from '../useResponsiveLayout'

/**
 * 构造 window.matchMedia 模拟：支持按视口宽度计算 matches 并派发 change 事件
 */
function mockMatchMedia(initialWidth) {
  let viewportWidth = initialWidth
  const mediaQueryLists = []

  window.matchMedia = vi.fn((query) => {
    const maxWidth = parseInt(query.match(/max-width:\s*(\d+)px/)[1], 10)
    const changeListeners = new Set()
    const mediaQueryList = {
      media: query,
      get matches() {
        return viewportWidth <= maxWidth
      },
      addEventListener: (eventName, listener) => {
        if (eventName === 'change') changeListeners.add(listener)
      },
      removeEventListener: (eventName, listener) => {
        if (eventName === 'change') changeListeners.delete(listener)
      },
      _emitChange() {
        changeListeners.forEach((listener) => listener({ matches: this.matches }))
      }
    }
    mediaQueryLists.push(mediaQueryList)
    return mediaQueryList
  })

  return {
    setViewportWidth(newWidth) {
      viewportWidth = newWidth
      mediaQueryLists.forEach((mql) => mql._emitChange())
    }
  }
}

describe('useResponsiveLayout', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('断点常量固定为 768 和 1200', () => {
    expect(MOBILE_BREAKPOINT).toBe(768)
    expect(TABLET_BREAKPOINT).toBe(1200)
  })

  it('390px 视口下 isMobile 为 true 且 isTablet 为 false', () => {
    mockMatchMedia(390)
    const { isMobile, isTablet } = useResponsiveLayout()
    expect(isMobile.value).toBe(true)
    expect(isTablet.value).toBe(false)
  })

  it('1024px 视口下 isTablet 为 true 且 isMobile 为 false', () => {
    mockMatchMedia(1024)
    const { isMobile, isTablet } = useResponsiveLayout()
    expect(isMobile.value).toBe(false)
    expect(isTablet.value).toBe(true)
  })

  it('1440px 视口下 isMobile 和 isTablet 均为 false', () => {
    mockMatchMedia(1440)
    const { isMobile, isTablet } = useResponsiveLayout()
    expect(isMobile.value).toBe(false)
    expect(isTablet.value).toBe(false)
  })

  it('openMobileMenu 与 closeMobileMenu 切换抽屉可见状态', () => {
    mockMatchMedia(390)
    const { mobileMenuVisible, openMobileMenu, closeMobileMenu } = useResponsiveLayout()
    expect(mobileMenuVisible.value).toBe(false)
    openMobileMenu()
    expect(mobileMenuVisible.value).toBe(true)
    closeMobileMenu()
    expect(mobileMenuVisible.value).toBe(false)
  })

  it('视口从移动端切换到桌面端时抽屉自动关闭', async () => {
    const viewport = mockMatchMedia(390)
    const { isMobile, mobileMenuVisible, openMobileMenu } = useResponsiveLayout()
    openMobileMenu()
    expect(mobileMenuVisible.value).toBe(true)

    viewport.setViewportWidth(1440)
    await nextTick()
    expect(isMobile.value).toBe(false)
    expect(mobileMenuVisible.value).toBe(false)
  })

  it('视口变化时响应式状态同步更新', () => {
    const viewport = mockMatchMedia(1440)
    const { isMobile, isTablet } = useResponsiveLayout()
    expect(isMobile.value).toBe(false)

    viewport.setViewportWidth(600)
    expect(isMobile.value).toBe(true)
    expect(isTablet.value).toBe(false)

    viewport.setViewportWidth(900)
    expect(isMobile.value).toBe(false)
    expect(isTablet.value).toBe(true)
  })
})
