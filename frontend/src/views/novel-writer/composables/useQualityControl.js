/**
 * useQualityControl - 项目详情页 单元概述质控
 *
 * 管理单元概述的质量检测触发和结果展示。
 * v4.0优化: 剧集/电影类型跳过质控，仅小说类型执行。
 *
 * @date: 2026-06-10
 * @version: v1.0.0
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { novelWriterApi } from '@/api/novel-writer'

/**
 * @param {import('vue').ComputedRef} projectIdRef - 项目ID计算属性
 * @param {import('vue').Ref} projectRef - 项目数据ref
 * @param {Function} loadProject - 重新加载项目数据的函数
 */
export function useQualityControl(projectIdRef, projectRef, loadProject) {
  const qualityControlLoading = ref(false)
  const showQualityControlResultDialog = ref(false)
  const qualityControlResult = ref(null)

  /**
   * 触发单元概述质量检测
   *
   * v4.0优化: 仅小说类型执行质控，剧集/电影类型跳过
   */
  async function handleTriggerQualityControl() {
    const project = projectRef?.value
    const projectId = projectIdRef?.value

    if (!projectId) {
      ElMessage.error('无法获取项目ID')
      return
    }

    // project 未加载时的临时状态，使用通用处理
    if (!project) {
      ElMessage.warning('项目数据未加载，请稍后再试')
      return
    }

    const contentType = project.content_type || 'novel'

    // v4.0优化: 剧集/电影类型跳过质控，引导用户使用对话修正
    if (contentType !== 'novel') {
      ElMessage.info('剧集/电影类型已禁用自动质控修正。如需调整内容，请使用对话修正功能。')
      return
    }

    qualityControlLoading.value = true

    try {
      const response = await novelWriterApi.triggerUnitSummariesQualityControl(
        projectId,
        { content_type: contentType }
      )

      if (response.success) {
        qualityControlResult.value = {
          qualityReport: response.data?.quality_report,
          revisionSummary: response.data?.revision_summary || [],
          revisedCount: response.data?.revised_count || 0,
          message: response.message || '质控检测完成'
        }

        showQualityControlResultDialog.value = true

        // 刷新项目数据
        if (loadProject) {
          await loadProject()
        }

        const issueCount = response.data?.quality_report?.issues?.length || 0
        if (issueCount > 0) {
          ElMessage.success(`质控检测完成，发现 ${issueCount} 个问题，已自动修正`)
        } else {
          ElMessage.success('质控检测完成，未发现任何问题')
        }
      } else {
        ElMessage.error(response.message || '质控检测失败')
      }
    } catch (error) {
      console.error('[ProjectDetail] 质控检测失败:', error)
      ElMessage.error('质控检测失败: ' + (error.message || '未知错误'))
    } finally {
      qualityControlLoading.value = false
    }
  }

  return {
    qualityControlLoading,
    showQualityControlResultDialog,
    qualityControlResult,
    handleTriggerQualityControl,
  }
}
