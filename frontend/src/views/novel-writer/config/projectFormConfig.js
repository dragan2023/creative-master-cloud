/**
 * projectFormConfig.js - 项目表单常量配置
 *
 * 集中管理 Index.vue 中的内容类型提示、默认配置、平台选项等常量
 */
// ==================== 内容类型提示 ====================
export const CONTENT_TYPE_HINTS = {
  'novel': '小说：根据大纲生成章节正文，每章约3000字',
  'series_script': '剧集剧本：根据大纲生成分集剧本，支持电视剧/网络剧/短剧等',
  'movie_script': '电影剧本：根据大纲生成场景剧本，支持院线电影/网络电影等'
}

// ==================== 小说配置默认值 ====================
export const DEFAULT_NOVEL_CONFIG = {
  target_platform: '',
  total_words: null,
  words_per_chapter: 3000,
  temperature: 0.8,
  narrative_perspective: '第三人称'
}

// ==================== 剧集剧本配置默认值 ====================
// 注意：剧本以"时长"为核心指标，字数仅供参考
export const DEFAULT_SERIES_SCRIPT_CONFIG = {
  series_type: '电视剧',
  narrative_mode: 'serialized',     // 叙事模式: serialized=连续剧, episodic_with_arc=主线串联单元剧, episodic=纯单元剧
  episode_duration_range: null,
  scenes_per_episode_range: null,
  format_standard: '标准格式',
  dialogue_narration_ratio: '均衡',
  target_broadcast: '',
  episode_count: 24,
  dialogue_style: '自然对话',
  narrative_rhythm: '紧凑',
  script_mode: 'real',
  words_per_episode: null
}

// ==================== 电影剧本配置默认值 ====================
// 注意：电影剧本以"时长"为核心指标
export const DEFAULT_MOVIE_SCRIPT_CONFIG = {
  movie_type: '院线电影',
  narrative_mode: 'serialized',     // 叙事模式: serialized=连续叙事, episodic_with_arc=主线串联单元电影, episodic=纯单元电影
  total_duration: null,
  format_standard: '标准格式',
  dialogue_narration_ratio: '均衡',
  target_platform: '',
  dialogue_style: '自然对话',
  narrative_rhythm: '紧凑',
  script_mode: 'real'
}

// ==================== 剧集类型对应的时长配置 ====================
export const SERIES_DURATION_CONFIG = {
  '电视剧': { min: 40, max: 60, defaultMin: 45, defaultMax: 50, hint: '电视剧通常45-50分钟/集' },
  '网络剧': { min: 20, max: 50, defaultMin: 30, defaultMax: 45, hint: '网络剧通常30-45分钟/集' },
  '短剧': { min: 3, max: 20, defaultMin: 5, defaultMax: 15, hint: '短剧通常5-15分钟/集' },
  '微短剧': { min: 1, max: 10, defaultMin: 3, defaultMax: 8, hint: '微短剧通常3-8分钟/集' },
  '网剧': { min: 20, max: 50, defaultMin: 30, defaultMax: 45, hint: '网剧通常30-45分钟/集' },
  '竖屏剧': { min: 1, max: 5, defaultMin: 1, defaultMax: 3, hint: '竖屏剧通常1-3分钟/集' }
}

// ==================== 电影类型对应的时长配置 ====================
export const MOVIE_DURATION_CONFIG = {
  '院线电影': { default: 120, min: 60, max: 180, hint: '院线电影通常90-120分钟' },
  '网络电影': { default: 90, min: 45, max: 120, hint: '网络电影通常60-90分钟' },
  '微电影': { default: 30, min: 10, max: 60, hint: '微电影通常20-45分钟' },
  '纪录片': { default: 90, min: 30, max: 180, hint: '纪录片时长灵活' },
  '动画电影': { default: 90, min: 60, max: 120, hint: '动画电影通常80-100分钟' }
}

// ==================== 剧本格式标准选项 ====================
export const FORMAT_STANDARD_OPTIONS = [
  { value: '标准格式', label: '标准格式', desc: '包含场景头、角色名、动作描述、对白等完整元素' },
  { value: '简格式', label: '简格式', desc: '精简场景描述，突出对白核心' },
  { value: '网络平台格式', label: '网络平台格式', desc: '适配流媒体平台，节奏快、信息密度高' },
  { value: '短剧格式', label: '短剧格式', desc: '单场戏结构清晰，适合竖屏观看' }
]

// ==================== 对白与叙述比例选项 ====================
export const DIALOGUE_RATIO_OPTIONS = [
  { value: '对话为主', label: '对话为主', desc: '60%以上为对白' },
  { value: '均衡', label: '均衡', desc: '对白与动作描述各占约50%' },
  { value: '叙述为主', label: '叙述为主', desc: '侧重场景描述' },
  { value: '动作导向', label: '动作导向', desc: '以动作描述为主' }
]

// ==================== 投放平台选项 ====================
export const TARGET_BROADCAST_OPTIONS = [
  '央视', '地方卫视', '爱奇艺', '腾讯视频', '优酷', '芒果TV', 'B站', '抖音', '快手', 'Netflix', '院线发行'
]

// ==================== 小说投放平台选项 ====================
export const NOVEL_PLATFORM_OPTIONS = [
  '起点中文网', '晋江文学城', '番茄小说', '豆瓣阅读', '纵横中文网', '17K小说网', '飞卢小说', '其他'
]

// ==================== 以下为与类型相关的辅助函数 ====================

/**
 * 根据剧集类型更新时长范围
 */
export function updateSeriesDurationByType(projectForm, seriesType) {
  const config = SERIES_DURATION_CONFIG[seriesType]
  if (config && projectForm.series_script_config) {
    projectForm.series_script_config.episode_duration_range = [config.defaultMin, config.defaultMax]
  }
}

/**
 * 根据电影类型更新时长
 */
export function updateMovieDurationByType(projectForm, movieType) {
  const config = MOVIE_DURATION_CONFIG[movieType]
  if (config && projectForm.movie_script_config) {
    projectForm.movie_script_config.total_duration = config.default
  }
}

/**
 * 获取剧集时长的最小值限制
 */
export function getSeriesDurationMin(projectForm) {
  const seriesType = projectForm.series_script_config?.series_type || '电视剧'
  const config = SERIES_DURATION_CONFIG[seriesType]
  return config?.min || 1
}

/**
 * 获取剧集时长的最大值限制
 */
export function getSeriesDurationMax(projectForm) {
  const seriesType = projectForm.series_script_config?.series_type || '电视剧'
  const config = SERIES_DURATION_CONFIG[seriesType]
  return config?.max || 120
}

/**
 * 获取剧集时长的提示信息
 */
export function getSeriesDurationHint(projectForm) {
  const seriesType = projectForm.series_script_config?.series_type || '电视剧'
  const config = SERIES_DURATION_CONFIG[seriesType]
  return config?.hint || ''
}

/**
 * 获取电影时长的最小值限制
 */
export function getMovieDurationMin(projectForm) {
  const movieType = projectForm.movie_script_config?.movie_type || '院线电影'
  const config = MOVIE_DURATION_CONFIG[movieType]
  return config?.min || 5
}

/**
 * 获取电影时长的最大值限制
 */
export function getMovieDurationMax(projectForm) {
  const movieType = projectForm.movie_script_config?.movie_type || '院线电影'
  const config = MOVIE_DURATION_CONFIG[movieType]
  return config?.max || 180
}

/**
 * 获取电影时长的提示信息
 */
export function getMovieDurationHint(projectForm) {
  const movieType = projectForm.movie_script_config?.movie_type || '院线电影'
  const config = MOVIE_DURATION_CONFIG[movieType]
  return config?.hint || ''
}
