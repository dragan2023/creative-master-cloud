/**
 * 新手引导组合式函数
 * 
 * 管理用户首次使用的引导流程，包括：
 * - 首次登录欢迎
 * - API Key配置引导
 * - 首次生成庆祝
 * 
 * @module useOnboarding
 */

import { ref, computed } from 'vue'
import { useApiKeyStore } from '@/stores'

// localStorage键名
const STORAGE_KEYS = {
  hasSeenWelcome: 'onboarding_welcome_seen',
  hasConfiguredAPI: 'onboarding_api_configured',
  hasFirstGeneration: 'onboarding_first_gen_done',
  skipOnboarding: 'onboarding_skip'
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
  
  // 从localStorage读取状态
  const hasSeenWelcome = computed(() => {
    return localStorage.getItem(STORAGE_KEYS.hasSeenWelcome) === 'true'
  })
  
  const hasConfiguredAPI = computed(() => {
    return localStorage.getItem(STORAGE_KEYS.hasConfiguredAPI) === 'true'
  })
  
  const hasFirstGeneration = computed(() => {
    return localStorage.getItem(STORAGE_KEYS.hasFirstGeneration) === 'true'
  })
  
  const hasAPIKeys = computed(() => {
    return apiKeyStore.apiKeys && apiKeyStore.apiKeys.length > 0
  })
  
  // 是否需要显示引导
  const needsOnboarding = computed(() => {
    return !hasSeenWelcome.value || (!hasConfiguredAPI.value && !hasAPIKeys.value)
  })
  
  /**
   * 初始化引导检查
   * 在首页onMounted时调用
   */
  function initOnboarding() {
    // 如果从未显示过欢迎，显示欢迎引导
    if (!hasSeenWelcome.value) {
      showWelcomeDialog.value = true
      currentStep.value = 0
      return
    }
    
    // 如果已配置过API Key，跳过
    if (hasConfiguredAPI.value) {
      return
    }
    
    // 检查是否已有API Key
    if (!hasAPIKeys.value) {
      showAPIGuideDialog.value = true
    }
  }
  
  /**
   * 完成欢迎步骤
   */
  function completeWelcome() {
    localStorage.setItem(STORAGE_KEYS.hasSeenWelcome, 'true')
    showWelcomeDialog.value = false
    
    // 立即检查API Key配置
    if (!hasAPIKeys.value) {
      setTimeout(() => {
        showAPIGuideDialog.value = true
      }, 300)
    }
  }
  
  /**
   * 完成API Key配置步骤
   */
  function completeAPIGuide() {
    localStorage.setItem(STORAGE_KEYS.hasConfiguredAPI, 'true')
    showAPIGuideDialog.value = false
  }
  
  /**
   * 标记首次生成完成
   */
  function markFirstGenerationDone() {
    if (!hasFirstGeneration.value) {
      localStorage.setItem(STORAGE_KEYS.hasFirstGeneration, 'true')
      showFirstGenCelebration.value = true
      
      // 3秒后自动关闭庆祝
      setTimeout(() => {
        showFirstGenCelebration.value = false
      }, 3000)
    }
  }
  
  /**
   * 跳过所有引导
   */
  function skipAll() {
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
    
    // 方法
    initOnboarding,
    completeWelcome,
    completeAPIGuide,
    markFirstGenerationDone,
    skipAll,
    resetOnboarding
  }
}
