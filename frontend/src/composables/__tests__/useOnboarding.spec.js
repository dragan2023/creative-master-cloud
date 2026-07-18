/**
 * 新手引导组合式函数测试
 *
 * 验证：
 * - 判断前先加载 API Key，避免"尚未加载"被误判为"未配置"
 * - Key 加载失败时不弹配置引导
 * - 引导状态按用户隔离，互不影响
 * - 匿名用户使用独立命名空间
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'

// mock API Key store，隔离网络与 Pinia 依赖
const mockApiKeyStore = {
  apiKeys: [],
  fetchApiKeys: vi.fn()
}

vi.mock('@/stores', () => ({
  useApiKeyStore: () => mockApiKeyStore
}))

import { useOnboarding } from '../useOnboarding'

describe('useOnboarding', () => {
  beforeEach(() => {
    localStorage.clear()
    mockApiKeyStore.apiKeys = []
    mockApiKeyStore.fetchApiKeys = vi.fn().mockResolvedValue()
  })

  it('should_not_show_api_guide_when_user_already_has_api_keys', async () => {
    mockApiKeyStore.apiKeys = [{ id: 1, provider: 'deepseek' }]
    localStorage.setItem('onboarding:7:welcome_seen', 'true')

    const onboarding = useOnboarding()
    await onboarding.initOnboarding(7)

    expect(onboarding.showAPIGuideDialog.value).toBe(false)
    expect(onboarding.showWelcomeDialog.value).toBe(false)
  })

  it('should_fetch_api_keys_before_judging_when_store_is_empty', async () => {
    localStorage.setItem('onboarding:7:welcome_seen', 'true')

    const onboarding = useOnboarding()
    await onboarding.initOnboarding(7)

    expect(mockApiKeyStore.fetchApiKeys).toHaveBeenCalledTimes(1)
    // 加载成功但确实没有 Key：可以弹配置引导
    expect(onboarding.showAPIGuideDialog.value).toBe(true)
  })

  it('should_not_treat_unknown_key_state_as_unconfigured_when_fetch_fails', async () => {
    mockApiKeyStore.fetchApiKeys = vi.fn().mockRejectedValue(new Error('network down'))
    localStorage.setItem('onboarding:7:welcome_seen', 'true')

    const onboarding = useOnboarding()
    await onboarding.initOnboarding(7)

    // 状态未知：既不弹配置引导，也不弹欢迎页
    expect(onboarding.showAPIGuideDialog.value).toBe(false)
    expect(onboarding.showWelcomeDialog.value).toBe(false)
  })

  it('should_isolate_onboarding_state_between_user_7_and_user_8', async () => {
    mockApiKeyStore.apiKeys = [{ id: 1 }]

    const onboardingUser7 = useOnboarding()
    await onboardingUser7.initOnboarding(7)
    expect(onboardingUser7.showWelcomeDialog.value).toBe(true)
    onboardingUser7.completeWelcome()
    expect(localStorage.getItem('onboarding:7:welcome_seen')).toBe('true')

    // 用户 8 在同一浏览器登录，仍应视为首次使用
    const onboardingUser8 = useOnboarding()
    await onboardingUser8.initOnboarding(8)
    expect(onboardingUser8.showWelcomeDialog.value).toBe(true)
    expect(localStorage.getItem('onboarding:8:welcome_seen')).toBeNull()
  })

  it('should_use_anonymous_namespace_when_user_id_is_missing', async () => {
    mockApiKeyStore.apiKeys = [{ id: 1 }]

    const onboarding = useOnboarding()
    await onboarding.initOnboarding(undefined)
    expect(onboarding.showWelcomeDialog.value).toBe(true)
    onboarding.completeWelcome()

    expect(localStorage.getItem('onboarding:anonymous:welcome_seen')).toBe('true')
  })

  it('should_skip_api_guide_when_user_already_completed_api_step', async () => {
    localStorage.setItem('onboarding:7:welcome_seen', 'true')
    localStorage.setItem('onboarding:7:api_configured', 'true')

    const onboarding = useOnboarding()
    await onboarding.initOnboarding(7)

    expect(mockApiKeyStore.fetchApiKeys).toHaveBeenCalledTimes(1)
    expect(onboarding.showAPIGuideDialog.value).toBe(false)
  })
})
