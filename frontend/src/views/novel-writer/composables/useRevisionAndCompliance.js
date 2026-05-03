/**
 * useRevisionAndCompliance - 修正对比与合规审核管理
 * 从 ProjectDetail.vue 中提取
 */
import { ElMessage } from 'element-plus'

export function useRevisionAndCompliance(options) {
  const {
    projectId, project,
    revisionCompareVisible, originalDraftContent, revisedContent,
    chapterRevisionInfo, revisionViewMode,
    complianceDetailVisible, complianceDetailData, chapterComplianceMarking,
    showComplianceDetail
  } = options

  function showRevisionCompareDialog() {
    revisionCompareVisible.value = true
  }

  return {
    showRevisionCompareDialog
  }
}
