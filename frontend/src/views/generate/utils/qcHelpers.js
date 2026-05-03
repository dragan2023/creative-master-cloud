/**
 * 质量管控相关纯工具函数
 *
 * 提取自 ResultViewer.vue，不依赖组件状态，可复用
 */

/** 根据分数返回 Element Plus 标签类型 */
export function getScoreType(score) {
  if (!score) return 'info'
  if (score >= 90) return 'success'
  if (score >= 70) return 'primary'
  if (score >= 60) return 'warning'
  return 'danger'
}

/** 根据分数返回颜色值 */
export function getScoreColor(score) {
  if (score >= 90) return '#67c23a'
  if (score >= 70) return '#409eff'
  if (score >= 60) return '#e6a23c'
  return '#f56c6c'
}

/** 根据进度百分比返回颜色值 */
export function getProgressColor(progress) {
  if (progress >= 80) return '#67c23a'
  if (progress >= 50) return '#409eff'
  if (progress >= 20) return '#e6a23c'
  return '#909399'
}

/** 根据进度状态返回 Element Plus 标签类型 */
export function getProgressStatusType(status) {
  switch (status) {
    case 'running': return 'primary'
    case 'success': return 'success'
    case 'failed': return 'danger'
    case 'completed': return 'success'
    case 'error': return 'danger'
    case 'reconnecting': return 'warning'
    default: return 'info'
  }
}

/** 根据维度键名返回中文标签 */
export function getDimensionLabel(dim) {
  const labels = {
    unit_structure: '单元结构',
    unit_character: '人物发展',
    unit_consistency: '大纲一致性',
    unit_timeline_space: '时间线空间',
    unit_ooc: '人物OOC',
    // 全局大纲四维度 (v1.1新增)
    global_structure: '宏观结构',
    global_character_worldview: '人物与世界观',
    global_plot_consistency: '剧情线一致性',
    global_storyline_integrity: '故事线完整性'
  }
  return labels[dim] || dim
}

/** getDimensionLabel 别名（兼容全局大纲质控模板） */
export const getDimensionName = getDimensionLabel

/** 根据严重程度返回 Element Plus 标签类型 */
export function getSeverityType(severity) {
  const types = {
    critical: 'danger',
    warning: 'warning',
    info: 'info'
  }
  return types[severity] || 'info'
}

/** 根据严重程度返回中文标签 */
export function getSeverityLabel(severity) {
  const labels = {
    critical: '严重',
    warning: '警告',
    info: '提示'
  }
  return labels[severity] || severity
}
