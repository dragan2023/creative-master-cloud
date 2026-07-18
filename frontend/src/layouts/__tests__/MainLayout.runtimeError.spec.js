/**
 * MainLayout 运行时错误边界集成测试
 *
 * 使用真实 Element Plus 组件、真实内存路由与真实抛错子组件验证：
 * - 子组件渲染阶段抛错时错误页出现、错误编号可见
 * - 原始堆栈与敏感令牌不泄露到页面
 * - 点击「重试当前页面」重新挂载子树并增加渲染尝试次数，可恢复
 * - 点击「返回首页」通过真实路由跳转回首页
 * - 每次错误控制台只记录一次，避免日志风暴
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { defineComponent, h, nextTick } from 'vue'
import { createRouter, createMemoryHistory } from 'vue-router'
import ElementPlus from 'element-plus'

vi.mock('@/stores', () => ({
  useUserStore: () => ({ userInfo: null, isSuperAdmin: false, logout: vi.fn() }),
  useAppStore: () => ({ sidebarCollapsed: false, toggleSidebar: vi.fn() })
}))

vi.mock('@/api', () => ({
  updateApi: {
    getCurrentVersion: vi.fn().mockResolvedValue({ version: '0.0.0-test' })
  }
}))

vi.mock('@/utils/authStorage', () => ({
  getToken: () => null,
  getUserInfo: () => null
}))

vi.mock('@/composables/useAppExit', async () => {
  const { ref } = await import('vue')
  return {
    useAppExit: () => ({
      exiting: ref(false),
      isLocalDesktopEnv: ref(false),
      detectRuntimeEnvironment: vi.fn(),
      confirmAndExit: vi.fn()
    })
  }
})

vi.mock('@/composables/useResponsiveLayout', async () => {
  const { ref } = await import('vue')
  return {
    useResponsiveLayout: () => ({
      isMobile: ref(false),
      mobileMenuVisible: ref(false),
      openMobileMenu: vi.fn(),
      closeMobileMenu: vi.fn()
    })
  }
})

import MainLayout from '../MainLayout.vue'

/** 敏感样例：断言不允许出现在错误页 DOM 中 */
const SENSITIVE_ERROR_MESSAGE = 'boom: secret-token-ABC123'

/** 抛错子组件渲染尝试计数（每次重新挂载 setup 重新执行） */
let renderAttempts = 0
/** 前 N 次渲染抛错，之后渲染成功 */
let failTimes = Infinity

const ThrowingChild = defineComponent({
  name: 'ThrowingChild',
  setup() {
    renderAttempts += 1
    if (renderAttempts <= failTimes) {
      throw new Error(SENSITIVE_ERROR_MESSAGE)
    }
    return () => h('div', { class: 'recovered-child' }, '子页面恢复成功')
  }
})

const HomeStub = defineComponent({
  name: 'HomeStub',
  setup() {
    return () => h('div', { class: 'home-stub' }, '首页内容')
  }
})

/** 构建真实内存路由并挂载 MainLayout，初始导航到抛错页面 */
async function mountLayoutAtThrowingRoute() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: HomeStub },
      { path: '/boom', component: ThrowingChild }
    ]
  })
  router.push('/boom')
  await router.isReady()

  const wrapper = mount(MainLayout, {
    global: {
      plugins: [router, ElementPlus],
      stubs: { MainNavMenu: true }
    },
    attachTo: document.body
  })
  await flushPromises()
  return { wrapper, router }
}

/** 查找包含指定文本的按钮 */
function findButtonByText(wrapper, text) {
  const button = wrapper.findAll('button').find(item => item.text().includes(text))
  expect(button, `按钮「${text}」应存在`).toBeTruthy()
  return button
}

let consoleErrorSpy

beforeEach(() => {
  renderAttempts = 0
  failTimes = Infinity
  consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
})

afterEach(() => {
  consoleErrorSpy.mockRestore()
  document.body.innerHTML = ''
})

describe('MainLayout 运行时错误边界', () => {
  it('should_show_error_page_with_visible_error_id_when_child_throws', async () => {
    const { wrapper } = await mountLayoutAtThrowingRoute()

    expect(wrapper.find('.runtime-error').exists()).toBe(true)
    expect(wrapper.text()).toContain('当前页面加载异常')
    // 错误编号可见且符合 UI-xxx 格式
    expect(wrapper.find('.error-id').text()).toMatch(/^UI-[0-9A-Z]+$/)
    wrapper.unmount()
  })

  it('should_not_leak_stack_or_token_into_error_page', async () => {
    const { wrapper } = await mountLayoutAtThrowingRoute()

    const pageText = wrapper.text()
    expect(pageText).not.toContain('secret-token-ABC123')
    expect(pageText).not.toContain(SENSITIVE_ERROR_MESSAGE)
    // 不出现堆栈特征（文件帧 / Error 前缀）
    expect(pageText).not.toMatch(/\.js:\d+/)
    expect(pageText).not.toContain('Error:')
    wrapper.unmount()
  })

  it('should_remount_subtree_and_increase_attempts_on_retry', async () => {
    const { wrapper } = await mountLayoutAtThrowingRoute()
    expect(renderAttempts).toBe(1)

    await findButtonByText(wrapper, '重试当前页面').trigger('click')
    await flushPromises()

    // 子树重新挂载：渲染尝试次数增加；持续失败时错误页再次出现
    expect(renderAttempts).toBe(2)
    expect(wrapper.find('.runtime-error').exists()).toBe(true)
    wrapper.unmount()
  })

  it('should_recover_child_content_when_retry_succeeds', async () => {
    failTimes = 1
    const { wrapper } = await mountLayoutAtThrowingRoute()
    expect(wrapper.find('.runtime-error').exists()).toBe(true)

    await findButtonByText(wrapper, '重试当前页面').trigger('click')
    await flushPromises()
    await nextTick()

    expect(wrapper.find('.runtime-error').exists()).toBe(false)
    expect(wrapper.find('.recovered-child').exists()).toBe(true)
    expect(wrapper.text()).toContain('子页面恢复成功')
    wrapper.unmount()
  })

  it('should_navigate_home_via_real_router_on_back_home', async () => {
    const { wrapper, router } = await mountLayoutAtThrowingRoute()
    expect(router.currentRoute.value.path).toBe('/boom')

    await findButtonByText(wrapper, '返回首页').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.path).toBe('/')
    expect(wrapper.find('.runtime-error').exists()).toBe(false)
    expect(wrapper.find('.home-stub').exists()).toBe(true)
    wrapper.unmount()
  })

  it('should_log_each_error_exactly_once_to_avoid_log_storm', async () => {
    const { wrapper } = await mountLayoutAtThrowingRoute()

    const errorBoundaryLogs = consoleErrorSpy.mock.calls.filter(
      call => typeof call[0] === 'string' && call[0].startsWith('[UI-')
    )
    expect(errorBoundaryLogs).toHaveLength(1)

    // 重试再次失败：新错误同样只记录一次（累计 2 条，不指数放大）
    await findButtonByText(wrapper, '重试当前页面').trigger('click')
    await flushPromises()

    const logsAfterRetry = consoleErrorSpy.mock.calls.filter(
      call => typeof call[0] === 'string' && call[0].startsWith('[UI-')
    )
    expect(logsAfterRetry).toHaveLength(2)
    wrapper.unmount()
  })
})
