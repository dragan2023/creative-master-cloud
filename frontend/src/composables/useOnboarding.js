/**
 * 新手引导组合式函数
 * 
 * 管理用户首次使用的引导流程，包括：
 * - 首次登录欢迎
 * - API Key配置引导
 * - 首次生成庆祝
 * 
 * 状态按用户隔离存储（onboarding:<userId>:<key>），
 * 判断前先确认 API Key 已加载，避免"未加载"被误判为"未配置"。
 * 
 * @module useOnboarding
 */

import { ref, computed } from 'vue'
import { useApiKeyStore } from '@/stores'

// localStorage 键名（业务段，不含用户命名空间）
const STORAGE_KEYS = {
  hasSeenWelcome: 'welcome_seen',
  hasConfiguredAPI: 'api_configured',
  hasFirstGeneration: 'first_gen_done',
  skipOnboarding: 'skip'
}

/**
 * 生成按用户隔离的存储键，避免不同账号共享同一浏览器状态
 * @param {number|string|null|undefined} userId - 当前用户标识
 * @param {string} key - 业务键名
 * @returns {string} 形如 onboarding:7:welcome_seen / onboarding:anonymous:welcome_seen
 */
const scopedKey = (userId, key) => `onboarding:${userId || 'anonymous'}:${key}`

/**
 * 新手引导组合式函数
 */
export function useOnboarding() {
  const apiKeyStore = useApiKeyStore()
  
  // 当前用户标识（由 initOnboarding 注入）
  const currentUserId = ref(null)
  // 写 localStorage 后自增，驱动 computed 重新求值
  const storageVersion = ref(0)
  
  // 引导状态
  const showWelcomeDialog = ref(false)
  const showAPIGuideDialog = ref(false)
  const showFirstGenCelebration = ref(false)
  const currentStep = ref(0)
  
  /** 读取当前用户的引导标记 */
  function readFlag(key) {
    return localStorage.getItem(scopedKey(currentUserId.value, key)) === 'true'
  }
  
  /** 写入当前用户的引导标记 */
  function writeFlag(key) {
    localStorage.setItem(scopedKey(currentUserId.value, key), 'true')
    storageVersion.value++
  }
  
  /** 移除当前用户的引导标记 */
  function removeFlag(key) {
    localStorage.removeItem(scopedKey(currentUserId.value, key))
    storageVersion.value++
  }
  
  // 从localStorage读取状态（依赖 currentUserId 与 storageVersion 保持响应式）
  const hasSeenWelcome = computed(() => {
    void storageVersion.value
    return readFlag(STORAGE_KEYS.hasSeenWelcome)
  })
  
  const hasConfiguredAPI = computed(() => {
    void storageVersion.value
    return readFlag(STORAGE_KEYS.hasConfiguredAPI)
  })
  
  const hasFirstGeneration = computed(() => {
    void storageVersion.value
    return readFlag(STORAGE_KEYS.hasFirstGeneration)
  })
  
  const hasAPIKeys = computed(() => {
    return apiKeyStore.apiKeys && apiKeyStore.apiKeys.length > 0
  })
  
  // 是否需要显示引导
  const needsOnboarding = computed(() => {
    return !hasSeenWelcome.value || (!hasConfiguredAPI.value && !hasAPIKeys.value)
  })
  
  /**
   * 初始化引导检查（在首页 onMounted 时 await 调用）
   * 判断前先加载 API Key，状态未知时不弹配置引导
   * @param {number|string|null|undefined} userId - 当前用户标识
   */
  async function initOnboarding(userId) {
    currentUserId.value = userId ?? null
    
    // API Key 尚未加载时先加载，避免把"未知"误判为"未配置"
    if (!apiKeyStore.apiKeys.length) {
      try {
        await apiKeyStore.fetchApiKeys()
      } catch (error) {
        console.warn('[Onboarding] 无法确认 API Key 状态，本次不弹配置引导', error)
        return
      }
    }
    
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
    writeFlag(STORAGE_KEYS.hasSeenWelcome)
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
    writeFlag(STORAGE_KEYS.hasConfiguredAPI)
    showAPIGuideDialog.value = false
  }
  
  /**
   * 标记首次生成完成
   */
  function markFirstGenerationDone() {
    if (!hasFirstGeneration.value) {
      writeFlag(STORAGE_KEYS.hasFirstGeneration)
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
    writeFlag(STORAGE_KEYS.hasSeenWelcome)
    writeFlag(STORAGE_KEYS.hasConfiguredAPI)
    writeFlag(STORAGE_KEYS.skipOnboarding)
    showWelcomeDialog.value = false
    showAPIGuideDialog.value = false
  }
  
  /**
   * 重置引导（用于测试）
   */
  function resetOnboarding() {
    removeFlag(STORAGE_KEYS.hasSeenWelcome)
    removeFlag(STORAGE_KEYS.hasConfiguredAPI)
    removeFlag(STORAGE_KEYS.hasFirstGeneration)
    removeFlag(STORAGE_KEYS.skipOnboarding)
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
