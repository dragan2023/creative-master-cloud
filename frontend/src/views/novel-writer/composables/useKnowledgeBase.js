/**
 * useKnowledgeBase - 知识库管理组合式函数
 *
 * 功能：
 * 1. 加载/刷新知识库状态
 * 2. 构建知识库（含轮询进度）
 * 3. 删除知识库
 * 4. 重置知识库构建状态
 *
 * 依赖：
 * - novelWriterApi
 * - projectId（ref/computed，来自父组件）
 *
 * 用法：
 * const { kbStatus, loadingKbStatus, buildingKb, ... } = useKnowledgeBase(projectId)
 */

import { ref, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { novelWriterApi } from '@/api/novel-writer'

export function useKnowledgeBase(projectId) {
  // ==================== 状态 ====================
  const kbStatus = ref({
    status: 'pending',
    progress: null,
    graphrag_enabled: true,
    stats: null
  })
  const loadingKbStatus = ref(false)
  const buildingKb = ref(false)
  const resettingKbStatus = ref(false)

  // 内部轮询定时器
  let kbBuildPollingTimer = null

  // ==================== 方法 ====================

  /** 加载知识库状态 */
  async function loadKnowledgeBaseStatus() {
    loadingKbStatus.value = true
    try {
      const res = await novelWriterApi.getKnowledgeBaseStatus(projectId.value)
      if (res.success) {
        kbStatus.value = res.data
      }
    } catch (error) {
      console.error('加载知识库状态失败', error)
    } finally {
      loadingKbStatus.value = false
    }
  }

  /** 刷新知识库状态 */
  async function refreshKnowledgeBaseStatus() {
    await loadKnowledgeBaseStatus()
    ElMessage.success('知识库状态已刷新')
  }

  /** 构建知识库
   * 基于项目大纲构建项目专属知识图谱，辅助AI进行正文生成。
   */
  async function handleBuildKnowledgeBase() {
    buildingKb.value = true
    try {
      const res = await novelWriterApi.buildKnowledgeBase(projectId.value)
      if (res.success) {
        ElMessage.success('知识库构建任务已启动')
        // 开始轮询状态
        startKbBuildPolling()
      }
    } catch (error) {
      ElMessage.error('启动知识库构建失败')
    } finally {
      buildingKb.value = false
    }
  }

  /** 知识库构建状态轮询 */
  function startKbBuildPolling() {
    if (kbBuildPollingTimer) {
      clearInterval(kbBuildPollingTimer)
    }

    kbBuildPollingTimer = setInterval(async () => {
      try {
        const res = await novelWriterApi.getKnowledgeBaseStatus(projectId.value)
        if (res.success) {
          kbStatus.value = res.data
          if (res.data.status !== 'building') {
            // 构建完成或失败，停止轮询
            clearInterval(kbBuildPollingTimer)
            kbBuildPollingTimer = null

            if (res.data.status === 'ready') {
              ElMessage.success('知识库构建完成')
            } else if (res.data.status === 'failed') {
              ElMessage.error('知识库构建失败')
            }
          }
        }
      } catch (error) {
        console.error('轮询知识库状态失败', error)
      }
    }, 2000)
  }

  /** 删除知识库 */
  async function handleDeleteKnowledgeBase() {
    try {
      const res = await novelWriterApi.deleteKnowledgeBase(projectId.value)
      if (res.success) {
        ElMessage.success('知识库已删除')
        kbStatus.value = {
          status: 'pending',
          progress: null,
          graphrag_enabled: true,
          stats: null
        }
      }
    } catch (error) {
      ElMessage.error('删除知识库失败')
    }
  }

  /** 重置知识库构建状态（用于清除幽灵状态） */
  async function handleResetKbStatus() {
    resettingKbStatus.value = true
    try {
      const res = await novelWriterApi.resetKnowledgeBaseStatus(projectId.value)
      if (res.success) {
        ElMessage.success(`知识库状态已重置: ${res.data.previous_status} → ${res.data.new_status}`)
        // 刷新知识库状态
        await loadKnowledgeBaseStatus()
      }
    } catch (error) {
      ElMessage.error('重置知识库状态失败')
    } finally {
      resettingKbStatus.value = false
    }
  }

  // ==================== 清理 ====================
  onUnmounted(() => {
    if (kbBuildPollingTimer) {
      clearInterval(kbBuildPollingTimer)
      kbBuildPollingTimer = null
    }
  })

  // ==================== 导出 ====================
  return {
    kbStatus,
    loadingKbStatus,
    buildingKb,
    resettingKbStatus,
    loadKnowledgeBaseStatus,
    refreshKnowledgeBaseStatus,
    handleBuildKnowledgeBase,
    handleDeleteKnowledgeBase,
    handleResetKbStatus
  }
}
