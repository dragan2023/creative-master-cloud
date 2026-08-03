/**
 * 新手引导组合式函数
 *
 * 管理用户首次使用的引导流程，包括：
 * - 首次登录欢迎（快捷入口选择）
 * - API Key配置引导
 * - 首次生成庆祝
 *
 * 版本化管理：
 * - ONBOARDING_VERSION 递增时，仅对新增步骤显示引导
 * - 已完成的历史步骤不会被重置
 *
 * @module useOnboarding
 */

import { ref, computed } from 'vue'
import { useApiKeyStore } from '@/stores'

// ============================================================
// 版本化管理
// ============================================================

/** 当前引导版本号 —— 升级提示词/步骤时递增此值 */
const ONBOARDING_VERSION = 2

/** 当前版本包含的所有步骤 ID */
const ALL_STEPS = ['welcome', 'api-guide', 'first-gen']

// localStorage键名
const STORAGE_KEYS = {
  // 版本号
  version: 'onboarding_version',
  // 按版本存储的已完成步骤集合
  completedSteps: (v) => `onboarding_steps_v${v}`,
  // 是否已看到欢迎
  hasSeenWelcome: 'onboarding_welcome_seen',
  // 是否已配置API
  hasConfiguredAPI: 'onboarding_api_configured',
  // 是否首次生成
  hasFirstGeneration: 'onboarding_first_gen_done',
  // 是否跳过
  skipOnboarding: 'onboarding_skip'
}

/**
 * 获取当前已完成步骤集合
 * @returns {Set<string>}
 */
function getCompletedSteps() {
  try {
    const raw = localStorage.getItem(STORAGE_KEYS.completedSteps(ONBOARDING_VERSION))
    if (!raw) return new Set()
    return new Set(JSON.parse(raw))
  } catch {
    return new Set()
  }
}

/**
 * 保存已完成步骤集合
 * @param {Set<string>} steps
 */
function saveCompletedSteps(steps) {
  localStorage.setItem(
    STORAGE_KEYS.completedSteps(ONBOARDING_VERSION),
    JSON.stringify([...steps])
  )
  localStorage.setItem(STORAGE_KEYS.version, String(ONBOARDING_VERSION))
}

/**
 * 标记单个步骤已完成
 * @param {string} stepId
 */
function markStepCompleted(stepId) {
  const steps = getCompletedSteps()
  steps.add(stepId)
  saveCompletedSteps(steps)
}

/**
 * 检查步骤是否已完成
 * @param {string} stepId
 * @returns {boolean}
 */
function isStepCompleted(stepId) {
  // 兼容旧版本数据：v1 使用的是独立的 localStorage key
  if (stepId === 'welcome') {
    if (localStorage.getItem(STORAGE_KEYS.hasSeenWelcome) === 'true') {
      markStepCompleted('welcome')
      return true
    }
  }
  if (stepId === 'api-guide') {
    if (localStorage.getItem(STORAGE_KEYS.hasConfiguredAPI) === 'true') {
      markStepCompleted('api-guide')
      return true
    }
  }
  if (stepId === 'first-gen') {
    if (localStorage.getItem(STORAGE_KEYS.hasFirstGeneration) === 'true') {
      markStepCompleted('first-gen')
      return true
    }
  }

  // 版本化检查
  const steps = getCompletedSteps()
  return steps.has(stepId)
}

/**
 * 新手引导组合式函数
 */
export function useOnboarding() {
  const apiKeyStore = useApiKeyStore()

  // 引导状态
  const showWelcomeDialog = ref(false)
  const showAPIGuideDialog = ref(false)
  const showFirstGenCelebration = ref(false)
  const currentStep = ref(0)

  // 已完成的步骤
  const welcomeCompleted = computed(() => isStepCompleted('welcome'))
  const apiGuideCompleted = computed(() => isStepCompleted('api-guide'))
  const firstGenCompleted = computed(() => isStepCompleted('first-gen'))

  // 是否有 API Key
  const hasAPIKeys = computed(() => {
    return apiKeyStore.apiKeys && apiKeyStore.apiKeys.length > 0
  })

  // 是否需要显示引导
  const needsOnboarding = computed(() => {
    if (isStepCompleted('welcome') && isStepCompleted('api-guide')) return false
    if (isStepCompleted('welcome') && hasAPIKeys.value) return false
    return true
  })

  /**
   * 初始化引导检查
   * 在首页 onMounted 时调用
   */
  function initOnboarding() {
    // 迁移旧版本数据
    migrateLegacyData()

    // 欢迎步骤
    if (!isStepCompleted('welcome')) {
      showWelcomeDialog.value = true
      currentStep.value = 0
      return
    }

    // API 配置步骤
    if (!isStepCompleted('api-guide') && !hasAPIKeys.value) {
      showAPIGuideDialog.value = true
      return
    }
  }

  /**
   * 迁移旧版本 localStorage 数据到版本化格式
   */
  function migrateLegacyData() {
    const savedVersion = localStorage.getItem(STORAGE_KEYS.version)
    if (savedVersion && parseInt(savedVersion, 10) >= ONBOARDING_VERSION) return

    // 从旧版 key 迁移
    if (localStorage.getItem(STORAGE_KEYS.hasSeenWelcome) === 'true') {
      markStepCompleted('welcome')
    }
    if (localStorage.getItem(STORAGE_KEYS.hasConfiguredAPI) === 'true') {
      markStepCompleted('api-guide')
    }
    if (localStorage.getItem(STORAGE_KEYS.hasFirstGeneration) === 'true') {
      markStepCompleted('first-gen')
    }
  }

  /**
   * 完成欢迎步骤
   */
  function completeWelcome() {
    markStepCompleted('welcome')
    // 同时写入旧版 key 保持兼容
    localStorage.setItem(STORAGE_KEYS.hasSeenWelcome, 'true')
    showWelcomeDialog.value = false

    // 立即检查 API Key 配置
    if (!hasAPIKeys.value && !isStepCompleted('api-guide')) {
      setTimeout(() => {
        showAPIGuideDialog.value = true
      }, 300)
    }
  }

  /**
   * 完成 API Key 配置步骤
   */
  function completeAPIGuide() {
    markStepCompleted('api-guide')
    localStorage.setItem(STORAGE_KEYS.hasConfiguredAPI, 'true')
    showAPIGuideDialog.value = false
  }

  /**
   * 标记首次生成完成
   */
  function markFirstGenerationDone() {
    if (!isStepCompleted('first-gen')) {
      markStepCompleted('first-gen')
      localStorage.setItem(STORAGE_KEYS.hasFirstGeneration, 'true')
      showFirstGenCelebration.value = true

      // 3 秒后自动关闭庆祝
      setTimeout(() => {
        showFirstGenCelebration.value = false
      }, 3000)
    }
  }

  /**
   * 跳过所有引导
   */
  function skipAll() {
    for (const step of ALL_STEPS) {
      markStepCompleted(step)
    }
    localStorage.setItem(STORAGE_KEYS.hasSeenWelcome, 'true')
    localStorage.setItem(STORAGE_KEYS.hasConfiguredAPI, 'true')
    localStorage.setItem(STORAGE_KEYS.skipOnboarding, 'true')
    showWelcomeDialog.value = false
    showAPIGuideDialog.value = false
  }

  /**
   * 重置引导（用于测试）
   */
  function resetOnboarding() {
    localStorage.removeItem(STORAGE_KEYS.version)
    for (const step of ALL_STEPS) {
      localStorage.removeItem(STORAGE_KEYS.completedSteps(step))
    }
    localStorage.removeItem(STORAGE_KEYS.hasSeenWelcome)
    localStorage.removeItem(STORAGE_KEYS.hasConfiguredAPI)
    localStorage.removeItem(STORAGE_KEYS.hasFirstGeneration)
    localStorage.removeItem(STORAGE_KEYS.skipOnboarding)
  }

  return {
    // 状态
    showWelcomeDialog,
    showAPIGuideDialog,
    showFirstGenCelebration,
    currentStep,
    needsOnboarding,
    hasAPIKeys,

    // 步骤状态
    welcomeCompleted,
    apiGuideCompleted,
    firstGenCompleted,

    // 版本
    onboardingVersion: ONBOARDING_VERSION,

    // 方法
    initOnboarding,
    completeWelcome,
    completeAPIGuide,
    markFirstGenerationDone,
    markStepCompleted,
    isStepCompleted,
    skipAll,
    resetOnboarding
  }
}
