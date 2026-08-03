/**
 * 统一任务展示模型 — 将后端事件映射为前端统一展示对象
 *
 * 模块: domain
 * 文件: taskPresentation.js
 * 功能: 定义用户可见的任务状态、阶段、操作模型
 *
 * 创建时间: 2026-07-24
 * 版本: 1.0.0
 */

// ==================== 状态常量 ====================

/** 任务状态枚举 */
export const TASK_STATUS = {
  QUEUED: 'queued',
  GENERATING: 'generating',
  QUALITY_CONTROL: 'quality_control',
  REVISING: 'revising',
  CANCELLING: 'cancelling',
  INTERRUPTED: 'interrupted',
  FAILED: 'failed',
  COMPLETED: 'completed',
  PENDING: 'pending',
  RUNNING: 'running',
}

/** 终端状态（任务不再变化） */
export const TERMINAL_STATUSES = new Set([
  TASK_STATUS.COMPLETED,
  TASK_STATUS.FAILED,
  TASK_STATUS.INTERRUPTED,
])

/** 活跃状态（任务仍在进行） */
export const ACTIVE_STATUSES = new Set([
  TASK_STATUS.QUEUED,
  TASK_STATUS.GENERATING,
  TASK_STATUS.QUALITY_CONTROL,
  TASK_STATUS.REVISING,
  TASK_STATUS.CANCELLING,
  TASK_STATUS.PENDING,
  TASK_STATUS.RUNNING,
])

// ==================== 状态文案映射 ====================

/** 面向用户的状态标签（不暴露后端内部异常） */
export const STATUS_LABELS = {
  [TASK_STATUS.QUEUED]: '排队中',
  [TASK_STATUS.PENDING]: '等待中',
  [TASK_STATUS.GENERATING]: '生成中',
  [TASK_STATUS.RUNNING]: '运行中',
  [TASK_STATUS.QUALITY_CONTROL]: '质控检查中',
  [TASK_STATUS.REVISING]: '修订中',
  [TASK_STATUS.CANCELLING]: '取消中',
  [TASK_STATUS.INTERRUPTED]: '已中断',
  [TASK_STATUS.FAILED]: '失败',
  [TASK_STATUS.COMPLETED]: '已完成',
}

/** 状态对应的 Element Plus tag type */
export const STATUS_TAG_TYPES = {
  [TASK_STATUS.QUEUED]: 'info',
  [TASK_STATUS.PENDING]: 'info',
  [TASK_STATUS.GENERATING]: 'warning',
  [TASK_STATUS.RUNNING]: 'warning',
  [TASK_STATUS.QUALITY_CONTROL]: 'warning',
  [TASK_STATUS.REVISING]: 'warning',
  [TASK_STATUS.CANCELLING]: 'info',
  [TASK_STATUS.INTERRUPTED]: 'danger',
  [TASK_STATUS.FAILED]: 'danger',
  [TASK_STATUS.COMPLETED]: 'success',
}

// ==================== 阶段定义 ====================

/** 通用生成流程阶段 */
export const GENERAL_PHASES = [
  { key: 'setup', label: '设定', icon: 'Setting' },
  { key: 'material', label: '资料与风格', icon: 'Document' },
  { key: 'generate', label: '生成', icon: 'MagicStick' },
  { key: 'review', label: '审阅', icon: 'View' },
  { key: 'deliver', label: '交付', icon: 'Download' },
]

/** 长篇写作流程阶段 */
export const LONG_FORM_PHASES = [
  { key: 'project_setup', label: '项目设定', icon: 'Folder' },
  { key: 'global_outline', label: '全局大纲', icon: 'Memo' },
  { key: 'unit_summaries', label: '单元概述', icon: 'List' },
  { key: 'writing', label: '正文', icon: 'Edit' },
  { key: 'quality_control', label: '质控', icon: 'CircleCheck' },
  { key: 'finalize', label: '定稿', icon: 'Trophy' },
]

// ==================== 操作定义 ====================

/** 不同状态下可执行的操作 */
export const STATUS_ACTIONS = {
  [TASK_STATUS.QUEUED]: ['cancel'],
  [TASK_STATUS.PENDING]: ['cancel'],
  [TASK_STATUS.GENERATING]: ['cancel', 'open_result'],
  [TASK_STATUS.RUNNING]: ['cancel', 'open_result'],
  [TASK_STATUS.QUALITY_CONTROL]: ['cancel', 'open_result'],
  [TASK_STATUS.REVISING]: ['cancel', 'open_result'],
  [TASK_STATUS.CANCELLING]: [],
  [TASK_STATUS.INTERRUPTED]: ['retry', 'continue', 'open_result'],
  [TASK_STATUS.FAILED]: ['retry', 'open_result'],
  [TASK_STATUS.COMPLETED]: ['open_result', 'export'],
}

/** 操作按钮配置 */
export const ACTION_CONFIG = {
  open_result: { label: '查看结果', icon: 'View', type: 'primary' },
  continue: { label: '继续', icon: 'VideoPlay', type: 'success' },
  retry: { label: '重试', icon: 'Refresh', type: 'warning' },
  cancel: { label: '取消', icon: 'CircleClose', type: 'danger' },
  export: { label: '导出', icon: 'Download', type: 'default' },
}

// ==================== 核心转换函数 ====================

/**
 * 将后端任务事件映射为统一展示对象
 * @param {Object} event - 后端推送事件或任务对象
 * @returns {Object} 标准化任务展示对象
 */
export function toTaskPresentation(event) {
  if (!event) return null

  return {
    id: event.task_id || event.id,
    projectId: event.project_id || null,
    phase: event.type || event.phase || 'unknown',
    status: event.status || 'unknown',
    progress: Math.round((event.progress ?? 0) * 100),
    message: event.message || '',
    canRetry: event.retryable === true || event.status === 'interrupted' || event.status === 'failed',
    contentType: event.content_type || 'unknown',
    moduleType: event.module_type || null,
    createdAt: event.created_at || event.createdAt || null,
    updatedAt: event.updated_at || event.updatedAt || null,
    completedUnits: event.completed_units ?? (event.completedUnits ?? 0),
    totalUnits: event.total_units ?? (event.totalUnits ?? 0),
    route: buildTaskRoute(event),
  }
}

/**
 * 根据任务类型和内容类型生成路由
 */
function buildTaskRoute(event) {
  const contentType = event.content_type || ''
  const taskId = event.task_id || event.id
  const projectId = event.project_id

  // 长篇写作任务 → 工作台
  if (contentType === 'novel' || contentType === 'series_script' || contentType === 'movie_script') {
    return projectId
      ? { name: 'NovelWriterDetail', params: { id: projectId } }
      : { path: '/novel-writer' }
  }

  // 其他创意生成任务 → 生成页
  const moduleType = event.module_type || mapContentTypeToModule(contentType)
  if (moduleType) {
    return { path: `/generate/${moduleType}` }
  }

  // 兜底：历史记录
  return { path: '/history' }
}

/**
 * 内容类型 → 模块路由参数映射
 */
function mapContentTypeToModule(contentType) {
  const map = {
    short_video: 'short-video',
    movie_outline: 'movie-outline',
    series_outline: 'series-outline',
    print_ad: 'print-ad',
    tvc: 'tvc',
    original_ip: 'original-ip',
    practical_writing: 'practical-writing',
    novel: 'novel',
  }
  return map[contentType] || null
}

/**
 * 获取用户可读的状态标签
 * @param {string} status
 * @returns {string}
 */
export function getStatusLabel(status) {
  return STATUS_LABELS[status] || status || '未知'
}

/**
 * 获取状态对应的 tag 类型
 */
export function getStatusTagType(status) {
  return STATUS_TAG_TYPES[status] || 'info'
}

/**
 * 判断是否为终端状态
 */
export function isTerminalStatus(status) {
  return TERMINAL_STATUSES.has(status)
}

/**
 * 判断是否为活跃状态
 */
export function isActiveStatus(status) {
  return ACTIVE_STATUSES.has(status)
}

/**
 * 生成面向用户的简要进度描述
 */
export function getProgressSummary(task) {
  if (!task) return ''
  const total = task.totalUnits || task.total_units || 0
  const completed = task.completedUnits || task.completed_units || 0
  if (total > 0) {
    return `${completed}/${total} 单元完成`
  }
  return task.progress != null ? `${task.progress}%` : ''
}

/**
 * 获取状态下可用的操作列表
 */
export function getAvailableActions(status) {
  return STATUS_ACTIONS[status] || []
}
