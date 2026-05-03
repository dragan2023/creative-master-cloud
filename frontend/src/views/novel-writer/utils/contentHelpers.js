/**
 * 写作工作台 - 内容类型/状态工具函数
 * 
 * @module views/novel-writer/utils/contentHelpers
 */

/**
 * 获取内容类型中文标签
 * @param {string} type - 内容类型 (novel, series_script, movie_script)
 * @returns {string} 中文标签
 */
export function getContentTypeLabel(type) {
  const labels = {
    novel: "小说",
    series_script: "连续剧剧本",
    movie_script: "电影剧本",
  }
  return labels[type] || "小说"
}

/**
 * 获取内容类型对应的 Element Plus Tag 类型
 * @param {string} type - 内容类型
 * @returns {string} Tag 类型 (primary, success, warning)
 */
export function getContentTypeTagType(type) {
  const types = {
    novel: "primary",
    series_script: "success",
    movie_script: "warning",
  }
  return types[type] || "primary"
}

/**
 * 获取任务状态对应的 Element Plus Tag 类型
 * @param {string} status - 任务状态
 * @returns {string} Tag 类型
 */
export function getStatusType(status) {
  const typeMap = {
    pending: "info",
    running: "primary",
    interrupted: "warning",
    completed: "success",
    failed: "danger",
  }
  return typeMap[status] || "info"
}

/**
 * 获取任务状态中文标签
 * @param {string} status - 任务状态
 * @returns {string} 中文标签
 */
export function getStatusLabel(status) {
  const labelMap = {
    pending: "等待中",
    running: "运行中",
    interrupted: "已中断",
    completed: "已完成",
    failed: "失败",
  }
  return labelMap[status] || status
}

/**
 * 格式化数字（千分位）
 * @param {number} num - 数字
 * @returns {string} 格式化后的字符串
 */
export function formatNumber(num) {
  if (num === undefined || num === null) return "0"
  return num.toLocaleString()
}

/**
 * 获取场景状态对应的 Element Plus Tag 类型
 * @param {string} status - 场景状态
 * @returns {string} Tag 类型
 */
export function getSceneStatusType(status) {
  const typeMap = {
    pending: "info",
    writing: "primary",
    reviewing: "warning",
    completed: "success",
    failed: "danger",
  }
  return typeMap[status] || "info"
}

/**
 * 获取场景状态中文标签
 * @param {string} status - 场景状态
 * @returns {string} 中文标签
 */
export function getSceneStatusLabel(status) {
  const labelMap = {
    pending: "等待中",
    writing: "写作中",
    reviewing: "审阅中",
    completed: "已完成",
    failed: "失败",
  }
  return labelMap[status] || status
}

/**
 * 格式化绝对时间戳为中文时间字符串
 * @param {number|string} timestamp - 时间戳
 * @returns {string} 格式化后的时间字符串
 */
export function formatTime(timestamp) {
  if (!timestamp) return ""
  const date = new Date(timestamp)
  return date.toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  })
}

/**
 * 格式化日期时间字符串
 * @param {string} str - ISO日期字符串
 * @returns {string} 本地化日期时间
 */
export function formatDateTime(str) {
  if (!str) return ''
  return new Date(str).toLocaleString()
}

/**
 * 合规审核问题类型标签映射
 */
const ISSUE_TYPE_LABELS = {
  'sensitive_word': '敏感词',
  'sensitive_name': '敏感人名',
  'sensitive_place': '敏感地名',
  'sensitive_event': '历史事件'
}

/**
 * 获取问题类型中文标签
 * @param {string} type - 问题类型
 * @returns {string} 中文标签
 */
export function getIssueTypeLabel(type) {
  return ISSUE_TYPE_LABELS[type] || type
}
