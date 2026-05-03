/**
 * useProjectLoader - 项目加载和章节管理逻辑
 * 
 * 从 useProjectDetailState.js 提取，封装项目数据加载、章节管理、内容类型标签等。
 */
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { novelWriterApi } from '@/api/novel-writer'

export function useProjectLoader() {
  const route = useRoute()

  // ==================== 内容类型标签 ====================

  const CONTENT_TYPE_LABELS = {
    'novel': '小说',
    'series_script': '剧集剧本',
    'movie_script': '电影剧本'
  }

  const CONTENT_TYPE_TAG_TYPES = {
    'novel': 'success',
    'series_script': 'warning',
    'movie_script': 'danger'
  }

  // ==================== 核心状态 ====================

  const loading = ref(true)
  const project = ref(null)
  const chapters = ref([])
  const selectedChapter = ref(null)
  const chapterContent = ref('')

  const projectId = computed(() => parseInt(route.params.id))

  const contentTypeLabel = computed(() => {
    if (!project.value) return ''
    return CONTENT_TYPE_LABELS[project.value.content_type] || project.value.content_type
  })

  const contentTypeTagType = computed(() => {
    if (!project.value) return 'info'
    return CONTENT_TYPE_TAG_TYPES[project.value.content_type] || 'info'
  })

  // ==================== 项目加载 ====================

  async function loadProject() {
    if (!projectId.value) return

    loading.value = true
    try {
      const data = await novelWriterApi.getProject(projectId.value)
      project.value = data
    } catch (error) {
      console.error('加载项目失败:', error)
      ElMessage.error('加载项目失败')
    } finally {
      loading.value = false
    }
  }

  async function loadChapters() {
    if (!projectId.value) return

    try {
      const data = await novelWriterApi.getChapters(projectId.value)
      chapters.value = data || []
    } catch (error) {
      console.error('加载章节失败:', error)
    }
  }

  async function loadProjectData() {
    await Promise.all([loadProject(), loadChapters()])
  }

  // ==================== 章节选择 ====================

  function selectChapter(chapter) {
    selectedChapter.value = chapter
    chapterContent.value = chapter?.content || ''
  }

  function clearSelectedChapter() {
    selectedChapter.value = null
    chapterContent.value = ''
  }

  // ==================== 章节内容加载 ====================

  async function loadChapterContent(chapterId) {
    if (!projectId.value || !chapterId) return

    try {
      const data = await novelWriterApi.getChapterContent(projectId.value, chapterId)
      chapterContent.value = data?.content || ''
    } catch (error) {
      console.error('加载章节内容失败:', error)
      ElMessage.error('加载章节内容失败')
    }
  }

  // ==================== 章节内容保存 ====================

  async function saveChapterContent(chapterId, content) {
    if (!projectId.value || !chapterId) return

    try {
      await novelWriterApi.updateChapterContent(projectId.value, chapterId, { content })
      ElMessage.success('保存成功')
    } catch (error) {
      console.error('保存章节内容失败:', error)
      ElMessage.error('保存失败')
      throw error
    }
  }

  // ==================== 章节删除 ====================

  async function deleteChapter(chapterId) {
    if (!projectId.value || !chapterId) return

    try {
      await novelWriterApi.deleteChapter(projectId.value, chapterId)
      ElMessage.success('删除成功')
      await loadChapters()
    } catch (error) {
      console.error('删除章节失败:', error)
      ElMessage.error('删除失败')
      throw error
    }
  }

  return {
    loading,
    project,
    chapters,
    selectedChapter,
    chapterContent,
    projectId,
    contentTypeLabel,
    contentTypeTagType,
    loadProject,
    loadChapters,
    loadProjectData,
    selectChapter,
    clearSelectedChapter,
    loadChapterContent,
    saveChapterContent,
    deleteChapter
  }
}
