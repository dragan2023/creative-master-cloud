/**
 * 表单状态和逻辑 composable
 * 管理所有表单字段、验证规则、上传功能等
 */
import { ref, computed, watch, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import { generateApi } from '@/api'
import { getAuthHeaders } from '@/utils/authStorage'
import { debounce } from '@/utils/debounce'

// 风格类型配置（两级，独立选择）
export const styleTypes = [
  { name: '反差', children: ['身份反差', '场景反差', '预期违背', '反转剧情'] },
  { name: '幽默/搞笑', children: ['冷幽默', '热梗模仿', '脱口秀', '无厘头', '讽刺', '谐音梗'] },
  { name: '情感共鸣', children: ['亲情', '友情', '爱情', '治愈', '励志', '怀旧', '遗憾', '孤独'] },
  { name: '知识科普', children: ['冷知识', '专业技能', '历史人文', '科学实验', '法律科普'] },
  { name: '生活Vlog', children: ['日常碎片', '学习打卡', '旅行日记', '做饭日常', '独居生活'] },
  { name: '测评/评测', children: ['数码测评', '美食探店', '好物开箱', '雷品吐槽', '实地测评'] },
  { name: '教程/教学', children: ['美妆教程', '穿搭教程', '手工DIY', '软件教学', '语言学习'] },
  { name: '采访/街访', children: ['随机采访', '情侣问答', '职场访谈', '挑战路人'] },
  { name: '才艺展示', children: ['唱歌', '跳舞', '乐器演奏', '绘画过程', '魔术表演', '杂技'] },
  { name: '解压/治愈', children: ['沉浸式整理', 'ASMR', '切肥皂', '手工制作', '风景大片'] },
  { name: '挑战/互动', children: ['挑战XX天', '粉丝点单', '投票选结局', '猜谜游戏'] },
  { name: '创意视觉', children: ['卡点变装', '运镜转场', 'AI生成画面', '特效合成'] },
  { name: '正能量/励志', children: ['凡人善举', '逆袭故事', '坚持梦想', '暖心瞬间'] },
  { name: '盘点/合集', children: ['年度盘点', 'XX种方法', '必看片单', '奇葩合集'] },
  { name: '观点/评论', children: ['热点辣评', '三观输出', '行业吐槽', '人生感悟'] },
  { name: '沉浸式体验', children: ['沉浸式回家', '沉浸式化妆', '沉浸式逛展', '第一人称视角'] }
]

// 题材类型选项
export const genres = ['爱情', '喜剧', '悬疑', '科幻', '奇幻', '动作', '剧情', '历史', '都市', '青春', '恐怖', '犯罪', '惊悚', '灾难']

// 剧集类型选项（旧剧本大纲用，保留向后兼容）
export const seriesTypes = ['院线电影', '网络电影', '长剧', '短剧', '微电影', '纪录片', '动画电影', '网络剧', '竖屏剧']

// 电影大纲 - 电影类型选项
export const movieTypes = ['院线电影', '网络电影', '微电影', '纪录片', '动画电影']

// 剧集大纲 - 剧集类型选项
export const seriesTypesOnly = ['电视剧', '网络剧', '短剧', '微短剧', '竖屏剧', '长剧']

// 剧集类型对应的时长配置（旧剧本大纲用）
export const SERIES_DURATION_CONFIG = {
  '院线电影': { min: 90, max: 150, defaultMin: 100, defaultMax: 120, hint: '院线电影通常90-120分钟' },
  '网络电影': { min: 60, max: 120, defaultMin: 80, defaultMax: 100, hint: '网络电影通常80-100分钟' },
  '长剧': { min: 40, max: 60, defaultMin: 45, defaultMax: 50, hint: '长剧通常45-50分钟/集' },
  '短剧': { min: 3, max: 20, defaultMin: 5, defaultMax: 15, hint: '短剧通常5-15分钟/集' },
  '微电影': { min: 5, max: 40, defaultMin: 15, defaultMax: 30, hint: '微电影通常15-30分钟' },
  '纪录片': { min: 30, max: 60, defaultMin: 40, defaultMax: 50, hint: '纪录片通常40-50分钟/集' },
  '动画电影': { min: 80, max: 120, defaultMin: 90, defaultMax: 100, hint: '动画电影通常90-100分钟' },
  '网络剧': { min: 20, max: 50, defaultMin: 30, defaultMax: 45, hint: '网络剧通常30-45分钟/集' },
  '竖屏剧': { min: 2, max: 10, defaultMin: 3, defaultMax: 5, hint: '竖屏剧通常3-5分钟/集' }
}

// 电影大纲 - 电影类型对应的整片时长配置
export const MOVIE_DURATION_CONFIG = {
  '院线电影': { min: 90, max: 180, defaultMin: 100, defaultMax: 120, hint: '院线电影通常90-120分钟' },
  '网络电影': { min: 60, max: 120, defaultMin: 80, defaultMax: 100, hint: '网络电影通常80-100分钟' },
  '微电影': { min: 5, max: 40, defaultMin: 15, defaultMax: 30, hint: '微电影通常15-30分钟' },
  '纪录片': { min: 60, max: 150, defaultMin: 80, defaultMax: 120, hint: '纪录片通常80-120分钟' },
  '动画电影': { min: 80, max: 120, defaultMin: 90, defaultMax: 100, hint: '动画电影通常90-100分钟' }
}

// 剧集大纲 - 剧集类型对应的每集时长配置
export const SERIES_EPISODE_DURATION_CONFIG = {
  '电视剧': { min: 40, max: 60, defaultMin: 45, defaultMax: 50, hint: '电视剧通常45-50分钟/集' },
  '网络剧': { min: 20, max: 50, defaultMin: 30, defaultMax: 45, hint: '网络剧通常30-45分钟/集' },
  '短剧': { min: 3, max: 20, defaultMin: 5, defaultMax: 15, hint: '短剧通常5-15分钟/集' },
  '微短剧': { min: 1, max: 5, defaultMin: 2, defaultMax: 3, hint: '微短剧通常2-3分钟/集' },
  '竖屏剧': { min: 2, max: 10, defaultMin: 3, defaultMax: 5, hint: '竖屏剧通常3-5分钟/集' },
  '长剧': { min: 40, max: 60, defaultMin: 45, defaultMax: 50, hint: '长剧通常45-50分钟/集' }
}

// 投放平台选项
export const platforms = ['央视', '地方卫视', '爱奇艺', '腾讯视频', '优酷', '芒果TV', 'B站', '抖音', '快手', '西瓜视频', '红果短剧', '河马剧场', 'Netflix', 'HBO', 'Disney+', '院线发行', '电影节展映']

export function useGenerationForm(type, router) {
  // 表单引用
  const formRef = ref()

  // 表单数据
  const form = ref({
    title: '',
    description: '',
    target_audience: '',
    duration: '',
    platform: '',
    genre: [],
    length: '',
    ad_type: '',
    product: '',
    // 剧本大纲新增字段
    series_type: '',
    reference_works: '',
    episode_count: '',
    // 电影大纲新增字段
    movie_type: '',
    scene_count: '',
    duration_range: [90, 120],
    scene_count_range: '',
    custom_outline: '',
    custom_outline_name: '',
    // 剧本专用配置参数
    episode_duration_range: [5, 15],
    scenes_per_episode_range: '',
    format_standard: '标准格式',
    dialogue_narration_ratio: '均衡',
    target_broadcast: '',
    script_mode: 'real',
    // 小说新增字段
    target_platform: '',
    tone: '',
    theme: '',
    unique_selling_point: '',
    chapter_count: '',
    // 平面设计新增字段
    design_category: '',
    brand_product: '',
    ad_purpose: '',
    core_message: '',
    audience_profile: '',
    contact_scene: '',
    style_tone: '',
    copy_content: '',
    size_spec: '',
    publish_media: '',
    ai_platforms_ad: '',
    // TVC新增字段
    broadcast_platform: '',
    tvc_mode: 'real',
    generate_ai_prompt_tvc: false,
    ai_platforms_tvc: '',
    // 多模态支持
    images: [],
    reference_video: '',
    // 短视频新增字段
    video_mode: 'virtual',
    style_types: [],
    style_types_level1: [],
    generate_ai_prompt: false,
    generate_storyboard_images: true,
    ai_platforms: [],
    // 短视频运营相关变量
    account_tone: '',
    target_fans: '',
    content_position: '',
    // 短视频参考资料上传
    reference_materials: '',
    reference_materials_name: '',
    // 原创IP计划字段
    ip_description: '',
    reference_ip: '',
    commercial_goal: '',
    custom_requirements: '',
    // 应用文写作-参考文档上传
    reference_document: '',
    reference_document_name: '',
    // 应用文写作-自定义文档长度
    doc_length_custom: ''
  })

  // 验证规则
  const rules = {
    title: [{ required: true, message: '请输入标题', trigger: 'blur' }],
    description: [{ required: true, message: '请输入内容', trigger: 'blur' }],
    target_audience: [{ required: true, message: '请输入目标受众', trigger: 'blur' }],
    ip_description: [{ required: true, min: 10, message: '请至少输入10个字符的IP角色描述', trigger: 'blur' }]
  }

  // 图片上传相关
  const imageFileList = ref([])
  const imageUrlInput = ref('')
  
  // 上传URL和Headers（通过集中化存储层）
  const uploadUrl = computed(() => `${import.meta.env.VITE_API_BASE_URL || ''}/api/v1/generate/upload`)
  const uploadHeaders = computed(() => getAuthHeaders())

  // 大纲上传状态
  const uploading_outline = ref(false)
  const outline_upload_progress = ref(0)

  // 参考资料上传状态
  const uploading_reference_materials = ref(false)
  const reference_materials_upload_progress = ref(0)

  // 应用文参考文档上传状态
  const uploading_reference_doc = ref(false)
  const reference_doc_upload_progress = ref(0)

  // 提示词优化状态
  const optimizing = ref(false)
  const optimizeTarget = ref('')

  // 是否使用两阶段生成模式
  const useTwoStageMode = computed(() => type.value === 'novel' || type.value === 'movie-outline' || type.value === 'series-outline')

  // 组合风格类型字符串
  const combinedStyleTypes = computed(() => {
    const level1 = form.value.style_types_level1 || []
    const level2 = form.value.style_types || []
    return [...level1, ...level2].join('+')
  })

  // 剧集类型时长提示
  const seriesDurationHint = computed(() => {
    const seriesType = form.value.series_type
    if (seriesType && SERIES_DURATION_CONFIG[seriesType]) {
      return SERIES_DURATION_CONFIG[seriesType].hint
    }
    return ''
  })

  // 电影类型时长提示
  const movieDurationHint = computed(() => {
    const mt = form.value.movie_type
    if (mt && MOVIE_DURATION_CONFIG[mt]) {
      return MOVIE_DURATION_CONFIG[mt].hint
    }
    return ''
  })

  // 剧集类型（剧集大纲）时长提示
  const seriesEpisodeDurationHint = computed(() => {
    const st = form.value.series_type
    if (st && SERIES_EPISODE_DURATION_CONFIG[st]) {
      return SERIES_EPISODE_DURATION_CONFIG[st].hint
    }
    return ''
  })

  // 上传前验证（图片）
  const beforeUpload = (file) => {
    const isImage = ['image/png', 'image/jpeg', 'image/jpg', 'image/gif', 'image/webp'].includes(file.type)
    const isLt50M = file.size / 1024 / 1024 < 50
    
    if (!isImage) {
      ElMessage.error('只能上传图片文件！')
      return false
    }
    if (!isLt50M) {
      ElMessage.error('图片大小不能超过50MB！')
      return false
    }
    return true
  }

  // 上传前验证（大纲文件）
  const beforeOutlineUpload = (file) => {
    const allowedExtensions = ['.txt', '.md', '.doc', '.docx', '.pdf']
    const fileExtension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
    
    if (!allowedExtensions.includes(fileExtension)) {
      ElMessage.error('只支持上传 .txt, .md, .doc, .docx, .pdf 格式的文件！')
      return false
    }
    if (file.size / 1024 / 1024 > 100) {
      ElMessage.error('文件大小不能超过100MB！')
      return false
    }
    uploading_outline.value = true
    outline_upload_progress.value = 0
    return true
  }

  // 大纲文件上传进度
  const handleOutlineProgress = (event) => {
    outline_upload_progress.value = Math.round(event.percent)
  }

  // 大纲文件上传成功
  // 注意：参数可能有两种格式：
  // 1. 直接调用：(response, file) - response 是 API 响应对象
  // 2. 事件传递：({ response, file }) - 第一个参数是包含 response 和 file 的对象
  const handleOutlineUploadSuccess = (data, fileOrUndefined) => {
    uploading_outline.value = false
    outline_upload_progress.value = 100
    
    // 判断参数格式：如果 data.response 存在，说明是事件传递格式
    let response, file
    if (data && data.response && data.file) {
      // 事件传递格式：{ response, file }
      response = data.response
      file = data.file
    } else {
      // 直接调用格式：(response, file)
      response = data
      file = fileOrUndefined
    }
    
    console.log('[Upload] 大纲上传响应:', JSON.stringify(response, null, 2))
    console.log('[Upload] response.code:', response.code, 'response.data:', response.data, 'file.name:', file?.name)
    
    if ((response.code === 0 || response.code === 200) && response.data?.url) {
      form.value.custom_outline = response.data.url
      form.value.custom_outline_name = file?.name || '已上传文件'
      ElMessage.success('大纲文件上传成功')
    } else {
      console.error('[Upload] 大纲上传失败，响应:', response)
      ElMessage.error(response?.message || '上传失败')
    }
  }

  // 大纲文件上传失败
  // 参数格式兼容：直接调用 (error) 或事件传递 ({ error, file })
  const handleOutlineUploadError = (data) => {
    uploading_outline.value = false
    outline_upload_progress.value = 0
    
    // 解析参数格式
    let error
    if (data && data.error) {
      error = data.error
    } else {
      error = data
    }
    
    console.error('[Upload] 大纲上传错误:', error)
    ElMessage.error('大纲文件上传失败：' + (error?.message || '未知错误'))
  }

  // 删除已上传的大纲文件
  const removeOutlineFile = () => {
    form.value.custom_outline = ''
    form.value.custom_outline_name = ''
    outline_upload_progress.value = 0
  }

  // ==================== 应用文参考文档上传 ====================

  // 上传前验证（参考文档 - 支持更多格式）
  const beforeReferenceDocUpload = (file) => {
    const allowedExtensions = ['.txt', '.md', '.doc', '.docx', '.pdf', '.xlsx']
    const fileExtension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
    
    if (!allowedExtensions.includes(fileExtension)) {
      ElMessage.error('只支持上传 .txt, .md, .doc, .docx, .pdf, .xlsx 格式的文件！')
      return false
    }
    if (file.size / 1024 / 1024 > 100) {
      ElMessage.error('文件大小不能超过100MB！')
      return false
    }
    uploading_reference_doc.value = true
    reference_doc_upload_progress.value = 0
    return true
  }

  // 参考文档上传进度
  const handleReferenceDocProgress = (event) => {
    reference_doc_upload_progress.value = Math.round(event.percent)
  }

  // 参考文档上传成功
  const handleReferenceDocUploadSuccess = (data, fileOrUndefined) => {
    uploading_reference_doc.value = false
    reference_doc_upload_progress.value = 100
    
    let response, file
    if (data && data.response && data.file) {
      response = data.response
      file = data.file
    } else {
      response = data
      file = fileOrUndefined
    }
    
    console.log('[Upload] 参考文档上传响应:', JSON.stringify(response, null, 2))
    
    if ((response.code === 0 || response.code === 200) && response.data?.url) {
      form.value.reference_document = response.data.url
      form.value.reference_document_name = file?.name || '已上传文件'
      ElMessage.success('参考文档上传成功')
    } else {
      console.error('[Upload] 参考文档上传失败，响应:', response)
      ElMessage.error(response?.message || '上传失败')
    }
  }

  // 参考文档上传失败
  const handleReferenceDocUploadError = (data) => {
    uploading_reference_doc.value = false
    reference_doc_upload_progress.value = 0
    
    let error
    if (data && data.error) {
      error = data.error
    } else {
      error = data
    }
    
    console.error('[Upload] 参考文档上传错误:', error)
    ElMessage.error('参考文档上传失败：' + (error?.message || '未知错误'))
  }

  // 删除已上传的参考文档
  const removeReferenceDocFile = () => {
    form.value.reference_document = ''
    form.value.reference_document_name = ''
    reference_doc_upload_progress.value = 0
  }

  // 参考资料上传前处理
  const beforeReferenceMaterialsUpload = (file) => {
    const allowedTypes = ['text/plain', 'text/markdown', 'application/pdf', 
      'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document']
    const allowedExtensions = ['.txt', '.md', '.doc', '.docx', '.pdf']
    const fileExtension = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
    
    if (!allowedTypes.includes(file.type) && !allowedExtensions.includes(fileExtension)) {
      ElMessage.error('只支持 .txt, .md, .doc, .docx, .pdf 格式的文件')
      return false
    }
    
    uploading_reference_materials.value = true
    reference_materials_upload_progress.value = 0
    
    // 模拟上传进度
    const progressInterval = setInterval(() => {
      if (reference_materials_upload_progress.value < 90) {
        reference_materials_upload_progress.value += 10
      }
    }, 200)
    
    file.progressInterval = progressInterval
    return true
  }

  // 参考资料上传成功
  // 参数格式兼容：直接调用 (response, file) 或事件传递 ({ response, file })
  const handleReferenceMaterialsUploadSuccess = (data, fileOrUndefined) => {
    uploading_reference_materials.value = false
    reference_materials_upload_progress.value = 100

    // 解析参数格式
    let response, file
    if (data && data.response && data.file) {
      response = data.response
      file = data.file
    } else {
      response = data
      file = fileOrUndefined
    }
  
    if (file?.raw?.progressInterval) {
      clearInterval(file.raw.progressInterval)
    }
  
    console.log('[Upload] 参考资料上传响应:', response)
    if ((response.code === 0 || response.code === 200) && response.data?.url) {
      form.value.reference_materials = response.data.url
      form.value.reference_materials_name = file?.name || '已上传文件'
      ElMessage.success('参考资料上传成功')
    } else {
      console.error('[Upload] 参考资料上传失败，响应:', response)
      ElMessage.error(response?.message || '上传失败')
    }
  }
  
  // 参考资料上传失败
  // 参数格式兼容：直接调用 (error, file) 或事件传递 ({ error, file })
  const handleReferenceMaterialsUploadError = (data, fileOrUndefined) => {
    uploading_reference_materials.value = false
    reference_materials_upload_progress.value = 0

    // 解析参数格式
    let error, file
    if (data && data.error && data.file) {
      error = data.error
      file = data.file
    } else {
      error = data
      file = fileOrUndefined
    }
  
    if (file?.raw?.progressInterval) {
      clearInterval(file.raw.progressInterval)
    }
  
    console.error('[Upload] 参考资料上传错误:', error)
    ElMessage.error('参考资料上传失败：' + (error?.message || '未知错误'))
  }

  // 删除已上传的参考资料
  const removeReferenceMaterialsFile = () => {
    form.value.reference_materials = ''
    form.value.reference_materials_name = ''
    reference_materials_upload_progress.value = 0
  }

  // 图片上传成功
  // 参数格式兼容：直接调用 (response, file) 或事件传递 ({ response, file })
  const handleUploadSuccess = (data, fileOrUndefined) => {
    // 解析参数格式
    let response
    if (data && data.response && data.file) {
      response = data.response
    } else {
      response = data
    }
    
    console.log('[Upload] 图片上传响应:', response)
    if ((response.code === 0 || response.code === 200) && response.data?.url) {
      form.value.images.push(response.data.url)
      ElMessage.success('图片上传成功')
    } else {
      console.error('[Upload] 图片上传失败，响应:', response)
      ElMessage.error(response?.message || '上传失败')
    }
  }

  // 图片上传失败
  // 参数格式兼容：直接调用 (error) 或事件传递 ({ error, file })
  const handleUploadError = (data) => {
    // 解析参数格式
    let error
    if (data && data.error) {
      error = data.error
    } else {
      error = data
    }
    
    console.error('[Upload] 图片上传错误:', error)
    ElMessage.error('图片上传失败：' + (error?.message || '未知错误'))
  }

  // 解析URL输入
  const parseImageUrls = () => {
    if (imageUrlInput.value.trim()) {
      const urls = imageUrlInput.value.split(',').map(url => url.trim()).filter(url => url)
      urls.forEach(url => {
        if (!form.value.images.includes(url)) {
          form.value.images.push(url)
        }
      })
    }
  }

  // 短视频模式切换处理
  const handleVideoModeChange = (mode) => {
    if (mode === 'real') {
      form.value.generate_ai_prompt = false
      form.value.generate_storyboard_images = false
      form.value.ai_platforms = []
    } else {
      form.value.generate_storyboard_images = true
    }
  }

  // 剧集类型变化处理（旧剧本大纲）
  const handleSeriesTypeChange = (value) => {
    if (value && SERIES_DURATION_CONFIG[value]) {
      const config = SERIES_DURATION_CONFIG[value]
      form.value.episode_duration_range = [config.defaultMin, config.defaultMax]
      if (value === '短剧' || value === '竖屏剧') {
        form.value.format_standard = '短剧格式'
      } else if (value === '网络剧' || value === '网络电影') {
        form.value.format_standard = '网络平台格式'
      } else {
        form.value.format_standard = '标准格式'
      }
    }
  }

  // 电影类型变化处理（电影大纲）
  const handleMovieTypeChange = (value) => {
    if (value && MOVIE_DURATION_CONFIG[value]) {
      const config = MOVIE_DURATION_CONFIG[value]
      form.value.duration_range = [config.defaultMin, config.defaultMax]
      if (value === '纪录片') {
        form.value.format_standard = '纪录片格式'
      } else if (value === '网络电影' || value === '微电影') {
        form.value.format_standard = '网络平台格式'
      } else {
        form.value.format_standard = '标准格式'
      }
    }
  }

  // 剧集类型变化处理（剧集大纲）
  const handleSeriesOutlineTypeChange = (value) => {
    if (value && SERIES_EPISODE_DURATION_CONFIG[value]) {
      const config = SERIES_EPISODE_DURATION_CONFIG[value]
      form.value.episode_duration_range = [config.defaultMin, config.defaultMax]
      if (value === '短剧' || value === '竖屏剧' || value === '微短剧') {
        form.value.format_standard = '短剧格式'
      } else if (value === '网络剧') {
        form.value.format_standard = '网络平台格式'
      } else {
        form.value.format_standard = '标准格式'
      }
    }
  }

  // 提示词优化处理
  const handleOptimizePrompt = async (targetField = 'description') => {
    let textToOptimize = ''
    if (targetField === 'description') {
      textToOptimize = form.value.description
    } else if (targetField === 'core_message') {
      textToOptimize = form.value.core_message
    } else if (targetField === 'ip_description') {
      textToOptimize = form.value.ip_description
    }
    
    if (!textToOptimize || textToOptimize.length < 5) {
      ElMessage.warning('请至少输入5个字符后再优化')
      return
    }
    
    optimizing.value = true
    optimizeTarget.value = targetField
    
    try {
      const moduleMap = {
        'short-video': 'short_video',
        'movie-outline': 'movie_outline',
        'series-outline': 'series_outline',
        'novel': 'novel',
        'print-ad': 'print_ad',
        'tvc': 'tvc',
        'original-ip': 'original_ip',
        'practical-writing': 'practical_writing'
      }
      const module = moduleMap[type.value] || type.value
      
      const res = await generateApi.optimize({
        module: module,
        original_text: textToOptimize
      })
      
      if (res.success && res.data) {
        if (targetField === 'description') {
          form.value.description = res.data.optimized_text
        } else if (targetField === 'core_message') {
          form.value.core_message = res.data.optimized_text
        } else if (targetField === 'ip_description') {
          form.value.ip_description = res.data.optimized_text
        }
        
        ElMessage.success(`优化完成！原文 ${res.data.original_length} 字 → 优化后 ${res.data.optimized_length} 字`)
      }
    } catch (error) {
      console.error('优化失败:', error)
      ElMessage.error(error.response?.data?.detail || '优化失败，请稍后重试')
    } finally {
      optimizing.value = false
      optimizeTarget.value = ''
    }
  }

  // 保存表单数据到 localStorage
  // 记录最近一次有效的模块类型：路由离开后 type.value 会变为 undefined，
  // 若直接拼接会写入错误的存储键 generate_form_undefined 导致数据丢失
  let lastValidModuleType = type.value

  const resolveStorageModuleType = () => {
    if (type.value) {
      lastValidModuleType = type.value
    }
    return type.value || lastValidModuleType
  }

  const saveFormData = () => {
    const moduleType = resolveStorageModuleType()
    if (!moduleType) return
    const dataToSave = {
      form: form.value,
      timestamp: Date.now()
    }
    localStorage.setItem(`generate_form_${moduleType}`, JSON.stringify(dataToSave))
  }

  // 从 localStorage 恢复表单数据
  const restoreFormData = () => {
    if (!type.value) return
    const saved = localStorage.getItem(`generate_form_${type.value}`)
    if (saved) {
      try {
        const { form: savedForm, timestamp } = JSON.parse(saved)
        if (Date.now() - timestamp < 24 * 60 * 60 * 1000) {
          form.value = { ...form.value, ...savedForm }
          if (typeof form.value.genre === 'string') {
            form.value.genre = form.value.genre ? form.value.genre.split('、') : []
          }
        } else {
          localStorage.removeItem(`generate_form_${type.value}`)
        }
      } catch (e) {
        console.error('恢复表单数据失败:', e)
      }
    }
  }

  // 监听表单变化自动保存（唯一监听器：停止输入 400ms 后最多写入一次）
  const debouncedSaveFormData = debounce(saveFormData, 400)
  const stopAutoSave = watch(form, debouncedSaveFormData, { deep: true })

  // 模块类型切换时（组件复用不卸载）：先用旧类型键落盘当前表单，
  // 再由页面层的 restoreFormData 加载新模块数据，避免切换前未满 400ms 的输入丢失
  watch(type, (newType, oldType) => {
    if (!oldType || newType === oldType) return
    debouncedSaveFormData.cancel()
    localStorage.setItem(`generate_form_${oldType}`, JSON.stringify({
      form: form.value,
      timestamp: Date.now()
    }))
    lastValidModuleType = newType || oldType
  })

  // 离开页面前将最终表单状态直接落盘。
  // 注意：不能仅依赖 flush()——Vue 的 pre-flush watcher 在“输入后立即路由跳转”场景下
  // 会因组件先卸载而被调度器丢弃，此时防抖器内没有待处理调用，最后一批输入会丢失。
  // 因此卸载时取消待处理定时器并无条件保存当前 form 状态，确保数据完整。
  onBeforeUnmount(() => {
    debouncedSaveFormData.cancel()
    saveFormData()
    stopAutoSave()
  })

  // 重置表单
  const resetForm = () => {
    formRef.value.resetFields()
    form.value.style_types = []
    form.value.style_types_level1 = []
    form.value.video_mode = 'virtual'
    form.value.generate_ai_prompt = false
    form.value.generate_storyboard_images = true
    form.value.ai_platforms = []
    form.value.series_type = ''
    form.value.reference_works = ''
  }

  // 导出配置相关
  const importInputRef = ref(null)

  const formatConfigTimestamp = (date) => {
    return date.toISOString().replace(/[-:T]/g, '').slice(0, 15)
  }

  const exportConfig = () => {
    const config = {
      version: '1.0',
      module_type: type.value,
      created_at: new Date().toISOString(),
      form_data: { ...form.value }
    }
    
    const blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${type.value}_config_${formatConfigTimestamp(new Date())}.json`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success('配置已导出')
  }

  const triggerImport = () => {
    importInputRef.value?.click()
  }

  const importConfig = async (event) => {
    const file = event.target.files[0]
    if (!file) return
    
    try {
      const text = await file.text()
      const config = JSON.parse(text)
      
      if (!config.version || !config.module_type || !config.form_data) {
        throw new Error('无效的配置文件格式')
      }
      
      if (config.module_type !== type.value) {
        ElMessage.warning(`配置文件类型不匹配：${config.module_type}，当前模块：${type.value}`)
        return
      }
      
      Object.keys(config.form_data).forEach(key => {
        if (key in form.value) {
          form.value[key] = config.form_data[key]
        }
      })
      
      ElMessage.success('配置已导入')
    } catch (error) {
      ElMessage.error('导入失败：' + error.message)
    } finally {
      event.target.value = ''
    }
  }

  return {
    // 表单相关
    formRef,
    form,
    rules,
    
    // 上传相关
    imageFileList,
    imageUrlInput,
    uploadUrl,
    uploadHeaders,
    uploading_outline,
    outline_upload_progress,
    uploading_reference_materials,
    reference_materials_upload_progress,
    
    // 应用文参考文档上传
    uploading_reference_doc,
    reference_doc_upload_progress,
    
    // 优化相关
    optimizing,
    optimizeTarget,
    
    // 计算属性
    useTwoStageMode,
    combinedStyleTypes,
    seriesDurationHint,
    movieDurationHint,
    seriesEpisodeDurationHint,
    
    // 方法
    beforeUpload,
    beforeOutlineUpload,
    handleOutlineProgress,
    handleOutlineUploadSuccess,
    handleOutlineUploadError,
    removeOutlineFile,
    beforeReferenceMaterialsUpload,
    handleReferenceMaterialsUploadSuccess,
    handleReferenceMaterialsUploadError,
    removeReferenceMaterialsFile,
    handleUploadSuccess,
    handleUploadError,
    parseImageUrls,
    
    // 应用文参考文档上传方法
    beforeReferenceDocUpload,
    handleReferenceDocProgress,
    handleReferenceDocUploadSuccess,
    handleReferenceDocUploadError,
    removeReferenceDocFile,
    
    handleVideoModeChange,
    handleSeriesTypeChange,
    handleMovieTypeChange,
    handleSeriesOutlineTypeChange,
    handleOptimizePrompt,
    saveFormData,
    restoreFormData,
    resetForm,
    
    // 导入导出
    importInputRef,
    exportConfig,
    triggerImport,
    importConfig
  }
}
