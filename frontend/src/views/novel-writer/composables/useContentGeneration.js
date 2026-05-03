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
      
      generating.value = true
      selectedEpisode.value = episodeNum
      ElMessage.info(`开始生成第${episodeNum}集正文...`)
      abortController.value = new AbortController()
      
      const res = await novelWriterApi.generateEpisodeContent(
        projectId.value, episodeNum, abortController.value.signal
      )
      
      if (res.success) {
        ElMessage.success(`第${episodeNum}集正文生成成功，共${res.data.word_count}字`)
        await loadProject()
        await loadChapters()
        if (res.data.chapter) {
          const newChapter = { ...res.data.chapter, chapter_number: res.data.chapter.chapter_number, status: 'completed', word_count: res.data.chapter.word_count }
          selectChapter(newChapter)
          chapterContent.value = res.data.content
        }
      } else {
        ElMessage.error(res.data?.error_message || '生成失败')
      }
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
      
      const res = await novelWriterApi.generateChapterContent(
        projectId.value, chapterNum, abortController.value.signal
      )
      
      if (res.success) {
        ElMessage.success(`第${chapterNum}章正文生成成功，共${res.data.word_count}字`)
        await loadProject()
        await loadChapters()
        await loadChapterOutlines()
        if (res.data.chapter) {
          const newChapter = { ...res.data.chapter, chapter_number: res.data.chapter.chapter_number, status: 'completed', word_count: res.data.chapter.word_count }
          selectChapter(newChapter)
          chapterContent.value = res.data.content
        }
      } else {
        ElMessage.error(res.data?.error_message || '生成失败')
      }
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
      
      const res = await novelWriterApi.generateSceneContent(
        projectId.value, sceneNum, abortController.value.signal
      )
      
      if (res.success) {
        ElMessage.success(`第${sceneNum}场正文生成成功，共${res.data.word_count}字`)
        await loadProject()
        await loadChapters()
        await loadSceneOutlines()
        if (res.data.chapter || res.data.content) {
          const newChapter = {
            id: res.data.chapter?.id,
            chapter_number: sceneNum,
            chapter_title: res.data.scene_title || `第${sceneNum}场`,
            status: 'completed',
            word_count: res.data.word_count
          }
          selectChapter(newChapter)
          chapterContent.value = res.data.content
        }
      } else {
        ElMessage.error(res.data?.error_message || '生成失败')
      }
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
    const totalEp = episodeOutlines.value.length
    if (totalEp === 0) { ElMessage.warning('请先设置集数'); return }
    
    const episodesWithOutline = episodeOutlines.value.filter(ep => ep.has_detailed)
    if (episodesWithOutline.length === 0) {
      ElMessage.warning('请先生成分集详细大纲')
      return
    }
    
    let pendingEpisodes
    if (episodeNumbers && Array.isArray(episodeNumbers)) {
      pendingEpisodes = episodeNumbers.filter(n => episodesWithOutline.some(ep => ep.episode_number === n))
      if (pendingEpisodes.length === 0) { ElMessage.warning('指定的集数没有详细大纲'); return }
    } else {
      const existingContent = episodesWithOutline
        .filter(ep => ep.content_status === 'generated').map(ep => ep.episode_number)
      const allEpisodeNumbers = episodesWithOutline.map(ep => ep.episode_number)
      pendingEpisodes = allEpisodeNumbers.filter(ep => !existingContent.includes(ep))
    }
    
    if (pendingEpisodes.length === 0) { ElMessage.success('全部分集正文已生成'); return }
    
    try {
      await ElMessageBox.confirm(
        `将生成第 ${Math.min(...pendingEpisodes)} 至第 ${Math.max(...pendingEpisodes)} 集，共 ${pendingEpisodes.length} 集正文。确定继续吗？`,
        '确认批量生成', { type: 'info' }
      )
      
      taskStore.setTask({
        project_id: projectId.value, task_type: 'episode_content', status: 'running',
        total_count: pendingEpisodes.length, completed_count: 0
      })
      
      generatingAllContent.value = true
      batchContentType.value = 'episode'
      abortController.value = new AbortController()
      
      const res = await novelWriterApi.generateAllEpisodeContent(projectId.value, {
        unit_numbers: pendingEpisodes, stop_on_error: true
      }, abortController.value.signal)
      
      if (res.success) {
        ElMessage.success('批量生成完成！成功' + res.data.completed_count + '集')
        await loadProject(); await loadChapters(); await loadEpisodeOutlines()
      }
    } catch (error) {
      if (error?.name === 'CanceledError' || error?.cancelled) { ElMessage.warning('批量生成已终止') }
      else if (error !== 'cancel') { ElMessage.error(error.response?.data?.detail || '批量生成失败') }
    } finally {
      generatingAllContent.value = false; batchContentType.value = null;
      abortController.value = null; taskStore.clearTask()
    }
  }

  // ==================== 批量正文生成（章节） ====================
  async function handleGenerateAllChapterContent(chapterNumbers = null) {
    const totalCh = chapterOutlines.value.length
    if (totalCh === 0) { ElMessage.warning('请先设置章节数'); return }
    
    const chaptersWithOutline = chapterOutlines.value.filter(ch => ch.has_detailed)
    if (chaptersWithOutline.length === 0) {
      ElMessage.warning('请先生成章节详细大纲'); return
    }
    
    let pendingChapters
    if (chapterNumbers && Array.isArray(chapterNumbers)) {
      pendingChapters = chapterNumbers.filter(n => chaptersWithOutline.some(ch => ch.chapter_number === n))
      if (pendingChapters.length === 0) { ElMessage.warning('指定的章节没有详细大纲'); return }
    } else {
      const existingContent = chaptersWithOutline
        .filter(ch => ch.content_status === 'generated').map(ch => ch.chapter_number)
      const allChapterNumbers = chaptersWithOutline.map(ch => ch.chapter_number)
      pendingChapters = allChapterNumbers.filter(ch => !existingContent.includes(ch))
    }
    
    if (pendingChapters.length === 0) { ElMessage.success('全部章节正文已生成'); return }
    
    try {
      await ElMessageBox.confirm(
        `将生成第 ${Math.min(...pendingChapters)} 至第 ${Math.max(...pendingChapters)} 章，共 ${pendingChapters.length} 章正文。确定继续吗？`,
        '确认批量生成', { type: 'info' }
      )
      
      taskStore.setTask({
        project_id: projectId.value, task_type: 'chapter_content', status: 'running',
        total_count: pendingChapters.length, completed_count: 0
      })
      
      generatingAllContent.value = true
      batchContentType.value = 'chapter'
      abortController.value = new AbortController()
      
      const res = await novelWriterApi.generateAllChapterContent(projectId.value, {
        unit_numbers: pendingChapters, stop_on_error: true
      }, abortController.value.signal)
      
      if (res.success) {
        ElMessage.success('批量生成完成！成功' + res.data.completed_count + '章')
        await loadProject(); await loadChapters(); await loadChapterOutlines()
      }
    } catch (error) {
      if (error?.name === 'CanceledError' || error?.cancelled) { ElMessage.warning('批量生成已终止') }
      else if (error !== 'cancel') { ElMessage.error(error.response?.data?.detail || '批量生成失败') }
    } finally {
      generatingAllContent.value = false; batchContentType.value = null;
      abortController.value = null; taskStore.clearTask()
    }
  }

  // ==================== 批量正文生成（场景） ====================
  async function handleGenerateAllSceneContent(sceneNumbers = null) {
    const scenesWithOutline = sceneOutlines.value.filter(sc => sc.has_detailed)
    if (scenesWithOutline.length === 0) {
      ElMessage.warning('请先生成场景详细大纲'); return
    }
    
    let pendingScenes
    if (sceneNumbers && Array.isArray(sceneNumbers)) {
      pendingScenes = sceneNumbers.filter(n => scenesWithOutline.some(sc => sc.scene_number === n))
      if (pendingScenes.length === 0) { ElMessage.warning('指定的场景没有详细大纲'); return }
    } else {
      const existingContent = scenesWithOutline
        .filter(sc => sc.content_status === 'generated').map(sc => sc.scene_number)
      const allSceneNumbers = scenesWithOutline.map(sc => sc.scene_number)
      pendingScenes = allSceneNumbers.filter(sc => !existingContent.includes(sc))
    }
    
    if (pendingScenes.length === 0) { ElMessage.success('全部场景正文已生成'); return }
    
    try {
      await ElMessageBox.confirm(
        `将生成第 ${Math.min(...pendingScenes)} 至第 ${Math.max(...pendingScenes)} 场，共 ${pendingScenes.length} 场正文。确定继续吗？`,
        '确认批量生成', { type: 'info' }
      )
      
      taskStore.setTask({
        project_id: projectId.value, task_type: 'scene_content', status: 'running',
        total_count: pendingScenes.length, completed_count: 0
      })
      
      generatingAllContent.value = true
      batchContentType.value = 'scene'
      abortController.value = new AbortController()
      
      const res = await novelWriterApi.generateAllSceneContent(projectId.value, {
        unit_numbers: pendingScenes, stop_on_error: true
      }, abortController.value.signal)
      
      if (res.success) {
        ElMessage.success('批量生成完成！成功' + res.data.completed_count + '场')
        await loadProject(); await loadChapters(); await loadSceneOutlines()
      }
    } catch (error) {
      if (error?.name === 'CanceledError' || error?.cancelled) { ElMessage.warning('批量生成已终止') }
      else if (error !== 'cancel') { ElMessage.error(error.response?.data?.detail || '批量生成失败') }
    } finally {
      generatingAllContent.value = false; batchContentType.value = null;
      abortController.value = null; taskStore.clearTask()
    }
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
