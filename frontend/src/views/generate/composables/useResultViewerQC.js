/**
 * ResultViewer 质控逻辑组合式函数
 *
 * 封装全局大纲质控、单元概述质控、质控进度展示等逻辑。
 * 从 ResultViewer.vue 提取，减少主组件体积。
 */
import { computed } from 'vue'
import { ElMessage } from 'element-plus'
import { qualityControlApi } from '@/api'

export function useResultViewerQC(props, emit) {
  // ==================== 质控按钮文字 ====================

  const getQCButtonText = computed(() => {
    if (props.globalOutlineQCLoading) {
      return '检测中...'
    }
    if (props.globalOutlineQCReport) {
      if (props.globalOutlineQCReport.overall_score >= 80) {
        return '重新检测'
      }
      return '一键修正并重新检测'
    }
    return '质量检测'
  })

  // ==================== 重连状态 ====================

  const isReconnecting = computed(() => {
    return props.qcProgress?.status === 'reconnecting'
  })

  const reconnectMessage = computed(() => {
    return props.qcProgress?.message || '连接中断，正在重连...'
  })

  // ==================== 全局大纲质控 ====================

  async function handleGlobalOutlineQC() {
    // 两阶段模式允许projectId为空（后端支持project_id=0）
    // 如果projectId为空，会传递0给后端，表示两阶段大纲模式
    emit('global-outline-qc')
  }

  // ==================== 单元概述质控 ====================

  async function handleUnitSummariesQC() {
    // 两阶段模式允许projectId为空（后端支持project_id=0）
    emit('quality-control-unit-summaries')
  }

  // ==================== 质控进度辅助 ====================

  function getProgressColor(progress) {
    if (progress < 30) return '#f56c6c'
    if (progress < 70) return '#e6a23c'
    return '#67c23a'
  }

  function getProgressStatusType(status) {
    const map = {
      analyzing: 'info',
      checking: 'warning',
      generating_report: 'primary',
      reconnecting: 'warning',
      completed: 'success',
      failed: 'danger'
    }
    return map[status] || 'info'
  }

  function getDimensionLabel(dim) {
    const map = {
      logic: '逻辑一致性',
      character: '人物设定',
      plot: '情节结构',
      setting: '世界观设定',
      pacing: '节奏把控',
      language: '语言风格'
    }
    return map[dim] || dim
  }

  function getDimensionName(dim) {
    return getDimensionLabel(dim)
  }

  function getScoreType(score) {
    if (score >= 80) return 'success'
    if (score >= 60) return 'warning'
    return 'danger'
  }

  function getScoreColor(score) {
    if (score >= 80) return '#67c23a'
    if (score >= 60) return '#e6a23c'
    return '#f56c6c'
  }

  function getSeverityType(severity) {
    const map = { critical: 'danger', major: 'warning', minor: 'info' }
    return map[severity] || 'info'
  }

  function getSeverityLabel(severity) {
    const map = {
      critical: '严重',
      major: '重要',
      minor: '建议'
    }
    return map[severity] || severity
  }

  // ==================== 新增：按严重程度分组问题 ====================
  
  function groupIssuesBySeverity(issues) {
    if (!issues || !Array.isArray(issues)) {
      return { critical: [], major: [], minor: [] }
    }
    
    return {
      critical: issues.filter(issue => issue.severity === 'critical'),
      major: issues.filter(issue => issue.severity === 'major'),
      minor: issues.filter(issue => issue.severity === 'minor')
    }
  }

  return {
    getQCButtonText,
    isReconnecting,
    reconnectMessage,
    handleGlobalOutlineQC,
    handleUnitSummariesQC,
    getProgressColor,
    getProgressStatusType,
    getDimensionLabel,
    getDimensionName,
    getScoreType,
    getScoreColor,
    getSeverityType,
    getSeverityLabel,
    groupIssuesBySeverity
  }
}
