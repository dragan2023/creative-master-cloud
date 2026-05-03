/**
 * 项目状态管理 Composable
 * 
 * 处理项目数据、单元概述、章节大纲等状态管理逻辑
 */
import { ref, computed, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { novelWriterApi } from '@/api/novel-writer'
import { getToken, getAuthHeaders } from '@/utils/authStorage'

/**
 * 项目状态 Composable
 * @param {Object} props - 组件 props
 * @param {Object} props.projectId - 项目ID
 * @param {Object} props.projectTotalUnits - 项目总单元数
 * @param {Object} props.unitSummaries - 单元概述数据
 * @param {Object} props.contentType - 内容类型
 * @param {Object} props.projectType - 项目类型
 * @param {Object} props.chapters - 章节列表
 * @param {Object} props.projectData - 项目数据
 * @param {Object} props.chapterOutlines - 章节大纲数据
 * @param {Function} emit - emit 函数
 */
export function useProjectState(props, emit) {
  const route = useRoute()

  // ==================== 响应式状态 ====================
  const localProjectData = ref({})
  const loadingProject = ref(false)
  const generatingDirectory = ref(false)

  // 大纲上传相关
  const showOutlineUploadDialog = ref(false)
  const outlineInput = ref('')
  const uploadingOutline = ref(false)
  const outlineUploadRef = ref(null)

  // 单元概述上传相关
  const showUnitSummariesUploadDialog = ref(false)
  const unitSummariesUploadRef = ref(null)
  const unitSummariesFileList = ref([])
  const uploadingUnitSummaries = ref(false)

  // 知识图谱相关
  const knowledgeGraphVisible = ref(false)

  // 章节大纲相关
  const showChapterOutlineDialog = ref(false)
  const currentChapterOutline = ref(null)
  const currentChapterNum = ref(null)
  const showOutlineListDialog = ref(false)

  // 单元大纲生成表单
  const outlineForm = ref({
    start_unit: 1,
    unit_count: null,
    skip_existing: true
  })

  // 生成章节大纲相关
  const generatingOutlines = ref(false)
  const chapterOutlineProgress = ref(null)
  const chapterOutlineEventSource = ref(null)

  // 项目设置弹窗
  const showSettingsDialog = ref(false)
  const showModelConfigDialog = ref(false)

  // 风格文档相关
  const styleDocumentInfo = ref(null)
  const showStyleDocumentDetail = ref(false)
  const aiEliminationEnabled = ref(true)
  const aiEliminationThreshold = ref(50)

  // ==================== 计算属性 ====================

  // 计算项目ID
  const projectId = computed(() => {
    if (props.projectId) return Number(props.projectId)
    if (route.params.id) return Number(route.params.id)
    return null
  })

  // 合并后的项目数据
  const projectData = computed(() => {
    return props.projectData && Object.keys(props.projectData).length > 0
      ? props.projectData
      : localProjectData.value
  })

  // 项目总单元数
  const projectTotalUnits = computed(() => {
    if (props.projectTotalUnits && props.projectTotalUnits > 0) {
      return props.projectTotalUnits
    }
    return projectData.value?.total_chapters || 0
  })

  // 根据项目类型获取单元标签
  const unitLabel = computed(() => {
    switch (props.contentType) {
      case 'series_script':
        return '集'
      case 'movie_script':
        return '场'
      default:
        return '章'
    }
  })

  // 单元概述数据
  const unitSummaries = computed(() => {
    if (props.unitSummaries && Object.keys(props.unitSummaries).length > 0) {
      return props.unitSummaries
    }
    return projectData.value?.unit_summaries || {}
  })

  // 是否有单元概述
  const hasUnitSummaries = computed(() => {
    return unitSummaries.value && Object.keys(unitSummaries.value).length > 0
  })

  // 章节大纲数据
  const chapterOutlines = computed(() => {
    if (props.chapterOutlines && Object.keys(props.chapterOutlines).length > 0) {
      return props.chapterOutlines
    }
    return projectData.value?.chapter_outlines || {}
  })

  // 是否可以生成章节大纲
  const canGenerateChapterOutlines = computed(() => {
    const effectiveType = props.contentType || props.projectType || 'novel'
    if (effectiveType !== 'novel') return false
    return hasUnitSummaries.value
  })

  // 章节大纲统计信息
  const chapterOutlineStats = computed(() => {
    const outlines = chapterOutlines.value || {}
    const total =
      projectTotalUnits.value ||
      Object.keys(unitSummaries.value || {}).length ||
      0
    const generated = Object.keys(outlines).filter((key) => {
      const outline = outlines[key]
      return outline && outline.status !== 'pending'
    }).length

    let lastGeneratedNum = 0
    for (let i = 1; i <= total; i++) {
      const outline = outlines[i.toString()]
      if (outline && outline.status !== 'pending') {
        lastGeneratedNum = i
      }
    }

    const nextToGenerate = lastGeneratedNum < total ? lastGeneratedNum + 1 : null

    return {
      total,
      generated,
      pending: total - generated,
      lastGeneratedNum,
      nextToGenerate,
      progress: total > 0 ? Math.round((generated / total) * 100) : 0
    }
  })

  // 智能推荐起始单元
  const recommendedStartUnit = computed(() => {
    const stats = chapterOutlineStats.value
    return stats.nextToGenerate || 1
  })

  // 已生成的章节大纲列表
  const generatedOutlineList = computed(() => {
    const outlines = chapterOutlines.value || {}
    const total =
      projectTotalUnits.value ||
      Object.keys(unitSummaries.value || {}).length ||
      0
    const generated = []

    for (let i = 1; i <= total; i++) {
      const outline = outlines[i.toString()]
      if (outline && outline.status !== 'pending') {
        generated.push({
          chapter_number: i,
          chapter_title: outline.chapter_title || `第${i}章`,
          status: outline.status || 'generated',
          chapter_summary: outline.chapter_summary || null,
          updated_at: outline.updated_at || null
        })
      }
    }

    return generated
  })

  // 风格文档上传地址
  const styleUploadAction = computed(() => {
    return `${import.meta.env.VITE_API_BASE_URL || ''}/api/v1/novel-writer/projects/${projectId.value}/style-document`
  })

  // 上传请求头（通过集中化存储层）
  const uploadHeaders = computed(() => getAuthHeaders())

  // ==================== 方法 ====================

  // 加载项目数据
  async function loadProjectData() {
    if (!projectId.value) return

    loadingProject.value = true
    try {
      const res = await novelWriterApi.getProject(projectId.value)
      if (res.success) {
        localProjectData.value = res.data
      }
    } catch (error) {
      ElMessage.error('加载项目数据失败')
    } finally {
      loadingProject.value = false
    }
  }

  // 加载风格文档信息
  async function loadStyleDocumentInfo() {
    if (!projectId.value) {
      console.warn('loadStyleDocumentInfo: projectId 为空，跳过加载')
      return
    }

    try {
      const res = await novelWriterApi.getStyleDocument(projectId.value)
      if (res.success) {
        styleDocumentInfo.value = res.data
        aiEliminationEnabled.value = res.data.ai_elimination_enabled ?? true
        aiEliminationThreshold.value = res.data.ai_elimination_threshold ?? 50
      }
    } catch (error) {
      console.error('加载风格文档信息失败:', error)
    }
  }

  // 生成目录
  async function handleGenerateDirectory() {
    generatingDirectory.value = true
    try {
      const res = await novelWriterApi.generateDirectory(projectId.value, {
        total_chapters: projectTotalUnits.value || 10,
        chapter_naming_style: '数字编号',
        generate_names: true
      })
      if (res.success) {
        ElMessage.success('目录生成成功')
        emit('refresh')
      } else {
        ElMessage.error(res.message || '目录生成失败')
      }
    } catch (error) {
      ElMessage.error('目录生成失败')
    } finally {
      generatingDirectory.value = false
    }
  }

  // 构建知识库 - 基于项目大纲构建项目专属知识图谱，辅助AI进行正文生成
  async function handleBuildKnowledgeBase() {
    try {
      const res = await novelWriterApi.buildKnowledgeBase(projectId.value)
      if (res.success) {
        ElMessage.success('知识库构建任务已启动')
      } else {
        ElMessage.error(res.message || '构建失败')
      }
    } catch (error) {
      ElMessage.error('知识库构建失败')
    }
  }

  // 大纲文件选择处理
  function handleOutlineFileChange(file) {
    const reader = new FileReader()
    reader.onload = (e) => {
      outlineInput.value = e.target.result
    }
    reader.readAsText(file.raw)
  }

  // 上传大纲
  async function handleUploadOutline() {
    if (!outlineInput.value.trim()) {
      ElMessage.warning('请输入大纲内容')
      return
    }

    uploadingOutline.value = true
    try {
      const res = await novelWriterApi.updateProject(projectId.value, {
        outline_content: outlineInput.value
      })

      if (res.success) {
        ElMessage.success('大纲上传成功')
        showOutlineUploadDialog.value = false
        outlineInput.value = ''
        emit('refresh')
      } else {
        ElMessage.error(res.message || '上传失败')
      }
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '上传失败')
    } finally {
      uploadingOutline.value = false
    }
  }

  // 处理单元概述文件选择
  function handleUnitSummariesFileChange(file) {
    unitSummariesFileList.value = [file.raw]
  }

  // 超出文件数量限制处理
  function handleUploadExceed(files) {
    ElMessage.warning('只能上传一个文件，请先移除当前文件')
  }

  // 取消上传
  function handleCancelUnitSummariesUpload() {
    showUnitSummariesUploadDialog.value = false
    unitSummariesFileList.value = []
  }

  // 上传单元概述文件
  async function handleUploadUnitSummariesFile() {
    if (unitSummariesFileList.value.length === 0) {
      ElMessage.warning('请选择要上传的文件')
      return
    }

    uploadingUnitSummaries.value = true
    try {
      const formData = new FormData()
      formData.append('file', unitSummariesFileList.value[0])

      const res = await novelWriterApi.uploadUnitSummariesFile(
        projectId.value,
        formData
      )
      if (res.success) {
        ElMessage.success(res.data?.message || '单元概述上传成功')
        showUnitSummariesUploadDialog.value = false
        unitSummariesFileList.value = []
        await loadProjectData()
        emit('refresh')
      } else {
        ElMessage.error(res.data?.message || '上传失败')
      }
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '上传失败')
    } finally {
      uploadingUnitSummaries.value = false
    }
  }

  // 生成章节详细大纲
  async function handleGenerateChapterOutlines() {
    if (!projectId.value) {
      ElMessage.warning('项目ID不存在')
      return
    }

    try {
      generatingOutlines.value = true
      chapterOutlineProgress.value = {
        status: 'running',
        message: '正在启动生成任务...',
        total: 0,
        generated: [],
        failed: [],
        current_chapter: null
      }

      const startUnit = outlineForm.value.start_unit || 1
      const unitCount = outlineForm.value.unit_count || null
      const skipExisting = outlineForm.value.skip_existing

      const response = await novelWriterApi.generateChapterOutlinesAsync(
        projectId.value,
        {
          start_unit: startUnit,
          unit_count: unitCount,
          stop_on_error: false,
          skip_existing: skipExisting
        }
      )

      if (response.success) {
        ElMessage.success('章节大纲生成任务已启动')
        connectChapterOutlineEvents()
      } else {
        ElMessage.error(response.data?.message || '启动任务失败')
        chapterOutlineProgress.value = null
      }
    } catch (error) {
      console.error('启动章节大纲生成失败:', error)
      ElMessage.error(
        '启动章节大纲生成失败: ' +
          (error.response?.data?.detail || error.message || '未知错误')
      )
      chapterOutlineProgress.value = null
    } finally {
      generatingOutlines.value = false
    }
  }

  // 建立SSE连接监听章节大纲生成进度
  function connectChapterOutlineEvents() {
    if (chapterOutlineEventSource.value) {
      chapterOutlineEventSource.value.close()
    }

    const token = getToken()
    const url = novelWriterApi.getChapterOutlinesEventsUrl(
      projectId.value,
      token
    )
    chapterOutlineEventSource.value = new EventSource(url)

    chapterOutlineEventSource.value.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        chapterOutlineProgress.value = data

        if (
          data.status === 'completed' ||
          data.status === 'interrupted' ||
          data.status === 'failed'
        ) {
          chapterOutlineEventSource.value.close()
          chapterOutlineEventSource.value = null

          loadProjectData()
          emit('refresh')

          if (data.status === 'completed') {
            const generatedCount = data.generated?.length || 0
            const failedCount = data.failed?.length || 0
            let message = `成功生成 ${generatedCount} 个章节详细大纲`
            if (failedCount > 0) {
              message += `，失败 ${failedCount} 个`
            }
            ElMessage.success(message)
          } else if (data.status === 'interrupted') {
            ElMessage.warning(data.message || '任务已中断')
          } else {
            ElMessage.error(data.message || '生成失败')
          }

          setTimeout(() => {
            chapterOutlineProgress.value = null
          }, 2000)
        }
      } catch (e) {
        console.error('解析SSE数据失败:', e)
      }
    }

    chapterOutlineEventSource.value.onerror = (error) => {
      console.error('SSE连接错误:', error)
      if (chapterOutlineEventSource.value) {
        chapterOutlineEventSource.value.close()
        chapterOutlineEventSource.value = null
      }
    }
  }

  // 中断章节大纲生成
  async function handleInterruptChapterOutlines() {
    if (!projectId.value) return

    try {
      const response = await novelWriterApi.interruptChapterOutlines(
        projectId.value
      )
      if (response.success) {
        ElMessage.success('中断信号已发送')
      } else {
        ElMessage.warning(response.data?.message || '没有运行中的任务')
        chapterOutlineProgress.value = null
      }
    } catch (error) {
      console.error('中断章节大纲生成失败:', error)
      ElMessage.error(
        '中断失败: ' +
          (error.response?.data?.detail || error.message || '未知错误')
      )
    }
  }

  // 从断点继续生成
  function handleContinueFromBreakpoint() {
    outlineForm.value.start_unit = recommendedStartUnit.value
    outlineForm.value.skip_existing = true
    handleGenerateChapterOutlines()
  }

  // 查看章节大纲
  async function handleViewChapterOutline(chapterNum) {
    try {
      const outlines = chapterOutlines.value || {}
      let outline = outlines[chapterNum.toString()]

      if (!outline || !outline.detailed_outline) {
        const res = await novelWriterApi.getChapterOutline(
          projectId.value,
          chapterNum
        )
        if (res.success && res.data) {
          outline = res.data
        }
      }

      if (outline) {
        currentChapterOutline.value = outline
        currentChapterNum.value = chapterNum
        showChapterOutlineDialog.value = true
      } else {
        ElMessage.warning('未找到章节大纲数据')
      }
    } catch (error) {
      console.error('获取章节大纲失败:', error)
      ElMessage.error('获取章节大纲失败')
    }
  }

  // 编辑章节大纲
  function handleEditChapterOutline() {
    if (!currentChapterNum.value) return
    ElMessage.info('章节大纲编辑功能开发中')
  }

  // 风格文档上传前校验
  function beforeStyleUpload(file) {
    const allowedTypes = ['.txt', '.docx', '.pdf', '.md']
    const fileExt = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()

    if (!allowedTypes.includes(fileExt)) {
      ElMessage.warning('仅支持 .txt, .docx, .pdf, .md 格式的文件')
      return false
    }

    const maxSize = 10 * 1024 * 1024
    if (file.size > maxSize) {
      ElMessage.warning('文件大小不能超过10MB')
      return false
    }

    return true
  }

  // 风格文档上传成功
  function handleStyleUploadSuccess(response) {
    if (response.success) {
      ElMessage.success('风格文档上传成功，正在分析中...')
      loadStyleDocumentInfo()
    } else {
      ElMessage.error(response.message || '上传失败')
    }
  }

  // 风格文档上传失败
  function handleStyleUploadError(error) {
    console.error('风格文档上传失败:', error)
    ElMessage.error('风格文档上传失败')
  }

  // 删除风格文档
  async function handleDeleteStyleDocument() {
    if (!projectId.value) {
      ElMessage.warning('项目ID不存在')
      return
    }

    try {
      const { ElMessageBox } = await import('element-plus')
      await ElMessageBox.confirm(
        '确定要删除风格文档吗？删除后AI将无法模仿该文档的写作风格。',
        '确认删除',
        {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        }
      )

      const res = await novelWriterApi.deleteStyleDocument(projectId.value)
      if (res.success) {
        ElMessage.success('风格文档已删除')
        await loadStyleDocumentInfo()
      } else {
        ElMessage.error(res.message || '删除失败')
      }
    } catch (error) {
      if (error !== 'cancel') {
        console.error('删除风格文档失败:', error)
        ElMessage.error('删除失败: ' + (error.message || '未知错误'))
      }
    }
  }

  // AI文风消除开关变更
  async function handleAiEliminationChange(value) {
    try {
      await novelWriterApi.updateStyleDocumentSettings(projectId.value, {
        ai_elimination_enabled: value
      })
      ElMessage.success(value ? '已启用AI文风消除' : '已关闭AI文风消除')
    } catch (error) {
      ElMessage.error('设置保存失败')
      aiEliminationEnabled.value = !value
    }
  }

  // 消除强度变更
  async function handleThresholdChange(value) {
    try {
      await novelWriterApi.updateStyleDocumentSettings(projectId.value, {
        ai_elimination_threshold: value
      })
    } catch (error) {
      console.error('保存消除强度失败:', error)
    }
  }

  // 清理资源
  function cleanup() {
    if (chapterOutlineEventSource.value) {
      chapterOutlineEventSource.value.close()
      chapterOutlineEventSource.value = null
    }
  }

  // 获取内容类型标签
  function getContentTypeLabel(type) {
    const labels = {
      novel: '小说',
      series_script: '连续剧剧本',
      movie_script: '电影剧本'
    }
    return labels[type] || '小说'
  }

  // 获取内容类型标签样式
  function getContentTypeTagType(type) {
    const types = {
      novel: 'primary',
      series_script: 'success',
      movie_script: 'warning'
    }
    return types[type] || 'primary'
  }

  return {
    // 状态
    localProjectData,
    loadingProject,
    generatingDirectory,
    showOutlineUploadDialog,
    outlineInput,
    uploadingOutline,
    outlineUploadRef,
    showUnitSummariesUploadDialog,
    unitSummariesUploadRef,
    unitSummariesFileList,
    uploadingUnitSummaries,
    knowledgeGraphVisible,
    showChapterOutlineDialog,
    currentChapterOutline,
    currentChapterNum,
    showOutlineListDialog,
    outlineForm,
    generatingOutlines,
    chapterOutlineProgress,
    chapterOutlineEventSource,
    showSettingsDialog,
    showModelConfigDialog,
    styleDocumentInfo,
    showStyleDocumentDetail,
    aiEliminationEnabled,
    aiEliminationThreshold,

    // 计算属性
    projectId,
    projectData,
    projectTotalUnits,
    unitLabel,
    unitSummaries,
    hasUnitSummaries,
    chapterOutlines,
    canGenerateChapterOutlines,
    chapterOutlineStats,
    recommendedStartUnit,
    generatedOutlineList,
    styleUploadAction,
    uploadHeaders,

    // 方法
    loadProjectData,
    loadStyleDocumentInfo,
    handleGenerateDirectory,
    handleBuildKnowledgeBase,
    handleOutlineFileChange,
    handleUploadOutline,
    handleUnitSummariesFileChange,
    handleUploadExceed,
    handleCancelUnitSummariesUpload,
    handleUploadUnitSummariesFile,
    handleGenerateChapterOutlines,
    handleInterruptChapterOutlines,
    handleContinueFromBreakpoint,
    handleViewChapterOutline,
    handleEditChapterOutline,
    beforeStyleUpload,
    handleStyleUploadSuccess,
    handleStyleUploadError,
    handleDeleteStyleDocument,
    handleAiEliminationChange,
    handleThresholdChange,
    cleanup,
    getContentTypeLabel,
    getContentTypeTagType
  }
}
