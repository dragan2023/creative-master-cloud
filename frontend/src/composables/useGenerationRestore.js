/**
 * 生成状态恢复组合式函数
 * 检测未完成的生成任务，提供恢复功能
 */
import { ref, onMounted } from 'vue'
import { generateApi } from '@/api'

export function useGenerationRestore(type, restoreState) {
  const hasRestorableState = ref(false)
  const restorableData = ref(null)
  const restoring = ref(false)

  /**
   * 尝试恢复生成状态
   * 检查是否有可恢复的未完成生成任务
   */
  const tryRestore = async () => {
    try {
      // 检查restoreState中是否有可恢复的数据
      if (!restoreState?.value) {
        console.log('[useGenerationRestore] 没有恢复状态数据')
        return false
      }

      const state = restoreState.value
      console.log('[useGenerationRestore] 检查恢复状态:', {
        type,
        hasState: !!state,
        status: state?.status,
        stageKeys: state?.stage_data ? Object.keys(state.stage_data) : []
      })

      // 检查是否是未完成的状态
      if (state.status !== 'processing' && state.status !== 'pending') {
        console.log('[useGenerationRestore] 任务已完成，无需恢复')
        return false
      }

      // 检查stage_data中是否有可恢复的内容
      const stageData = state.stage_data || {}
      const contentKeys = [
        'global_outline',
        'content',
        'script_content',
        'ad_content',
        'development_plan',
        'partial_content',
        'progress'
      ]

      const hasContent = contentKeys.some(key => {
        const val = stageData[key]
        return val && (typeof val === 'string' && val.length > 0)
      })

      if (hasContent) {
        hasRestorableState.value = true
        restorableData.value = state
        console.log('[useGenerationRestore] 发现可恢复的生成状态，内容字段:', 
          contentKeys.filter(k => stageData[k] && (typeof stageData[k] === 'string' && stageData[k].length > 0))
        )
        return true
      }

      console.log('[useGenerationRestore] 没有可恢复的内容')
      return false
    } catch (e) {
      console.error('[useGenerationRestore] 恢复检查失败:', e)
      return false
    }
  }

  /**
   * 执行恢复操作
   */
  const restore = async () => {
    if (!restorableData.value) return null
    restoring.value = true
    try {
      const result = restorableData.value
      console.log('[useGenerationRestore] 正在恢复生成状态...')
      hasRestorableState.value = false
      return result
    } catch (e) {
      console.error('[useGenerationRestore] 恢复失败:', e)
      return null
    } finally {
      restoring.value = false
    }
  }

  /**
   * 清除恢复状态
   */
  const clearRestore = () => {
    hasRestorableState.value = false
    restorableData.value = null
  }

  return {
    hasRestorableState,
    restorableData,
    restoring,
    tryRestore,
    restore,
    clearRestore
  }
}
