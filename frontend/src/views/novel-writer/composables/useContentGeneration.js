/**
 * useContentGeneration - 内容生成管理（单篇和批量）
 * 从 ProjectDetail.vue 中提取的所有内容生成相关逻辑
 */
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { novelWriterApi } from '@/api/novel-writer'

export function useContentGeneration(options) {
  const {
    projectId, project, chapters, selectedChapter, chapterContent,
    episodeOutlines, chapterOutlines, sceneOutlines,
    taskStore, abortController,
    // Callbacks for refreshing data
    loadProject, loadChapters, loadEpisodeOutlines,
    loadChapterOutlines, loadSceneOutlines, selectChapter,
    // Shared refs from useProjectDetailState (avoid duplication)
    generating: _generating,
    generatingChapter: _generatingChapter,
    generatingAllContent: _generatingAllContent,
    showBatchCountDialog: _showBatchCountDialog,
    batchCountLoading: _batchCountLoading,
    batchCountConfig: _batchCountConfig,
    batchContentType: _batchContentType,
    batchProgress: _batchProgress
  } = options

  // 使用外部传入的共享 ref（避免重复定义导致模板引用不一致）
  const generating = _generating || ref(false)
  const generatingChapter = _generatingChapter || ref(false)
  const selectedEpisode = ref(null)
  const selectedScene = ref(null)

  // 批量正文生成状态
  const generatingAllContent = _generatingAllContent || ref(false)
  const batchContentType = _batchContentType || ref(null)
  const batchProgress = _batchProgress || ref({ completed: 0, total: 0, current: null })

  // 指定数量生成对话框
  const showBatchCountDialog = _showBatchCountDialog || ref(false)
  const batchCountLoading = _batchCountLoading || ref(false)
  const batchCountConfig = _batchCountConfig || ref({
    startUnit: 1,
    count: 5,
    maxUnit: 100,
    unitLabel: '章',
    type: 'outline',
    contentType: 'chapter'
  })

  // 生成单集正文
  async function generateEpisodeContent(outline) {
    const episodeNum = outline.episode_number
    if (!outline.has_detailed) {
      ElMessage.warning('请先生成分集详细大纲')
      return
    }
    
    try {
      if (outline.content_status === 'generated') {
        await ElMessageBox.confirm(
          `第${episodeNum}集正文已生成，重新生成将覆盖原有内容。确定要继续吗？`,
          '确认重新生成',
          { type: 'warning' }
        )
      } else {
        await ElMessageBox.confirm(
          `确定要生成第${episodeNum}集的正文吗？可能需要较长时间。`,
          '确认生成',
          { type: 'info' }
        )
      }
      
      ElMessage.warning('正文生成已迁移至写作工作台的多Agent Pipeline系统，请在写作工作台中创建任务进行生成')
      return
    } catch (error) {
      if (error?.name === 'CanceledError' || error?.cancelled) {
        console.log('生成已被用户取消')
      } else if (error !== 'cancel') {
        console.error('生成分集正文失败:', error)
        ElMessage.error(error.response?.data?.detail || '生成失败')
      }
    } finally {
      generating.value = false
      selectedEpisode.value = null
      abortController.value = null
    }
  }

  // 生成单章正文
  async function generateChapterContentFn(outline) {
    const chapterNum = outline.chapter_number
    if (!outline.has_detailed) {
      ElMessage.warning('请先生成章节详细大纲')
      return
    }
    
    try {
      if (outline.content_status === 'generated') {
        await ElMessageBox.confirm(
          `第${chapterNum}章正文已生成，重新生成将覆盖原有内容。确定要继续吗？`,
          '确认重新生成',
          { type: 'warning' }
        )
      } else {
        await ElMessageBox.confirm(
          `确定要生成第${chapterNum}章的正文吗？可能需要较长时间。`,
          '确认生成',
          { type: 'info' }
        )
      }
      
      generating.value = true
      ElMessage.info(`开始生成第${chapterNum}章正文...`)
      abortController.value = new AbortController()
      
      ElMessage.warning('正文生成已迁移至写作工作台的多Agent Pipeline系统，请在写作工作台中创建任务进行生成')
      return
    } catch (error) {
      if (error?.name === 'CanceledError' || error?.cancelled) {
        console.log('生成已被用户取消')
      } else if (error !== 'cancel') {
        console.error('生成章节正文失败:', error)
        ElMessage.error(error.response?.data?.detail || '生成失败')
      }
    } finally {
      generating.value = false
      abortController.value = null
    }
  }

  // 生成单场正文
  async function generateSceneContentFn(outline) {
    const sceneNum = outline.scene_number
    if (!outline.has_detailed) {
      ElMessage.warning('请先生成场景详细大纲')
      return
    }
    
    try {
      if (outline.content_status === 'generated') {
        await ElMessageBox.confirm(
          `第${sceneNum}场正文已生成，重新生成将覆盖原有内容。确定要继续吗？`,
          '确认重新生成',
          { type: 'warning' }
        )
      } else {
        await ElMessageBox.confirm(
          `确定要生成第${sceneNum}场的正文吗？可能需要较长时间。`,
          '确认生成',
          { type: 'info' }
        )
      }
      
      generating.value = true
      selectedScene.value = sceneNum
      ElMessage.info(`开始生成第${sceneNum}场正文...`)
      abortController.value = new AbortController()
      
      ElMessage.warning('正文生成已迁移至写作工作台的多Agent Pipeline系统，请在写作工作台中创建任务进行生成')
      return
    } catch (error) {
      if (error?.name === 'CanceledError' || error?.cancelled) {
        console.log('生成已被用户取消')
      } else if (error !== 'cancel') {
        console.error('生成场景正文失败:', error)
        ElMessage.error(error.response?.data?.detail || '生成失败')
      }
    } finally {
      generating.value = false
      selectedScene.value = null
      abortController.value = null
    }
  }

  // 终止全部分集大纲生成
  function handleStopGeneration() {
    if (abortController.value) {
      abortController.value.abort()
      abortController.value = null
    }
    generating.value = false
    selectedEpisode.value = null
    selectedScene.value = null
    ElMessage.warning('已终止生成')
  }

  // ==================== 批量正文生成（分集） ====================
  async function handleGenerateAllEpisodeContent(episodeNumbers = null) {
    ElMessage.warning('批量正文生成已迁移至写作工作台的多Agent Pipeline系统，请在写作工作台中创建任务进行生成')
    return
  }

  // ==================== 批量正文生成（章节） ====================
  async function handleGenerateAllChapterContent(chapterNumbers = null) {
    ElMessage.warning('批量正文生成已迁移至写作工作台的多Agent Pipeline系统，请在写作工作台中创建任务进行生成')
    return
  }

  // ==================== 批量正文生成（场景） ====================
  async function handleGenerateAllSceneContent(sceneNumbers = null) {
    ElMessage.warning('批量正文生成已迁移至写作工作台的多Agent Pipeline系统，请在写作工作台中创建任务进行生成')
    return
  }

  // 终止批量生成
  function handleStopBatchGeneration() {
    if (abortController.value) { abortController.value.abort(); abortController.value = null }
    generatingAllContent.value = false
    batchContentType.value = null
    taskStore.cancelTask(projectId.value)
    ElMessage.warning('已终止批量生成')
  }

  // ==================== 指定数量生成对话框 ====================
  function openBatchCountDialog(type, contentType) {
    let defaultStart = 1
    let maxUnit = 100
    let unitLabelText = '章'
    
    if (type === 'outline') {
      if (contentType === 'chapter') {
        const existing = chapterOutlines.value.filter(o => o.has_detailed).map(o => o.chapter_number)
        defaultStart = existing.length > 0 ? Math.max(...existing) + 1 : 1
        maxUnit = totalChapterOutlineCount() || 100
        unitLabelText = '章'
      } else if (contentType === 'episode') {
        const existing = episodeOutlines.value.filter(o => o.has_detailed).map(o => o.episode_number)
        defaultStart = existing.length > 0 ? Math.max(...existing) + 1 : 1
        maxUnit = totalEpisodeCount() || 100
        unitLabelText = '集'
      } else if (contentType === 'scene') {
        const existing = sceneOutlines.value.filter(o => o.has_detailed).map(o => o.scene_number)
        defaultStart = existing.length > 0 ? Math.max(...existing) + 1 : 1
        maxUnit = totalSceneOutlineCount() || 100
        unitLabelText = '场'
      }
    } else {
      if (contentType === 'chapter') {
        const chaptersWithOutline = chapterOutlines.value.filter(ch => ch.has_detailed)
        const existingContent = chaptersWithOutline.filter(ch => ch.content_status === 'generated').map(ch => ch.chapter_number)
        const pending = chaptersWithOutline.map(ch => ch.chapter_number).filter(n => !existingContent.includes(n))
        defaultStart = pending.length > 0 ? Math.min(...pending) : 1
        maxUnit = totalChapterOutlineCount() || 100
        unitLabelText = '章'
      } else if (contentType === 'episode') {
        const episodesWithOutline = episodeOutlines.value.filter(ep => ep.has_detailed)
        const existingContent = episodesWithOutline.filter(ep => ep.content_status === 'generated').map(ep => ep.episode_number)
        const pending = episodesWithOutline.map(ep => ep.episode_number).filter(n => !existingContent.includes(n))
        defaultStart = pending.length > 0 ? Math.min(...pending) : 1
        maxUnit = totalEpisodeCount() || 100
        unitLabelText = '集'
      } else if (contentType === 'scene') {
        const scenesWithOutline = sceneOutlines.value.filter(sc => sc.has_detailed)
        const existingContent = scenesWithOutline.filter(sc => sc.content_status === 'generated').map(sc => sc.scene_number)
        const pending = scenesWithOutline.map(sc => sc.scene_number).filter(n => !existingContent.includes(n))
        defaultStart = pending.length > 0 ? Math.min(...pending) : 1
        maxUnit = totalSceneOutlineCount() || 100
        unitLabelText = '场'
      }
    }
    
    batchCountConfig.value = {
      startUnit: defaultStart, count: 5, maxUnit: maxUnit,
      unitLabel: unitLabelText, type: type, contentType: contentType
    }
    showBatchCountDialog.value = true
  }

  async function totalChapterOutlineCount() {
    return project.value?.total_chapters || 0
  }

  async function totalEpisodeCount() {
    return project.value?.series_script_config?.episode_count || project.value?.script_config?.episode_count || 0
  }

  async function totalSceneOutlineCount() {
    return project.value?.total_chapters || 0
  }

  // 执行指定数量生成
  async function executeBatchCountGenerate() {
    const { startUnit, count, type, contentType, maxUnit } = batchCountConfig.value
    const endUnit = Math.min(startUnit + count - 1, maxUnit)
    const unitNumbers = Array.from({ length: endUnit - startUnit + 1 }, (_, i) => startUnit + i)
    showBatchCountDialog.value = false
    
    if (type === 'outline') {
      if (contentType === 'chapter') {
        if (handleGenerateAllChapterOutlines) await handleGenerateAllChapterOutlines(unitNumbers)
      } else if (contentType === 'episode') {
        if (handleGenerateAllEpisodeOutlines) await handleGenerateAllEpisodeOutlines(unitNumbers)
      } else if (contentType === 'scene') {
        if (handleGenerateAllSceneOutlines) await handleGenerateAllSceneOutlines(unitNumbers)
      }
    } else {
      if (contentType === 'chapter') {
        await handleGenerateAllChapterContent(unitNumbers)
      } else if (contentType === 'episode') {
        await handleGenerateAllEpisodeContent(unitNumbers)
      } else if (contentType === 'scene') {
        await handleGenerateAllSceneContent(unitNumbers)
      }
    }
  }

  // 统一取消任务
  async function handleCancelTask() {
    const confirmed = await ElMessageBox.confirm(
      '确定要终止当前生成任务吗？', '确认终止', { type: 'warning' }
    ).catch(() => false)
    
    if (confirmed) {
      if (abortController.value) {
        abortController.value.abort()
        abortController.value = null
      }
      generatingAllContent.value = false
      batchContentType.value = null
      
      const success = await taskStore.cancelTask(projectId.value)
      if (success) {
        ElMessage.warning('已终止生成任务')
        await loadProject()
      }
    }
  }

  return {
    generating, generatingChapter, selectedEpisode, selectedScene,
    generatingAllContent, batchContentType, batchProgress,
    showBatchCountDialog, batchCountLoading, batchCountConfig,
    generateEpisodeContent,
    generateChapterContent: generateChapterContentFn,
    generateSceneContent: generateSceneContentFn,
    handleStopGeneration,
    handleGenerateAllEpisodeContent, handleGenerateAllChapterContent,
    handleGenerateAllSceneContent,
    handleStopBatchGeneration,
    openBatchCountDialog, executeBatchCountGenerate,
    handleCancelTask
  }
}
