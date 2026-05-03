/**
 * 创意模块统一配置
 * 
 * 新增模块只需在此注册，无需修改其他文件。
 * 
 * @date: 2026-04-02
 * @version: v3.0.0
 * @author: 周金磊
 */

/**
 * 模块详细配置
 * 每个模块包含前端展示和API调用所需的全部信息
 */
export const MODULE_CONFIGS = {
  // 短视频脚本
  'short-video': {
    id: 'short-video',
    name: '短视频脚本',
    title: '短视频脚本',
    description: '为抖音、快手等平台生成短视频脚本',
    apiMethod: 'shortVideo',
    apiEndpoint: '/api/v1/generate/short-video/stream',
    icon: 'VideoCamera',
    color: '#FF6B6B',
    backendModuleId: 'short_video',
    kbCategory: 'short-video',
    features: {
      knowledge: true,
      search: true,
      trending: true,
      mcp: true,
      images: false,
      videos: true,
    },
  },
  // 平面广告
  'print-ad': {
    id: 'print-ad',
    name: '平面广告',
    title: '平面广告',
    description: 'Logo、海报、宣传单、包装等多类型平面设计',
    apiMethod: 'printAd',
    apiEndpoint: '/api/v1/generate/print-ad/stream',
    icon: 'Picture',
    color: '#96CEB4',
    backendModuleId: 'print_ad',
    kbCategory: 'print-ad',
    features: {
      knowledge: true,
      search: true,
      trending: true,
      mcp: true,
      images: true,
      videos: false,
    },
  },
  // TVC广告脚本
  'tvc': {
    id: 'tvc',
    name: 'TVC广告脚本',
    title: 'TVC广告脚本',
    description: '电视广告、商业视频脚本',
    apiMethod: 'tvc',
    apiEndpoint: '/api/v1/generate/tvc/stream',
    icon: 'Film',
    color: '#FFEAA7',
    backendModuleId: 'tvc',
    kbCategory: 'tvc',
    features: {
      knowledge: true,
      search: true,
      trending: true,
      mcp: true,
      images: false,
      videos: true,
    },
  },
  // 原创IP计划
  'original-ip': {
    id: 'original-ip',
    name: '原创IP计划',
    title: '原创IP计划',
    description: '从概念到落地的完整角色IP构建',
    apiMethod: 'originalIp',
    apiEndpoint: '/api/v1/generate/original-ip/stream',
    icon: 'Avatar',
    color: '#A855F7',
    backendModuleId: 'original_ip',
    kbCategory: 'general',
    features: {
      knowledge: true,
      search: true,
      trending: false,
      mcp: false,
      images: false,
      videos: false,
    },
  },
  // 小说大纲
  'novel': {
    id: 'novel',
    name: '小说大纲',
    title: '小说大纲',
    description: '网络小说、短篇故事大纲创作',
    apiMethod: 'novel',
    apiEndpoint: '/api/v1/generate/novel/stream',
    icon: 'Notebook',
    color: '#45B7D1',
    backendModuleId: 'novel',
    kbCategory: 'novel',
    features: {
      knowledge: true,
      search: true,
      trending: true,
      mcp: true,
      images: false,
      videos: false,
    },
  },
  // 电影大纲
  'movie-outline': {
    id: 'movie-outline',
    name: '电影大纲',
    title: '电影大纲',
    description: '院线电影、网络电影、微电影、纪录片、动画电影大纲生成',
    apiMethod: 'movieOutline',
    apiEndpoint: '/api/v1/generate/movie-outline/stream',
    icon: 'Film',
    color: '#E8B86D',
    backendModuleId: 'movie_outline',
    kbCategory: 'movie-outline',
    features: {
      knowledge: true,
      search: true,
      trending: true,
      mcp: true,
      images: false,
      videos: false,
    },
  },
  // 剧集大纲
  'series-outline': {
    id: 'series-outline',
    name: '剧集大纲',
    title: '剧集大纲',
    description: '电视剧、网络剧、短剧、微短剧、竖屏剧、长剧大纲生成',
    apiMethod: 'seriesOutline',
    apiEndpoint: '/api/v1/generate/series-outline/stream',
    icon: 'VideoCamera',
    color: '#4ECDC4',
    backendModuleId: 'series_outline',
    kbCategory: 'series-outline',
    features: {
      knowledge: true,
      search: true,
      trending: true,
      mcp: true,
      images: false,
      videos: false,
    },
  },
}

/**
 * 模块名称映射（便于快速查找）
 * key: 前端路由参数值
 * value: 模块显示名称
 */
export const MODULE_NAMES = {}
Object.entries(MODULE_CONFIGS).forEach(([key, config]) => {
  MODULE_NAMES[key] = config.name
})

/**
 * 后端模块ID映射
 * key: 后端模块标识符
 * value: 前端模块配置
 */
export const BACKEND_MODULE_MAP = {}
Object.entries(MODULE_CONFIGS).forEach(([key, config]) => {
  BACKEND_MODULE_MAP[config.backendModuleId] = config
})

/**
 * 获取模块配置
 * 
 * @param {string} moduleId - 模块ID（前端路由参数值）
 * @returns {Object|null} 模块配置对象，未找到返回 null
 */
export function getModuleConfig(moduleId) {
  const config = MODULE_CONFIGS[moduleId]
  if (!config) {
    console.warn(`未知的模块: ${moduleId}`)
    return null
  }
  return config
}

/**
 * 根据后端模块ID获取配置
 * 
 * @param {string} backendModuleId - 后端模块标识符
 * @returns {Object|null} 模块配置对象，未找到返回 null
 */
export function getModuleConfigByBackendId(backendModuleId) {
  const config = BACKEND_MODULE_MAP[backendModuleId]
  if (!config) {
    console.warn(`未知的后端模块: ${backendModuleId}`)
    return null
  }
  return config
}

/**
 * 获取所有模块ID列表
 * 
 * @returns {string[]} 模块ID列表
 */
export function getAllModuleIds() {
  return Object.keys(MODULE_CONFIGS)
}

/**
 * 获取所有模块配置列表
 * 
 * @returns {Object[]} 模块配置数组
 */
export function getAllModuleConfigs() {
  return Object.values(MODULE_CONFIGS)
}

/**
 * 获取模块显示名称
 * 
 * @param {string} moduleId - 模块ID
 * @returns {string} 模块显示名称，未找到返回模块ID
 */
export function getModuleDisplayName(moduleId) {
  const config = getModuleConfig(moduleId)
  return config?.name || moduleId
}

/**
 * 检查模块是否支持某功能
 * 
 * @param {string} moduleId - 模块ID
 * @param {string} feature - 功能名称 (knowledge, search, trending, mcp, images, videos)
 * @returns {boolean} 是否支持
 */
export function moduleSupportsFeature(moduleId, feature) {
  const config = getModuleConfig(moduleId)
  if (!config) return false
  return config.features?.[feature] || false
}

/**
 * 获取支持指定功能的所有模块
 * 
 * @param {string} feature - 功能名称
 * @returns {Object[]} 支持该功能的模块配置数组
 */
export function getModulesByFeature(feature) {
  return Object.values(MODULE_CONFIGS).filter(
    config => config.features?.[feature]
  )
}

/**
 * 获取知识库分类对应的模块
 * 
 * @param {string} kbCategory - 知识库分类键
 * @returns {Object|null} 模块配置对象
 */
export function getModuleByKbCategory(kbCategory) {
  return Object.values(MODULE_CONFIGS).find(
    config => config.kbCategory === kbCategory
  ) || null
}

/**
 * 向后兼容：创意模块列表（用于首页展示）
 * 与原有的 CREATIVE_MODULES 格式保持一致
 */
export const CREATIVE_MODULES = Object.values(MODULE_CONFIGS).map(config => ({
  key: config.id,
  title: config.title,
  icon: config.icon,
  description: config.description,
  color: config.color,
}))

/**
 * 向后兼容：模块名称映射
 * key: 后端返回的下划线格式
 * value: 前端显示名称
 */
export const MODULE_NAME_MAP = {}
Object.values(MODULE_CONFIGS).forEach(config => {
  MODULE_NAME_MAP[config.backendModuleId] = config.name
})

/**
 * 向后兼容：模块标签类型映射
 * 用于 el-tag 组件的 type 属性
 */
export const MODULE_TAG_TYPES = {
  'short-video': 'danger',
  'movie-outline': 'warning',
  'series-outline': 'success',
  'novel': 'primary',
  'print-ad': 'warning',
  'tvc': 'info',
  'original-ip': 'purple',
}

export default MODULE_CONFIGS
