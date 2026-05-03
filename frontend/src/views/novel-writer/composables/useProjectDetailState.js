/**
 * useProjectDetailState - 核心状态管理与共享数据
 * �?ProjectDetail.vue 中提取，集中管理所有共享响应式状�?
 */
import { ref, computed, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import DOMPurify from 'dompurify'
import { marked } from 'marked'
import { novelWriterApi } from '@/api/novel-writer'
import { useTaskStore } from '@/stores/task'
import { useKnowledgeBase } from './useKnowledgeBase'
import { useProjectLoader } from './useProjectLoader'
import { useTaskMonitoring } from './useTaskMonitoring'
import {
  Document, Reading, Cpu, DataAnalysis, ChatDotRound,
  Edit, Folder, List, Loading, Finished,
  CircleCheck, CircleClose, Warning
} from '@element-plus/icons-vue'

export function useProjectDetailState(refreshCallbacks = {}) {
  const route = useRoute()
  const router = useRouter()
  const taskStore = useTaskStore()

  const projectId = computed(() => parseInt(route.params.id))

  // ==================== 提取到 composables ====================
  const {
    loading, project, chapters, selectedChapter, chapterContent,
    contentTypeLabel, contentTypeTagType,
    loadProject, loadChapters, loadProjectData,
    selectChapter, clearSelectedChapter,
    loadChapterContent, saveChapterContent, deleteChapter
  } = useProjectLoader()

  const {
    sseConnection, sseReconnectTimer, taskPollingTimer,
    startSSEConnection, stopSSEConnection,
    startTaskPolling, stopTaskPolling,
    refreshListByTaskType, startTaskMonitoring, stopTaskMonitoring
  } = useTaskMonitoring(projectId, refreshCallbacks)

  // ==================== 以下为保留逻辑 ====================

  const TASK_POLLING_INTERVAL = 2000
  const SSE_RECONNECT_DELAY = 3000

  function showOutlineUpload() {
    // 滚动到上传区域
  }

  // ==================== 生成状�?====================
  const generating = ref(false)
  const generatingChapter = ref(false)
  const generatingDirectory = ref(false)
  const regeneratingNames = ref(false)
  const manualUnitCount = ref(10)

  // ==================== 单元概述上传状�?====================
  const showUnitSummariesUploadDialog = ref(false)
  const unitSummariesUploadMode = ref('file')
  const unitSummariesInput = ref('')
  const globalOutlineInput = ref('')
  const uploadingUnitSummaries = ref(false)

  // ==================== AbortController ====================
  const abortController = ref(null)


  // ==================== 分集大纲状�?====================
  const episodeOutlines = ref([])
  const generatingEpisodeOutlines = ref(false)
  const generatingSingleEpisode = ref(null)
  const selectedEpisode = ref(null)

  // ==================== 批量正文生成状�?====================
  const generatingAllContent = ref(false)
  const batchContentType = ref(null)
  const batchProgress = ref({ completed: 0, total: 0, current: null })

  // ==================== 指定数量生成对话�?====================
  const showBatchCountDialog = ref(false)
  const batchCountLoading = ref(false)
  const batchCountConfig = ref({
    startUnit: 1,
    count: 5,
    maxUnit: 100,
    unitLabel: '�?,
    type: 'outline',
    contentType: 'chapter'
  })

  // ==================== 分集大纲详情弹窗 ====================
  const outlineDetailVisible = ref(false)
  const currentOutlineDetail = ref({
    episode_number: 0,
    episode_title: '',
    raw_content: ''
  })
  const outlineEditMode = ref(false)
  const outlineEditContent = ref('')
  const outlineEditTitle = ref('')
  const savingOutlineEdit = ref(false)
  const editingEpisodeTitle = ref(null)
  const editEpisodeTitleValue = ref('')

  // ==================== 章节标题编辑 ====================
  const editingChapter = ref(null)
  const editTitleValue = ref('')

  // ==================== 章节大纲状态（小说�?====================
  const chapterOutlines = ref([])
  const generatingChapterOutlines = ref(false)
  const generatingSingleChapterOutline = ref(null)

  // ==================== 章节大纲详情弹窗 ====================
  const chapterOutlineDetailVisible = ref(false)
  const currentChapterOutlineDetail = ref({
    chapter_number: 0,
    chapter_title: '',
    raw_content: '',
    revision_info: null,
    original_content: null
  })
  const chapterOutlineRevisionCompareVisible = ref(false)
  const chapterOutlineOriginalContent = ref('')
  const chapterOutlineRevisedContent = ref('')
  const chapterOutlineRevisionInfo = ref(null)
  const chapterOutlineRevisionViewMode = ref('diff')

  const chapterOutlineEditMode = ref(false)
  const chapterOutlineEditContent = ref('')
  const chapterOutlineEditTitle = ref('')
  const savingChapterOutlineEdit = ref(false)
  const editingChapterOutlineTitle = ref(null)
  const editChapterOutlineTitleValue = ref('')

  // ==================== 场景大纲状态（电影剧本�?====================
  const sceneOutlines = ref([])
  const generatingSceneOutlines = ref(false)
  const generatingSingleSceneOutline = ref(null)

  // ==================== 场景大纲详情弹窗 ====================
  const sceneOutlineDetailVisible = ref(false)
  const currentSceneOutlineDetail = ref({
    scene_number: 0,
    scene_title: '',
    raw_content: ''
  })
  const sceneOutlineEditMode = ref(false)
  const sceneOutlineEditContent = ref('')
  const sceneOutlineEditTitle = ref('')
  const savingSceneOutlineEdit = ref(false)
  const editingSceneOutlineTitle = ref(null)
  const editSceneOutlineTitleValue = ref('')

  // ==================== 用户干预对话�?====================
  const interventionDialogVisible = ref(false)
  const interventionData = ref({
    unit_number: 0,
    content_type: 'novel',
    inferred_summary: '',
    reference_info: null,
    message: ''
  })
  const interventionLoading = ref(false)
  const interventionUserChoice = ref('')
  const interventionUserGuidance = ref('')

  const interventionOptions = [
    { value: 'accept', label: '接受推断结果', desc: '使用系统推断的概要继续生�?, icon: 'CircleCheck' },
    { value: 'provide', label: '提供概要内容', desc: '自行输入章节概要', icon: 'Edit' },
    { value: 'reference', label: '参考相邻章�?, desc: '使用前后章节信息重新生成', icon: 'Reading' },
    { value: 'skip', label: '跳过此章�?, desc: '暂时跳过，稍后处�?, icon: 'VideoPause' }
  ]

  // ==================== 对话框状�?====================
  const settingsVisible = ref(false)
  const exportVisible = ref(false)
  const savingSettings = ref(false)
  const exporting = ref(false)

  // ==================== 知识库状�?====================
  const {
    kbStatus,
    loadingKbStatus,
    buildingKb,
    resettingKbStatus,
    loadKnowledgeBaseStatus,
    refreshKnowledgeBaseStatus,
    handleBuildKnowledgeBase,
    handleDeleteKnowledgeBase,
    handleResetKbStatus
  } = useKnowledgeBase(projectId)

  const knowledgeGraphVisible = ref(false)

  // ==================== 修正对比状�?====================
  const revisionCompareVisible = ref(false)
  const originalDraftContent = ref('')
  const revisedContent = ref('')
  const chapterRevisionInfo = ref(null)
  const revisionViewMode = ref('diff')

  // ==================== 合规审核状�?====================
  const complianceDetailVisible = ref(false)
  const complianceDetailData = ref(null)

  const chapterComplianceMarking = computed(() => {
    return selectedChapter.value?.chapter_metadata?.compliance_marking || null
  })

  // ==================== 问题类型映射 ====================
  const ISSUE_TYPE_LABELS = {
    'sensitive_word': '敏感�?,
    'sensitive_location': '敏感地名',
    'sensitive_person': '名人姓名',
    'sensitive_event': '历史事件'
  }

  function getIssueTypeLabel(type) {
    return ISSUE_TYPE_LABELS[type] || type
  }

  function showComplianceDetail(chapter) {
    if (chapter?.chapter_metadata?.compliance_marking) {
      complianceDetailData.value = chapter.chapter_metadata.compliance_marking
      complianceDetailVisible.value = true
    }
  }

  // ==================== 修正字数变化 ====================
  const revisionWordChange = computed(() => {
    const originalLen = chapterRevisionInfo.value?.original_length || originalDraftContent.value?.length || 0
    const revisedLen = chapterRevisionInfo.value?.revised_length || revisedContent.value?.length || 0
    return revisedLen - originalLen
  })

  const revisionDiffHtml = computed(() => {
    if (!originalDraftContent.value || !revisedContent.value) return ''
    return computeDiffHtml(originalDraftContent.value, revisedContent.value)
  })

  // ==================== 章节大纲修正计算属�?====================
  const chapterOutlineRevisionWordChange = computed(() => {
    const originalLen = chapterOutlineRevisionInfo.value?.original_length || chapterOutlineOriginalContent.value?.length || 0
    const revisedLen = chapterOutlineRevisionInfo.value?.revised_length || chapterOutlineRevisedContent.value?.length || 0
    return revisedLen - originalLen
  })

  const chapterOutlineRevisionDiffHtml = computed(() => {
    if (!chapterOutlineOriginalContent.value || !chapterOutlineRevisedContent.value) return ''
    return computeDiffHtml(chapterOutlineOriginalContent.value, chapterOutlineRevisedContent.value)
  })

  // ==================== 默认配置 ====================
  const DEFAULT_NOVEL_CONFIG = {
    target_platform: '',
    words_per_chapter: 3000,
    narrative_perspective: '第三人称',
    tone: '正剧',
    temperature: 0.8
  }

  const DEFAULT_SERIES_SCRIPT_CONFIG = {
    series_type: '电视�?,
    episode_count: null,
    episode_duration_range: [30, 45],
    format_standard: '标准格式',
    dialogue_narration_ratio: '均衡',
    target_broadcast: ''
  }

  const DEFAULT_MOVIE_SCRIPT_CONFIG = {
    movie_type: '院线电影',
    total_duration: 90,
    format_standard: '标准格式',
    dialogue_narration_ratio: '均衡',
    target_platform: ''
  }

  // ==================== 表单 ====================
  const settingsForm = ref({
    title: '',
    genre: '',
    novel_config: { ...DEFAULT_NOVEL_CONFIG },
    series_script_config: { ...DEFAULT_SERIES_SCRIPT_CONFIG },
    movie_script_config: { ...DEFAULT_MOVIE_SCRIPT_CONFIG },
    kb_vertical_enabled: false,
    kb_user_specific_enabled: false,
    kb_manual_enabled: false,
    graphrag_enabled: true,
    compliance_enabled: true,
    compliance_level: 'normal',
    compliance_platform: ''
  })

  const exportForm = ref({
    format: 'txt',
    include_metadata: false,
    chapter_range: ''
  })

  // ==================== 计算属�?====================
  const canGenerate = computed(() => {
    return project.value?.outline_content && project.value?.total_chapters > 0
  })

  const totalWords = computed(() => {
    return chapters.value.reduce((sum, c) => sum + (c.word_count || 0), 0)
  })

  const totalEpisodeCount = computed(() => {
    return project.value?.series_script_config?.episode_count || project.value?.script_config?.episode_count || 0
  })

  const generatedEpisodeCount = computed(() => {
    return episodeOutlines.value.filter(e => e.has_detailed).length
  })

  const renderedOutlineContent = computed(() => {
    if (!currentOutlineDetail.value.raw_content) return ''
    return DOMPurify.sanitize(marked(currentOutlineDetail.value.raw_content))
  })

  const totalChapterOutlineCount = computed(() => {
    return project.value?.total_chapters || 0
  })

  const generatedChapterOutlineCount = computed(() => {
    return chapterOutlines.value.filter(c => c.has_detailed).length
  })

  const renderedChapterOutlineContent = computed(() => {
    if (!currentChapterOutlineDetail.value.raw_content) return ''
    return DOMPurify.sanitize(marked(currentChapterOutlineDetail.value.raw_content))
  })

  const totalSceneOutlineCount = computed(() => {
    return project.value?.total_chapters || 0
  })

  const generatedSceneOutlineCount = computed(() => {
    return sceneOutlines.value.filter(s => s.has_detailed).length
  })

  const generatedEpisodeContentCount = computed(() => {
    return episodeOutlines.value.filter(e => e.content_status === 'generated').length
  })

  const generatedChapterContentCount = computed(() => {
    return chapterOutlines.value.filter(c => c.content_status === 'generated').length
  })

  const generatedSceneContentCount = computed(() => {
    return sceneOutlines.value.filter(s => s.content_status === 'generated').length
  })

  const renderedSceneOutlineContent = computed(() => {
    if (!currentSceneOutlineDetail.value.raw_content) return ''
    return DOMPurify.sanitize(marked(currentSceneOutlineDetail.value.raw_content))
  })

  const unitLabel = computed(() => {
    const contentType = project.value?.content_type
    if (contentType === 'novel') return '�?
    if (contentType === 'series_script') return '�?
    if (contentType === 'movie_script') return '�?
    if (project.value?.project_type === 'script') return '�?
    return '�?
  })

  // ==================== 内容类型标签辅助 ====================
  function getTypeLabel(contentType) {
    return CONTENT_TYPE_LABELS[contentType] || '小说'
  }

  function getTypeTagType(contentType) {
    return CONTENT_TYPE_TAG_TYPES[contentType] || 'info'
  }

  // ==================== 显示修正对比对话�?====================
  function showRevisionCompareDialog() {
    revisionCompareVisible.value = true
  }

  // ==================== Diff 算法 ====================
  function computeDiffHtml(oldText, newText) {
    if (!oldText && !newText) return ''
    if (!oldText) return `<div class="diff-paragraph added">${escapeHtml(newText)}</div>`
    if (!newText) return `<div class="diff-paragraph removed">${escapeHtml(oldText)}</div>`
    
    const oldParagraphs = oldText.split(/\n+/).filter(p => p.trim())
    const newParagraphs = newText.split(/\n+/).filter(p => p.trim())
    
    if (oldParagraphs.length <= 100 && newParagraphs.length <= 100) {
      return computeDiffWithLCS(oldParagraphs, newParagraphs)
    } else {
      return computeDiffSimple(oldParagraphs, newParagraphs)
    }
  }

  function computeDiffWithLCS(oldParagraphs, newParagraphs) {
    const lcs = findLCS(oldParagraphs, newParagraphs)
    let html = ''
    let oldIdx = 0, newIdx = 0, lcsIdx = 0
    
    while (oldIdx < oldParagraphs.length || newIdx < newParagraphs.length) {
      if (lcsIdx < lcs.length && oldIdx < oldParagraphs.length && 
          oldParagraphs[oldIdx] === lcs[lcsIdx] && 
          newIdx < newParagraphs.length && newParagraphs[newIdx] === lcs[lcsIdx]) {
        html += `<div class="diff-paragraph unchanged">${escapeHtml(oldParagraphs[oldIdx])}</div>`
        oldIdx++
        newIdx++
        lcsIdx++
      } else if (newIdx < newParagraphs.length &&
                 (lcsIdx >= lcs.length || newParagraphs[newIdx] !== lcs[lcsIdx])) {
        if (oldIdx < oldParagraphs.length &&
            (lcsIdx >= lcs.length || oldParagraphs[oldIdx] !== lcs[lcsIdx])) {
          html += `<div class="diff-paragraph removed">${escapeHtml(oldParagraphs[oldIdx])}</div>`
          html += `<div class="diff-paragraph added">${escapeHtml(newParagraphs[newIdx])}</div>`
          oldIdx++
          newIdx++
        } else {
          html += `<div class="diff-paragraph added">${escapeHtml(newParagraphs[newIdx])}</div>`
          newIdx++
        }
      } else if (oldIdx < oldParagraphs.length &&
                 (lcsIdx >= lcs.length || oldParagraphs[oldIdx] !== lcs[lcsIdx])) {
        html += `<div class="diff-paragraph removed">${escapeHtml(oldParagraphs[oldIdx])}</div>`
        oldIdx++
      }
    }
    return html
  }

  function computeDiffSimple(oldParagraphs, newParagraphs) {
    const newSet = new Set(newParagraphs)
    const oldSet = new Set(oldParagraphs)
    let html = ''
    
    for (const para of oldParagraphs) {
      if (newSet.has(para)) {
        html += `<div class="diff-paragraph unchanged">${escapeHtml(para)}</div>`
      } else {
        html += `<div class="diff-paragraph removed">${escapeHtml(para)}</div>`
      }
    }
    
    for (const para of newParagraphs) {
      if (!oldSet.has(para)) {
        html += `<div class="diff-paragraph added">${escapeHtml(para)}</div>`
      }
    }
    
    return html
  }

  function findLCS(arr1, arr2) {
    const m = arr1.length, n = arr2.length
    const dp = Array(m + 1).fill(null).map(() => Array(n + 1).fill(0))
    
    for (let i = 1; i <= m; i++) {
      for (let j = 1; j <= n; j++) {
        if (arr1[i - 1] === arr2[j - 1]) {
          dp[i][j] = dp[i - 1][j - 1] + 1
        } else {
          dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1])
        }
      }
    }
    
    const lcs = []
    let i = m, j = n
    while (i > 0 && j > 0) {
      if (arr1[i - 1] === arr2[j - 1]) {
        lcs.unshift(arr1[i - 1])
        i--
        j--
      } else if (dp[i - 1][j] > dp[i][j - 1]) {
        i--
      } else {
        j--
      }
    }
    return lcs
  }

  function escapeHtml(text) {
    if (!text) return ''
    return text
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;')
      .replace(/ /g, '&nbsp;')
  }

  // ==================== 核心加载方法 ====================
  async function loadProject() {
    loading.value = true
    try {
      const res = await novelWriterApi.getProject(projectId.value)
      if (res.success) {
        project.value = res.data
        const kbConfig = res.data.knowledge_base_config || {}
        const complianceConfig = res.data.compliance_config || {}
        
        manualUnitCount.value = res.data.total_chapters || 10
        
        settingsForm.value = {
          title: res.data.title,
          genre: res.data.genre || '',
          novel_config: res.data.novel_config || { ...DEFAULT_NOVEL_CONFIG },
          series_script_config: res.data.series_script_config || { ...DEFAULT_SERIES_SCRIPT_CONFIG },
          movie_script_config: res.data.movie_script_config || { ...DEFAULT_MOVIE_SCRIPT_CONFIG },
          kb_vertical_enabled: kbConfig.kb_vertical_enabled || false,
          kb_user_specific_enabled: kbConfig.kb_user_specific_enabled || false,
          kb_manual_enabled: kbConfig.kb_manual_enabled || false,
          graphrag_enabled: kbConfig.graphrag_enabled !== false,
          compliance_enabled: complianceConfig.enabled !== false,
          compliance_level: complianceConfig.level || 'normal',
          compliance_platform: complianceConfig.platform || ''
        }
      }
    } catch (error) {
      ElMessage.error('加载项目失败')
      router.back()
    } finally {
      loading.value = false
    }
  }

  async function loadChapters() {
    try {
      const res = await novelWriterApi.getChapters(projectId.value)
      if (res.success) {
        chapters.value = res.data.chapters
      }
    } catch (error) {
      console.error('加载章节列表失败', error)
    }
  }

  async function selectChapter(chapter) {
    selectedChapter.value = chapter
    chapterContent.value = ''
    chapterRevisionInfo.value = null

    if (chapter.status === 'completed') {
      try {
        const res = await novelWriterApi.getChapter(projectId.value, chapter.chapter_number)
        if (res.success) {
          chapterContent.value = res.data.final_content || ''
          if (res.data.chapter_metadata?.revision_info) {
            chapterRevisionInfo.value = res.data.chapter_metadata.revision_info
            originalDraftContent.value = res.data.draft_content || ''
            revisedContent.value = res.data.final_content || ''
          }
        }
      } catch (error) {
        console.error('加载章节内容失败', error)
      }
    }
  }

  // ==================== 大纲上传 ====================
  async function handleOutlineUpload(options) {
    const file = options.file
    const formData = new FormData()
    formData.append('file', file)

    try {
      ElMessage.info('正在上传大纲...')
      const res = await novelWriterApi.uploadOutline(projectId.value, formData)
      if (res.success) {
        const extractedUnits = res.data.extracted_chapters || 0
        
        if (extractedUnits > 0) {
          ElMessage.success(`大纲上传成功，识别到${extractedUnits}�?{unitLabel.value}`)
          manualUnitCount.value = extractedUnits
        } else {
          ElMessage.warning('大纲上传成功，但未能自动识别，请手动设置数量')
        }
        
        loadProject()
        loadChapters()
      }
    } catch (error) {
      ElMessage.error('上传失败')
    }
  }

  // ==================== 单元概述上传 ====================
  async function handleUploadUnitSummariesContent(contentData) {
    // contentData = { format: 'json'|'markdown', parsedData: Object, rawContent: string }
    if (!contentData || !contentData.parsedData) {
      ElMessage.warning('请输入单元概述内�?)
      return
    }
    const unitSummaries = contentData.parsedData
    
    // 验证数据格式
    if (typeof unitSummaries !== 'object' || Array.isArray(unitSummaries)) {
      ElMessage.error('单元概述格式错误，应为对象格�?)
      return
    }

    uploadingUnitSummaries.value = true
    try {
      const data = { unit_summaries: unitSummaries }
      
      if (globalOutlineInput.value.trim()) {
        data.global_outline = globalOutlineInput.value.trim()
      }

      const res = await novelWriterApi.uploadUnitSummaries(projectId.value, data)
      if (res.success) {
        ElMessage.success(res.data.message || '单元概述上传成功')
        showUnitSummariesUploadDialog.value = false
        unitSummariesInput.value = ''
        globalOutlineInput.value = ''
        loadProject()
      }
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '上传失败')
    } finally {
      uploadingUnitSummaries.value = false
    }
  }

  async function handleUnitSummariesFileUpload(options) {
    const file = options.file
    const validExtensions = ['.txt', '.md', '.doc', '.docx']
    const fileExt = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
    
    if (!validExtensions.includes(fileExt)) {
      ElMessage.error(`不支持的文件格式: ${fileExt}，支�?.txt, .md, .doc, .docx`)
      return
    }

    uploadingUnitSummaries.value = true
    try {
      const formData = new FormData()
      formData.append('file', file)
      ElMessage.info('正在上传单元概述文件...')
      
      const res = await novelWriterApi.uploadUnitSummariesFile(projectId.value, formData)
      if (res.success) {
        ElMessage.success(res.data.message || '单元概述上传成功')
        showUnitSummariesUploadDialog.value = false
        loadProject()
      }
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '上传失败')
    } finally {
      uploadingUnitSummaries.value = false
    }
  }

  // ==================== 目录生成 ====================
  async function handleGenerateDirectory() {
    if (!manualUnitCount.value || manualUnitCount.value < 1) {
      ElMessage.warning('请设置有效的数量')
      return
    }

    try {
      if (chapters.value.length > 0) {
        await ElMessageBox.confirm(
          `当前已有 ${chapters.value.length} �?{unitLabel.value}，重新生成将会清空现有内容。确定要继续吗？`,
          '重新生成目录',
          { type: 'warning' }
        )
      }

      generatingDirectory.value = true
      const res = await novelWriterApi.generateDirectory(projectId.value, {
        total_chapters: manualUnitCount.value,
        generate_names: true
      })
      
      if (res.success) {
        if (res.data && res.data.chapters) {
          ElMessage.success(`已创�?{manualUnitCount.value}�?{unitLabel.value}，名称已生成`)
        } else {
          ElMessage.success(`已创�?{manualUnitCount.value}�?{unitLabel.value}`)
        }
        loadProject()
        loadChapters()
      }
    } catch (error) {
      if (error !== 'cancel') {
        ElMessage.error('生成目录失败')
      }
    } finally {
      generatingDirectory.value = false
    }
  }

  async function handleRegenerateNames() {
    try {
      regeneratingNames.value = true
      ElMessage.info('正在生成章节名称...')
      const res = await novelWriterApi.regenerateChapterNames(projectId.value)
      if (res.success) {
        ElMessage.success(`成功更新${res.data.updated_count}�?{unitLabel.value}名称`)
        loadChapters()
      }
    } catch (error) {
      ElMessage.error('生成名称失败')
    } finally {
      regeneratingNames.value = false
    }
  }

  async function handleRegenerateDirectory() {
    try {
      await ElMessageBox.confirm(
        `重新生成目录将清空现有的 ${chapters.value.length} �?{unitLabel.value}及其内容，此操作不可撤销。确定要继续吗？`,
        '重新生成目录',
        { type: 'warning' }
      )

      const episodeCount = totalEpisodeCount.value || project.value?.total_chapters || chapters.value.length
      
      generatingDirectory.value = true
      const res = await novelWriterApi.generateDirectory(projectId.value, {
        total_chapters: episodeCount,
        generate_names: true
      })
      
      if (res.success) {
        ElMessage.success('目录已重新生�?)
        loadProject()
        loadChapters()
        if (project.value?.content_type === 'series_script' || project.value?.project_type === 'script') {
          if (refreshCallbacks.loadEpisodeOutlines) await refreshCallbacks.loadEpisodeOutlines()
        }
      }
    } catch (error) {
      if (error !== 'cancel') {
        ElMessage.error('重新生成目录失败')
      }
    } finally {
      generatingDirectory.value = false
    }
  }

  // ==================== 章节标题编辑 ====================
  function cleanChapterTitle(title) {
    if (!title) return '未命�?
    let cleaned = title
    cleaned = cleaned.replace(/^第\d+[集章场]\s*/g, '')
    cleaned = cleaned.replace(/第None[集章场]\s*/g, '')
    cleaned = cleaned.replace(/第\d+[集章场]\s*第\d+[集章场]\s*/g, '')
    cleaned = cleaned.trim()
    return cleaned || '未命�?
  }

  function startEditTitle(chapter) {
    editingChapter.value = chapter.chapter_number
    editTitleValue.value = cleanChapterTitle(chapter.chapter_title)
    if (editTitleValue.value === '未命�?) {
      editTitleValue.value = ''
    }
  }

  let isSavingTitle = false

  function handleEnterSaveTitle(chapter) {
    if (isSavingTitle) return
    saveChapterTitle(chapter)
  }

  function handleBlurSaveTitle(chapter) {
    if (isSavingTitle) return
    saveChapterTitle(chapter)
  }

  async function saveChapterTitle(chapter) {
    if (isSavingTitle) return
    isSavingTitle = true
    
    try {
      const newTitle = editTitleValue.value.trim()
      if (!newTitle) {
        editingChapter.value = null
        return
      }

      const currentCleaned = cleanChapterTitle(chapter.chapter_title)
      if (newTitle === currentCleaned) {
        editingChapter.value = null
        return
      }

      await novelWriterApi.updateChapterTitle(projectId.value, chapter.chapter_number, newTitle)
      chapter.chapter_title = newTitle
      editingChapter.value = null
      ElMessage.success('标题已更�?)
    } catch (error) {
      ElMessage.error('更新失败')
    } finally {
      setTimeout(() => {
        isSavingTitle = false
      }, 100)
    }
  }

  function cancelEditTitle() {
    editingChapter.value = null
    editTitleValue.value = ''
  }

  // ==================== 整体生成 ====================
  async function startGenerate() {
    if (!canGenerate.value) return

    try {
      await ElMessageBox.confirm(
        '确定要开始生成所有章节吗？这可能需要较长时间�?,
        '确认生成',
        { type: 'info' }
      )

      generating.value = true
      ElMessage.info('开始生成，请耐心等待...')

      const res = await novelWriterApi.generateAll(projectId.value, {
        start_chapter: 1,
        stop_on_error: true
      })

      if (res.success) {
        ElMessage.success(`生成完成！成�?{res.data.completed_count}章，失败${res.data.failed_count}章`)
        loadProject()
        loadChapters()
      }
    } catch (error) {
      if (error !== 'cancel') {
        ElMessage.error('生成失败')
      }
    } finally {
      generating.value = false
    }
  }

  // ==================== 单章生成 ====================
  async function generateSingleChapter() {
    if (!selectedChapter.value) return

    generatingChapter.value = true
    try {
      const res = await novelWriterApi.generateChapter(
        projectId.value,
        selectedChapter.value.chapter_number
      )

      if (res.success) {
        ElMessage.success('章节生成成功')
        loadChapters()
        selectChapter({ ...selectedChapter.value, status: 'completed' })
        loadProject()
      } else {
        ElMessage.error(res.data?.error_message || '生成失败')
      }
    } catch (error) {
      ElMessage.error('生成失败')
    } finally {
      generatingChapter.value = false
    }
  }

  // ==================== 保存章节内容 ====================
  async function saveChapterContent() {
    if (!selectedChapter.value || !chapterContent.value) return

    try {
      await novelWriterApi.updateChapter(
        projectId.value,
        selectedChapter.value.chapter_number,
        { content: chapterContent.value }
      )
      ElMessage.success('已保�?)
    } catch (error) {
      ElMessage.error('保存失败')
    }
  }

  // ==================== 下载章节内容 ====================
  function handleDownloadChapter(format) {
    if (!chapterContent.value || !selectedChapter.value) {
      ElMessage.warning('暂无内容可下�?)
      return
    }
    
    const chapterNum = selectedChapter.value.chapter_number
    const chapterTitle = selectedChapter.value.chapter_title || `�?{chapterNum}${unitLabel.value}`
    const projectTitle = project.value?.title || '未命名项�?
    
    let content = chapterContent.value
    let fileName = ''
    let mimeType = ''
    
    if (format === 'md') {
      content = `# ${chapterTitle}\n\n> 来源�?{projectTitle}\n\n---\n\n${chapterContent.value}`
      fileName = `${projectTitle}_${chapterTitle}.md`
      mimeType = 'text/markdown;charset=utf-8'
    } else {
      content = `${chapterTitle}\n来源�?{projectTitle}\n${'='.repeat(40)}\n\n${chapterContent.value}`
      fileName = `${projectTitle}_${chapterTitle}.txt`
      mimeType = 'text/plain;charset=utf-8'
    }
    
    const blob = new Blob([content], { type: mimeType })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName
    a.click()
    URL.revokeObjectURL(url)
    
    ElMessage.success('下载成功')
  }

  // ==================== 设置 ====================
  function showSettingsDialog() {
    settingsVisible.value = true
  }

  async function saveSettings() {
    savingSettings.value = true
    try {
      const updateData = {
        title: settingsForm.value.title,
        genre: settingsForm.value.genre,
        knowledge_base_config: {
          kb_vertical_enabled: settingsForm.value.kb_vertical_enabled,
          kb_user_specific_enabled: settingsForm.value.kb_user_specific_enabled,
          kb_manual_enabled: settingsForm.value.kb_manual_enabled,
          graphrag_enabled: settingsForm.value.graphrag_enabled,
          kb_vertical_ids: [],
          kb_user_specific_ids: [],
          kb_manual_ids: []
        },
        compliance_config: {
          enabled: settingsForm.value.compliance_enabled,
          level: settingsForm.value.compliance_level,
          platform: settingsForm.value.compliance_platform
        }
      }
      
      const contentType = project.value?.content_type
      if (contentType === 'novel') {
        updateData.novel_config = settingsForm.value.novel_config
      } else if (contentType === 'series_script') {
        updateData.series_script_config = settingsForm.value.series_script_config
      } else if (contentType === 'movie_script') {
        updateData.movie_script_config = settingsForm.value.movie_script_config
      }
      
      await novelWriterApi.updateProject(projectId.value, updateData)
      ElMessage.success('设置已保�?)
      settingsVisible.value = false
      loadProject()
    } catch (error) {
      ElMessage.error('保存失败')
    } finally {
      savingSettings.value = false
    }
  }

  function showExportDialog() {
    exportVisible.value = true
  }

  async function handleExport() {
    exporting.value = true
    try {
      const res = await novelWriterApi.exportProject(projectId.value, exportForm.value)
      const url = window.URL.createObjectURL(new Blob([res]))
      const link = document.createElement('a')
      link.href = url
      link.setAttribute('download', `${project.value.title}.${exportForm.value.format}`)
      document.body.appendChild(link)
      link.click()
      link.remove()
      
      ElMessage.success('导出成功')
      exportVisible.value = false
    } catch (error) {
      ElMessage.error('导出失败')
    } finally {
      exporting.value = false
    }
  }

  async function handleDelete() {
    try {
      await ElMessageBox.confirm(
        '确定要删除此项目吗？删除后无法恢复�?,
        '确认删除',
        { type: 'warning' }
      )

      await novelWriterApi.deleteProject(projectId.value)
      ElMessage.success('项目已删�?)
      router.push('/novel-writer')
    } catch (error) {
      if (error !== 'cancel') {
        ElMessage.error('删除失败')
      }
    }
  }

  // ==================== 删除内容 ====================
  async function handleDeleteChapterContent(outline) {
    try {
      await novelWriterApi.deleteChapterContent(projectId.value, outline.chapter_number)
      ElMessage.success(`第${outline.chapter_number}章正文已删除`)
      if (refreshCallbacks.loadChapterOutlines) await refreshCallbacks.loadChapterOutlines()
    } catch (error) {
      ElMessage.error('删除失败')
    }
  }

  async function handleSyncContentStatus() {
    try {
      loading.value = true
      const res = await novelWriterApi.syncContentStatus(projectId.value)
      ElMessage.success(res.message || '正文状态同步成功')
      // 刷新对应类型的大纲列表
      if (project.value?.content_type === 'novel') {
        if (refreshCallbacks.loadChapterOutlines) await refreshCallbacks.loadChapterOutlines()
      } else if (project.value?.content_type === 'series_script') {
        if (refreshCallbacks.loadEpisodeOutlines) await refreshCallbacks.loadEpisodeOutlines()
      } else if (project.value?.content_type === 'movie_script') {
        if (refreshCallbacks.loadSceneOutlines) await refreshCallbacks.loadSceneOutlines()
      }
    } catch (error) {
      ElMessage.error('同步失败')
    } finally {
      loading.value = false
    }
  }

  async function handleClearAllOutlines() {
    try {
      await ElMessageBox.confirm(
        '确定要清空所有大纲吗？此操作不可恢复�?,
        '确认清空',
        { type: 'warning' }
      )
      await novelWriterApi.deleteAllOutlines(projectId.value)
      ElMessage.success('所有大纲已清空')
      await loadProject()
    } catch (error) {
      if (error !== 'cancel') {
        ElMessage.error('清空失败')
      }
    }
  }

  async function handleClearAllContent() {
    try {
      await ElMessageBox.confirm(
        '确定要清空所有正文吗？大纲将保留。此操作不可恢复�?,
        '确认清空',
        { type: 'warning' }
      )
      await novelWriterApi.deleteAllChapterContent(projectId.value)
      ElMessage.success('所有正文已清空')
      await loadProject()
    } catch (error) {
      if (error !== 'cancel') {
        ElMessage.error('清空失败')
      }
    }
  }

  async function handleClearAll() {
    try {
      await ElMessageBox.confirm(
        '确定要清空所有大纲和正文吗？此操作不可恢复！',
        '确认清空',
        { type: 'warning' }
      )
      await novelWriterApi.deleteAllContent(projectId.value)
      ElMessage.success('所有大纲和正文已清�?)
      await loadProject()
    } catch (error) {
      if (error !== 'cancel') {
        ElMessage.error('清空失败')
      }
    }
  }

  // ==================== 辅助函数 ====================
  function getStatusType(status) {
    const types = { init: 'info', generating: 'primary', completed: 'success', failed: 'danger', paused: 'warning' }
    return types[status] || 'info'
  }

  function getStatusText(status) {
    const texts = { init: '初始�?, generating: '生成�?, completed: '已完�?, failed: '失败', paused: '已暂�? }
    return texts[status] || status
  }

  function getChapterStatusType(status) {
    const types = { pending: 'info', drafting: 'warning', completed: 'success', failed: 'danger' }
    return types[status] || 'info'
  }

  function getChapterStatusText(status) {
    const texts = { pending: '待生�?, drafting: '生成�?, completed: '已完�?, failed: '失败' }
    return texts[status] || status
  }

  function formatDateTime(str) {
    if (!str) return ''
    return new Date(str).toLocaleString()
  }

  function getStepIcon(iconName) {
    const iconMap = {
      'Document': Document, 'Reading': Reading, 'Cpu': Cpu,
      'DataAnalysis': DataAnalysis, 'ChatDotRound': ChatDotRound,
      'Edit': Edit, 'Folder': Folder, 'List': List,
      'Loading': Loading, 'Finished': Finished,
      'CircleCheck': CircleCheck, 'CircleClose': CircleClose, 'Warning': Warning
    }
    return iconMap[iconName] || Loading
  }

  function formatDuration(ms) {
    if (!ms || ms < 0) return ''
    if (ms < 1000) return `${ms}ms`
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`
    return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`
  }

  const getDisplaySteps = computed(() => {
    const steps = taskStore.stepsHistory
    if (!steps || steps.length === 0) return []
    const stepMap = new Map()
    for (const step of steps) {
      const key = step.key
      if (!stepMap.has(key) || step.status === 'done' || step.status === 'error') {
        stepMap.set(key, step)
      }
    }
    return Array.from(stepMap.values()).reverse()
  })

  // 自动清理：组件卸载时停止任务监控，防止SSE连接和定时器泄漏
  onUnmounted(() => {
    stopTaskMonitoring()
  })

  return {
    // 路由
    route, router,
    // Store
    taskStore,
    // Core refs
    projectId, loading, project, chapters, selectedChapter, chapterContent,
    // Generate states
    generating, generatingChapter, generatingDirectory, regeneratingNames, manualUnitCount,
    // Unit summaries upload
    showUnitSummariesUploadDialog, unitSummariesUploadMode, unitSummariesInput,
    globalOutlineInput, uploadingUnitSummaries,
    // AbortController
    abortController,
    // Task monitoring
    taskPollingTimer, TASK_POLLING_INTERVAL, sseConnection, sseReconnectTimer, SSE_RECONNECT_DELAY,
    // Episode outlines
    episodeOutlines, generatingEpisodeOutlines, generatingSingleEpisode, selectedEpisode,
    // Batch generation
    generatingAllContent, batchContentType, batchProgress,
    // Batch count dialog
    showBatchCountDialog, batchCountLoading, batchCountConfig,
    // Episode detail dialog
    outlineDetailVisible, currentOutlineDetail, outlineEditMode, outlineEditContent,
    outlineEditTitle, savingOutlineEdit, editingEpisodeTitle, editEpisodeTitleValue,
    // Chapter editing
    editingChapter, editTitleValue,
    // Chapter outlines
    chapterOutlines, generatingChapterOutlines, generatingSingleChapterOutline,
    // Chapter outline dialog
    chapterOutlineDetailVisible, currentChapterOutlineDetail,
    chapterOutlineRevisionCompareVisible, chapterOutlineOriginalContent,
    chapterOutlineRevisedContent, chapterOutlineRevisionInfo, chapterOutlineRevisionViewMode,
    chapterOutlineEditMode, chapterOutlineEditContent, chapterOutlineEditTitle,
    savingChapterOutlineEdit, editingChapterOutlineTitle, editChapterOutlineTitleValue,
    // Scene outlines
    sceneOutlines, generatingSceneOutlines, generatingSingleSceneOutline,
    // Scene outline dialog
    sceneOutlineDetailVisible, currentSceneOutlineDetail,
    sceneOutlineEditMode, sceneOutlineEditContent, sceneOutlineEditTitle,
    savingSceneOutlineEdit, editingSceneOutlineTitle, editSceneOutlineTitleValue,
    // Intervention
    interventionDialogVisible, interventionData, interventionLoading,
    interventionUserChoice, interventionUserGuidance, interventionOptions,
    // Dialogs
    settingsVisible, exportVisible, savingSettings, exporting,
    // Knowledge base
    knowledgeGraphVisible,
    kbStatus, loadingKbStatus, buildingKb, resettingKbStatus,
    loadKnowledgeBaseStatus, refreshKnowledgeBaseStatus,
    handleBuildKnowledgeBase, handleDeleteKnowledgeBase, handleResetKbStatus,
    // Revision
    revisionCompareVisible, originalDraftContent, revisedContent,
    chapterRevisionInfo, revisionViewMode,
    // Compliance
    complianceDetailVisible, complianceDetailData, chapterComplianceMarking,
    // Issue labels
    ISSUE_TYPE_LABELS, getIssueTypeLabel, showComplianceDetail,
    // Revision computed
    revisionWordChange, revisionDiffHtml,
    // Chapter outline revision
    chapterOutlineRevisionWordChange, chapterOutlineRevisionDiffHtml,
    // Forms
    settingsForm, exportForm,
    // Computed
    canGenerate, totalWords, totalEpisodeCount, generatedEpisodeCount,
    renderedOutlineContent, totalChapterOutlineCount, generatedChapterOutlineCount,
    renderedChapterOutlineContent, totalSceneOutlineCount, generatedSceneOutlineCount,
    generatedEpisodeContentCount, generatedChapterContentCount, generatedSceneContentCount,
    renderedSceneOutlineContent, unitLabel, getTypeLabel, getTypeTagType,
    getDisplaySteps,
    // Diff
    computeDiffHtml, findLCS, escapeHtml,
    // Core methods
    loadProject, loadChapters, selectChapter, showRevisionCompareDialog,
    handleOutlineUpload, handleUploadUnitSummariesContent, handleUnitSummariesFileUpload,
    handleGenerateDirectory, handleRegenerateNames, handleRegenerateDirectory,
    cleanChapterTitle, startEditTitle, handleEnterSaveTitle, handleBlurSaveTitle,
    saveChapterTitle, cancelEditTitle,
    startGenerate, generateSingleChapter, saveChapterContent: saveChapterContent,
    handleDownloadChapter,
    showSettingsDialog, saveSettings, showExportDialog, handleExport, handleDelete,
    handleDeleteChapterContent, handleSyncContentStatus,
    handleClearAllOutlines, handleClearAllContent, handleClearAll,
    // Helpers
    getStatusType, getStatusText, getChapterStatusType, getChapterStatusText,
    formatDateTime, getStepIcon, formatDuration, showOutlineUpload,
    // SSE + Polling
    startSSEConnection, stopSSEConnection,
    startTaskMonitoring, stopTaskMonitoring,
    startTaskPolling, stopTaskPolling, refreshListByTaskType
  }
}
