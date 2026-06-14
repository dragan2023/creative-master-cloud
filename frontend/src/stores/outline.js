/**
 * useOutlineStore - 大纲管理 Pinia Store
 *
 * 将 useOutlineManagement 的 30+ 参数传递重构为集中式状态管理。
 * 所有大纲相关的状态和方法统一在此 store 中管理，
 * 调用方只需 store = useOutlineStore() 即可访问一切。
 *
 * 迁移时间: 2026-04-26
 * 原始文件: composables/useOutlineManagement.js (985行, 30+参数)
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { novelWriterApi } from '@/api/novel-writer'

export const useOutlineStore = defineStore('outline', () => {
  // ========================================================================
  //  外部依赖（需要在 initProject 时设置）
  // ========================================================================
  const _projectId = ref(null)
  const _project = ref(null)
  const _taskStore = ref(null)
  const _abortController = ref(null)
  const _loadProject = ref(null)
  const _loadChapters = ref(null)
  const _startTaskPolling = ref(null)
  const _stopTaskPolling = ref(null)

  /**
   * 初始化项目上下文 — 由 ProjectDetail.vue 在 setup 时调用一次
   */
  function initProject(deps) {
    _projectId.value = deps.projectId
    _project.value = deps.project
    _taskStore.value = deps.taskStore
    _abortController.value = deps.abortController
    _loadProject.value = deps.loadProject
    _loadChapters.value = deps.loadChapters
    _startTaskPolling.value = deps.startTaskPolling
    _stopTaskPolling.value = deps.stopTaskPolling
  }

  // 便捷访问器
  const projectId = computed(() => _projectId.value)
  const project = computed(() => _project.value)

  // ========================================================================
  //  分集大纲状态
  // ========================================================================
  const episodeOutlines = ref([])
  const generatingEpisodeOutlines = ref(false)
  const generatingSingleEpisode = ref(null)

  // 分集大纲详情弹窗
  const outlineDetailVisible = ref(false)
  const currentOutlineDetail = ref({ episode_number: 0, episode_title: '', raw_content: '' })
  const outlineEditMode = ref(false)
  const outlineEditContent = ref('')
  const outlineEditTitle = ref('')
  const savingOutlineEdit = ref(false)
  const editingEpisodeTitle = ref(null)
  const editEpisodeTitleValue = ref('')

  // ========================================================================
  //  章节大纲状态
  // ========================================================================
  const chapterOutlines = ref([])
  const generatingChapterOutlines = ref(false)
  const generatingSingleChapterOutline = ref(null)

  // 章节大纲详情弹窗
  const chapterOutlineDetailVisible = ref(false)
  const currentChapterOutlineDetail = ref({
    chapter_number: 0, chapter_title: '', raw_content: '',
    revision_info: null, original_content: null
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

  // ========================================================================
  //  场景大纲状态
  // ========================================================================
  const sceneOutlines = ref([])
  const generatingSceneOutlines = ref(false)
  const generatingSingleSceneOutline = ref(null)

  // 场景大纲详情弹窗
  const sceneOutlineDetailVisible = ref(false)
  const currentSceneOutlineDetail = ref({ scene_number: 0, scene_title: '', raw_content: '' })
  const sceneOutlineEditMode = ref(false)
  const sceneOutlineEditContent = ref('')
  const sceneOutlineEditTitle = ref('')
  const savingSceneOutlineEdit = ref(false)
  const editingSceneOutlineTitle = ref(null)
  const editSceneOutlineTitleValue = ref('')

  // ========================================================================
  //  用户干预状态
  // ========================================================================
  const interventionDialogVisible = ref(false)
  const interventionData = ref({
    unit_number: 0, content_type: 'novel', inferred_summary: '',
    reference_info: null, message: ''
  })
  const interventionLoading = ref(false)
  const interventionUserChoice = ref('')
  const interventionUserGuidance = ref('')
  const interventionOptions = [
    { value: 'accept', label: '接受推断结果', desc: '使用系统推断的概要继续生成', icon: 'CircleCheck' },
    { value: 'provide', label: '提供概要内容', desc: '自行输入章节概要', icon: 'Edit' },
    { value: 'reference', label: '参考相邻章节', desc: '使用前后章节信息重新生成', icon: 'Reading' },
    { value: 'skip', label: '跳过此章节', desc: '暂时跳过，稍后处理', icon: 'VideoPause' }
  ]

  // ========================================================================
  //  计算属性
  // ========================================================================
  const totalEpisodeCount = computed(() => project.value?.episode_count || 0)
  const totalChapterOutlineCount = computed(() => project.value?.chapter_count || 0)
  const totalSceneOutlineCount = computed(() => project.value?.scene_count || 0)

  const generatedEpisodeCount = computed(() =>
    episodeOutlines.value.filter(e => e.has_detailed).length
  )
  const generatedChapterOutlineCount = computed(() =>
    chapterOutlines.value.filter(c => c.has_detailed).length
  )
  const generatedSceneOutlineCount = computed(() =>
    sceneOutlines.value.filter(s => s.has_detailed).length
  )

  const generatedEpisodeContentCount = computed(() =>
    episodeOutlines.value.filter(e => e.content_status === 'generated').length
  )
  const generatedChapterContentCount = computed(() =>
    chapterOutlines.value.filter(c => c.content_status === 'generated').length
  )
  const generatedSceneContentCount = computed(() =>
    sceneOutlines.value.filter(s => s.content_status === 'generated').length
  )

  const unitLabel = computed(() => {
    const type = project.value?.content_type
    if (type === 'series_script') return '集'
    if (type === 'movie_script') return '场'
    return '章'
  })

  // ========================================================================
  //  辅助: 下载Blob
  // ========================================================================
  function downloadBlob(content, fileName, mimeType) {
    const blob = new Blob([content], { type: mimeType })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = fileName; a.click()
    URL.revokeObjectURL(url)
  }

  // ========================================================================
  //  分集大纲操作
  // ========================================================================
  async function loadEpisodeOutlines() {
    if (project.value?.content_type !== 'series_script' && project.value?.project_type !== 'script') return
    try {
      const res = await novelWriterApi.getEpisodeOutlines(projectId.value)
      if (res.success && res.data) {
        const episodes = res.data.episodes || []
        episodeOutlines.value = episodes.map(ep => ({
          episode_number: ep.episode_number,
          episode_title: ep.episode_title || `第${ep.episode_number}集`,
          has_detailed: ep.status === 'generated' || ep.status === 'edited',
          content_status: ep.content_status || null,
          content_word_count: ep.content_word_count || 0,
          ...ep
        }))
      }
    } catch (error) {
      console.error('加载分集大纲失败', error)
    }
  }

  async function handleGenerateAllEpisodeOutlines(episodeNumbers = null) {
    const totalEp = totalEpisodeCount.value
    if (totalEp === 0) { ElMessage.warning('请先设置集数'); return }

    let pendingEpisodes
    if (episodeNumbers && Array.isArray(episodeNumbers)) {
      pendingEpisodes = episodeNumbers
    } else {
      const existingEpisodes = episodeOutlines.value.filter(ep => ep.has_detailed).map(ep => ep.episode_number)
      const allEpisodes = Array.from({ length: totalEp }, (_, i) => i + 1)
      pendingEpisodes = allEpisodes.filter(ep => !existingEpisodes.includes(ep))
    }

    if (pendingEpisodes.length === 0) { ElMessage.success('全部分集大纲已生成'); return }

    try {
      await ElMessageBox.confirm(
        pendingEpisodes.length !== totalEp
          ? `将生成第 ${Math.min(...pendingEpisodes)} 至第 ${Math.max(...pendingEpisodes)} 集，共 ${pendingEpisodes.length} 集。确定继续吗？`
          : `确定要生成全部 ${pendingEpisodes.length} 集的详细大纲吗？`,
        '确认生成', { type: 'info' }
      )

      _taskStore.value.setTask({
        project_id: projectId.value, task_type: 'episode_outline', status: 'running',
        total_count: pendingEpisodes.length, completed_count: 0
      })

      generatingEpisodeOutlines.value = true
      _abortController.value = new AbortController()
      _startTaskPolling.value()

      const res = await novelWriterApi.generateAllEpisodeOutlines(projectId.value, {
        episode_numbers: pendingEpisodes, stop_on_error: true
      }, _abortController.value.signal)

      _stopTaskPolling.value()

      if (res.success) {
        ElMessage.success(`分集大纲生成完成！成功 ${res.data.completed_count} 集，失败 ${res.data.failed_count} 集`)
        await _loadProject.value(); await loadEpisodeOutlines()
      }
    } catch (error) {
      _stopTaskPolling.value()
      if (error === 'cancel' || error?.cancelled) return
      console.error('生成分集大纲失败:', error)
      ElMessage.error('生成分集大纲失败')
    } finally {
      generatingEpisodeOutlines.value = false
      _abortController.value = null
      _taskStore.value.clearTask()
    }
  }

  async function handleGenerateSingleEpisodeOutline(episodeNum) {
    generatingSingleEpisode.value = episodeNum
    try {
      ElMessage.info(`正在生成第 ${episodeNum} 集详细大纲...`)
      const res = await novelWriterApi.generateOutlineWithIntervention(projectId.value, episodeNum, {
        content_type: 'series_script'
      })
      if (res.success) {
        const status = res.data?.status
        if (status === 'need_intervention') {
          showInterventionDialog(episodeNum, res.data)
          return
        } else if (status === 'success' || status === 'completed') {
          ElMessage.success(`第 ${episodeNum} 集详细大纲生成成功`)
          await _loadProject.value(); await loadEpisodeOutlines()
        } else if (status === 'skipped') {
          ElMessage.info(`第 ${episodeNum} 集已跳过`)
        } else {
          ElMessage.error(res.data?.message || '生成失败')
        }
      } else {
        ElMessage.error(res.data?.error_message || res.data?.message || '生成失败')
      }
    } catch (error) {
      if (error?.cancelled) return
      console.error('生成分集大纲失败:', error)
      ElMessage.error(`第 ${episodeNum} 集详细大纲生成失败`)
    } finally {
      generatingSingleEpisode.value = null
    }
  }

  async function showEpisodeOutlineDetail(outline) {
    try {
      const res = await novelWriterApi.getEpisodeOutline(projectId.value, outline.episode_number)
      if (res.success && res.data) {
        currentOutlineDetail.value = {
          episode_number: outline.episode_number,
          episode_title: outline.episode_title || `第${outline.episode_number}集`,
          raw_content: res.data.detailed_outline || ''
        }
        outlineDetailVisible.value = true
      }
    } catch (error) {
      console.error('获取分集大纲详情失败', error)
      ElMessage.error('获取大纲详情失败')
    }
  }

  function startEditOutline() {
    outlineEditContent.value = currentOutlineDetail.value.raw_content
    outlineEditTitle.value = currentOutlineDetail.value.episode_title
    outlineEditMode.value = true
  }

  function cancelEditOutline() {
    outlineEditMode.value = false
    outlineEditContent.value = ''
    outlineEditTitle.value = ''
  }

  async function saveOutlineEdit() {
    if (!outlineEditContent.value.trim()) { ElMessage.warning('大纲内容不能为空'); return }
    savingOutlineEdit.value = true
    try {
      const res = await novelWriterApi.updateEpisodeOutline(
        projectId.value, currentOutlineDetail.value.episode_number,
        { episode_title: outlineEditTitle.value, detailed_outline: outlineEditContent.value }
      )
      if (res.success) {
        currentOutlineDetail.value.episode_title = outlineEditTitle.value
        currentOutlineDetail.value.raw_content = outlineEditContent.value
        outlineEditMode.value = false
        await loadEpisodeOutlines()
        ElMessage.success('大纲已保存')
      }
    } catch (error) {
      console.error('保存大纲失败', error)
      ElMessage.error('保存失败')
    } finally {
      savingOutlineEdit.value = false
    }
  }

  function downloadSingleEpisodeOutline() {
    const content = currentOutlineDetail.value.raw_content
    if (!content) { ElMessage.warning('暂无内容可下载'); return }
    const episodeNum = currentOutlineDetail.value.episode_number
    const episodeTitle = currentOutlineDetail.value.episode_title
    downloadBlob(content, `${project.value?.title || '剧本'}_第${episodeNum}集_${episodeTitle}.md`, 'text/markdown;charset=utf-8')
    ElMessage.success('下载成功')
  }

  async function downloadEpisodeOutline(outline) {
    try {
      const res = await novelWriterApi.getEpisodeOutline(projectId.value, outline.episode_number)
      if (res.success && res.data?.detailed_outline) {
        downloadBlob(res.data.detailed_outline,
          `${project.value?.title || '剧本'}_第${outline.episode_number}集_${outline.episode_title}.md`,
          'text/markdown;charset=utf-8')
        ElMessage.success('下载成功')
      } else { ElMessage.warning('暂无内容可下载') }
    } catch (error) { console.error('下载大纲失败', error); ElMessage.error('下载失败') }
  }

  async function downloadAllEpisodeOutlines() {
    const generatedOutlines = episodeOutlines.value.filter(e => e.has_detailed)
    if (generatedOutlines.length === 0) { ElMessage.warning('暂无已生成的大纲可下载'); return }
    try {
      const promises = generatedOutlines.map(o => novelWriterApi.getEpisodeOutline(projectId.value, o.episode_number))
      const results = await Promise.all(promises)
      let mergedContent = `# ${project.value?.title || '剧本'} - 分集详细大纲\n\n> 共 ${generatedOutlines.length} 集\n\n---\n\n`
      results.forEach((res, index) => {
        const outline = generatedOutlines[index]
        if (res.success && res.data?.detailed_outline) {
          mergedContent += `## 第${outline.episode_number}集 ${outline.episode_title}\n\n${res.data.detailed_outline}\n\n---\n\n`
        }
      })
      downloadBlob(mergedContent, `${project.value?.title || '剧本'}_分集详细大纲_全集.md`, 'text/markdown;charset=utf-8')
      ElMessage.success(`已下载 ${generatedOutlines.length} 集大纲`)
    } catch (error) { console.error('下载全部大纲失败', error); ElMessage.error('下载失败') }
  }

  async function downloadAllEpisodeContent() {
    const generatedContents = episodeOutlines.value.filter(e => e.content_status === 'generated')
    if (generatedContents.length === 0) { ElMessage.warning('暂无已生成的正文可下载'); return }
    try {
      ElMessage.info('正在获取正文内容...')
      const res = await novelWriterApi.getAllScriptContent(projectId.value)
      if (!res?.success || !res?.data) { ElMessage.warning('暂无内容可下载'); return }

      const { project_title, contents, ai_resources, total_count } = res.data
      const safeTitle = (project_title || '剧本').replace(/[\\/:*?"<>|]/g, '_')

      // 文件1: 剧本正文
      let scriptMd = `\uFEFF# ${project_title || '剧本'} - 分集正文\n\n> 共 ${contents?.length || 0} 集\n\n---\n\n`
      if (contents && contents.length > 0) {
        contents.forEach(item => {
          scriptMd += `## 第${item.unit_index}集 ${item.unit_title}\n\n${item.content}\n\n---\n\n`
        })
      } else {
        scriptMd += `*暂无正文内容*\n\n`
      }
      downloadBlob(scriptMd, `${safeTitle}_剧本正文_全集.md`, 'text/markdown;charset=utf-8')

      // 文件2: AI资源提示词
      let aiMd = `\uFEFF# ${project_title || '剧本'} - AI资源提示词\n\n> 共 ${total_count || 0} 集\n\n---\n\n`
      if (ai_resources && ai_resources.length > 0) {
        ai_resources.forEach(item => {
          aiMd += `## 第${item.unit_index}集 ${item.unit_title}\n\n${item.content}\n\n---\n\n`
        })
      } else {
        aiMd += `*暂无AI资源内容*\n\n`
      }
      setTimeout(() => {
        downloadBlob(aiMd, `${safeTitle}_AI资源提示词_全集.md`, 'text/markdown;charset=utf-8')
        ElMessage.success(`已下载 ${contents?.length || 0} 集正文 + AI资源`)
      }, 200)
    } catch (error) { console.error('下载全部正文失败', error); ElMessage.error('下载失败') }
  }

  function startEditEpisodeTitle(outline) {
    editingEpisodeTitle.value = outline.episode_number
    editEpisodeTitleValue.value = outline.episode_title || ''
  }

  function cancelEditEpisodeTitle() {
    editingEpisodeTitle.value = null
    editEpisodeTitleValue.value = ''
  }

  async function saveEpisodeTitle(outline) {
    if (!editEpisodeTitleValue.value.trim()) { ElMessage.warning('标题不能为空'); return }
    if (editEpisodeTitleValue.value === outline.episode_title) { editingEpisodeTitle.value = null; return }
    try {
      const res = await novelWriterApi.updateEpisodeOutline(
        projectId.value, outline.episode_number,
        { episode_title: editEpisodeTitleValue.value }
      )
      if (res.success) {
        outline.episode_title = editEpisodeTitleValue.value
        editingEpisodeTitle.value = null
        ElMessage.success('集标题已更新')
      }
    } catch (error) { console.error('更新集标题失败', error); ElMessage.error('更新失败') }
  }

  async function handleDeleteEpisodeContent(outline) {
    try {
      await novelWriterApi.deleteEpisodeContent(projectId.value, outline.episode_number)
      ElMessage.success(`第${outline.episode_number}集正文已删除`)
      await loadEpisodeOutlines()
    } catch (error) { ElMessage.error('删除失败') }
  }

  async function handleDeleteEpisodeOutline(outline) {
    try {
      await novelWriterApi.deleteEpisodeOutline(projectId.value, outline.episode_number)
      ElMessage.success(`第${outline.episode_number}集大纲已删除`)
      await loadEpisodeOutlines()
    } catch (error) { ElMessage.error('删除失败') }
  }

  // ========================================================================
  //  章节大纲操作
  // ========================================================================
  async function loadChapterOutlines() {
    if (project.value?.content_type !== 'novel') return
    try {
      const res = await novelWriterApi.getChapterOutlines(projectId.value)
      if (res.success && res.data) {
        const chapters = res.data.chapters || []
        chapterOutlines.value = chapters.map(ch => ({
          chapter_number: ch.chapter_number,
          chapter_title: ch.chapter_title || `第${ch.chapter_number}章`,
          has_detailed: ch.status === 'generated' || ch.status === 'edited',
          content_status: ch.content_status || null,
          content_word_count: ch.content_word_count || 0,
          ...ch
        }))
      }
    } catch (error) { console.error('加载章节大纲失败', error) }
  }

  async function handleGenerateAllChapterOutlines(chapterNumbers = null) {
    const totalCh = totalChapterOutlineCount.value
    if (totalCh === 0) { ElMessage.warning('请先设置章节数'); return }

    let pendingChapters
    if (chapterNumbers && Array.isArray(chapterNumbers)) {
      pendingChapters = chapterNumbers
    } else {
      const existingChapters = chapterOutlines.value.filter(ch => ch.has_detailed).map(ch => ch.chapter_number)
      const allChapters = Array.from({ length: totalCh }, (_, i) => i + 1)
      pendingChapters = allChapters.filter(ch => !existingChapters.includes(ch))
    }

    if (pendingChapters.length === 0) { ElMessage.success('全部章节大纲已生成'); return }

    const confirmMsg = pendingChapters.length !== totalCh
      ? `将生成第 ${Math.min(...pendingChapters)} 至第 ${Math.max(...pendingChapters)} 章，共 ${pendingChapters.length} 章。确定继续吗？`
      : `确定要生成全部 ${pendingChapters.length} 章的详细大纲吗？`

    try {
      await ElMessageBox.confirm(confirmMsg, '确认生成', { type: 'info' })

      _taskStore.value.setTask({
        project_id: projectId.value, task_type: 'chapter_outline', status: 'running',
        total_count: pendingChapters.length, completed_count: 0
      })

      generatingChapterOutlines.value = true
      _abortController.value = new AbortController()
      _startTaskPolling.value()

      const res = await novelWriterApi.generateAllChapterOutlines(projectId.value, {
        chapter_numbers: pendingChapters, stop_on_error: true
      }, _abortController.value.signal)

      _stopTaskPolling.value()

      if (res.success) {
        ElMessage.success(`章节大纲生成完成！成功 ${res.data.completed_count} 章，失败 ${res.data.failed_count} 章`)
        await _loadProject.value(); await loadChapterOutlines()
      }
    } catch (error) {
      _stopTaskPolling.value()
      if (error === 'cancel' || error?.cancelled) return
      console.error('生成章节大纲失败:', error)
      ElMessage.error('生成章节大纲失败')
    } finally {
      generatingChapterOutlines.value = false
      _abortController.value = null
      _taskStore.value.clearTask()
    }
  }

  async function handleGenerateSingleChapterOutline(chapterNum, forceRegenerate = false) {
    generatingSingleChapterOutline.value = chapterNum
    try {
      ElMessage.info(`正在生成第 ${chapterNum} 章详细大纲...`)
      const res = await novelWriterApi.generateOutlineWithIntervention(projectId.value, chapterNum, {
        content_type: project.value?.content_type || 'novel',
        force_regenerate: forceRegenerate
      })
      if (res.success) {
        const status = res.data?.status
        if (status === 'need_intervention') {
          showInterventionDialog(chapterNum, res.data)
          return
        } else if (status === 'already_exists') {
          ElMessage.info(`第 ${chapterNum} 章已存在详细大纲，如需重新生成请点击强制重新生成`)
          return
        } else if (status === 'success' || status === 'completed') {
          ElMessage.success(`第 ${chapterNum} 章详细大纲生成成功`)
          await _loadProject.value(); await loadChapterOutlines()
        } else if (status === 'skipped') {
          ElMessage.info(`第 ${chapterNum} 章已跳过`)
        } else {
          ElMessage.error(res.data?.message || '生成失败')
        }
      } else {
        ElMessage.error(res.data?.error_message || res.data?.message || '生成失败')
      }
    } catch (error) {
      if (error?.cancelled) return
      console.error('生成章节大纲失败:', error)
      ElMessage.error(`第 ${chapterNum} 章详细大纲生成失败`)
    } finally {
      generatingSingleChapterOutline.value = null
    }
  }

  async function showChapterOutlineDetail(outline) {
    try {
      const res = await novelWriterApi.getChapterOutline(projectId.value, outline.chapter_number)
      if (res.success && res.data) {
        currentChapterOutlineDetail.value = {
          chapter_number: outline.chapter_number,
          chapter_title: outline.chapter_title || `第${outline.chapter_number}章`,
          raw_content: res.data.detailed_outline || '',
          revision_info: res.data.revision_info || null,
          original_content: res.data.original_content || null
        }
        chapterOutlineDetailVisible.value = true
      }
    } catch (error) {
      console.error('获取章节大纲详情失败', error)
      ElMessage.error('获取大纲详情失败')
    }
  }

  function showChapterOutlineRevisionCompare() {
    chapterOutlineOriginalContent.value = currentChapterOutlineDetail.value.original_content || ''
    chapterOutlineRevisedContent.value = currentChapterOutlineDetail.value.raw_content || ''
    chapterOutlineRevisionInfo.value = currentChapterOutlineDetail.value.revision_info || null
    chapterOutlineRevisionViewMode.value = 'diff'
    chapterOutlineRevisionCompareVisible.value = true
  }

  function startEditChapterOutline() {
    chapterOutlineEditContent.value = currentChapterOutlineDetail.value.raw_content
    chapterOutlineEditTitle.value = currentChapterOutlineDetail.value.chapter_title
    chapterOutlineEditMode.value = true
  }

  function cancelEditChapterOutline() {
    chapterOutlineEditMode.value = false
    chapterOutlineEditContent.value = ''
    chapterOutlineEditTitle.value = ''
  }

  async function saveChapterOutlineEdit() {
    if (!chapterOutlineEditContent.value.trim()) { ElMessage.warning('大纲内容不能为空'); return }
    savingChapterOutlineEdit.value = true
    try {
      const res = await novelWriterApi.updateChapterOutline(
        projectId.value, currentChapterOutlineDetail.value.chapter_number,
        { chapter_title: chapterOutlineEditTitle.value, detailed_outline: chapterOutlineEditContent.value }
      )
      if (res.success) {
        currentChapterOutlineDetail.value.chapter_title = chapterOutlineEditTitle.value
        currentChapterOutlineDetail.value.raw_content = chapterOutlineEditContent.value
        chapterOutlineEditMode.value = false
        await loadChapterOutlines()
        ElMessage.success('大纲已保存')
      }
    } catch (error) {
      console.error('保存章节大纲失败', error)
      ElMessage.error('保存失败')
    } finally {
      savingChapterOutlineEdit.value = false
    }
  }

  function downloadSingleChapterOutline() {
    const content = currentChapterOutlineDetail.value.raw_content
    if (!content) { ElMessage.warning('暂无内容可下载'); return }
    const chapterNum = currentChapterOutlineDetail.value.chapter_number
    const chapterTitle = currentChapterOutlineDetail.value.chapter_title
    downloadBlob(content, `${project.value?.title || '小说'}_第${chapterNum}章_${chapterTitle}.md`, 'text/markdown;charset=utf-8')
    ElMessage.success('下载成功')
  }

  async function downloadChapterOutline(outline) {
    try {
      const res = await novelWriterApi.getChapterOutline(projectId.value, outline.chapter_number)
      if (res.success && res.data?.detailed_outline) {
        downloadBlob(res.data.detailed_outline,
          `${project.value?.title || '小说'}_第${outline.chapter_number}章_${outline.chapter_title}.md`,
          'text/markdown;charset=utf-8')
        ElMessage.success('下载成功')
      } else { ElMessage.warning('暂无内容可下载') }
    } catch (error) { console.error('下载章节大纲失败', error); ElMessage.error('下载失败') }
  }

  async function downloadAllChapterOutlines() {
    const generatedOutlines = chapterOutlines.value.filter(c => c.has_detailed)
    if (generatedOutlines.length === 0) { ElMessage.warning('暂无已生成的大纲可下载'); return }
    try {
      const promises = generatedOutlines.map(o => novelWriterApi.getChapterOutline(projectId.value, o.chapter_number))
      const results = await Promise.all(promises)
      let mergedContent = `# ${project.value?.title || '小说'} - 章节详细大纲\n\n> 共 ${generatedOutlines.length} 章\n\n---\n\n`
      results.forEach((res, index) => {
        const outline = generatedOutlines[index]
        if (res.success && res.data?.detailed_outline) {
          mergedContent += `## 第${outline.chapter_number}章 ${outline.chapter_title}\n\n${res.data.detailed_outline}\n\n---\n\n`
        }
      })
      downloadBlob(mergedContent, `${project.value?.title || '小说'}_章节详细大纲_全章.md`, 'text/markdown;charset=utf-8')
      ElMessage.success(`已下载 ${generatedOutlines.length} 章大纲`)
    } catch (error) { console.error('下载全部章节大纲失败', error); ElMessage.error('下载失败') }
  }

  async function downloadAllChapterContent() {
    const generatedContents = chapterOutlines.value.filter(c => c.content_status === 'generated')
    if (generatedContents.length === 0) { ElMessage.warning('暂无已生成的正文可下载'); return }
    try {
      ElMessage.info('正在获取正文内容...')
      const res = await novelWriterApi.getAllChapterContent(projectId.value)
      if (!res.success || !res.data?.contents?.length) { ElMessage.warning('暂无正文内容可下载'); return }
      const contents = res.data.contents
      const projectTitle = res.data.project_title || '小说'
      let mergedContent = `# ${projectTitle} - 章节正文\n\n> 共 ${contents.length} 章\n\n---\n\n`
      contents.forEach(item => {
        mergedContent += `## 第${item.chapter_number}章 ${item.chapter_title}\n\n${item.content}\n\n---\n\n`
      })
      downloadBlob(mergedContent, `${projectTitle}_章节正文_全章.md`, 'text/markdown;charset=utf-8')
      ElMessage.success(`已下载 ${contents.length} 章正文`)
    } catch (error) { console.error('下载全部章节正文失败', error); ElMessage.error('下载失败') }
  }

  function startEditChapterOutlineTitle(outline) {
    editingChapterOutlineTitle.value = outline.chapter_number
    editChapterOutlineTitleValue.value = outline.chapter_title || ''
  }

  function cancelEditChapterOutlineTitle() {
    editingChapterOutlineTitle.value = null
    editChapterOutlineTitleValue.value = ''
  }

  async function saveChapterOutlineTitle(outline) {
    if (!editChapterOutlineTitleValue.value.trim()) { ElMessage.warning('标题不能为空'); return }
    if (editChapterOutlineTitleValue.value === outline.chapter_title) { editingChapterOutlineTitle.value = null; return }
    try {
      const res = await novelWriterApi.updateChapterOutline(
        projectId.value, outline.chapter_number,
        { chapter_title: editChapterOutlineTitleValue.value }
      )
      if (res.success) {
        outline.chapter_title = editChapterOutlineTitleValue.value
        editingChapterOutlineTitle.value = null
        ElMessage.success('章节标题已更新')
      }
    } catch (error) { console.error('更新章节标题失败', error); ElMessage.error('更新失败') }
  }

  async function handleDeleteChapterContent(outline) {
    try {
      await novelWriterApi.deleteChapterContent(projectId.value, outline.chapter_number)
      ElMessage.success(`第${outline.chapter_number}章正文已删除`)
      await loadChapterOutlines()
    } catch (error) { ElMessage.error('删除失败') }
  }

  async function handleDeleteChapterOutline(outline) {
    try {
      await novelWriterApi.deleteChapterOutline(projectId.value, outline.chapter_number)
      ElMessage.success(`第${outline.chapter_number}章大纲已删除`)
      await loadChapterOutlines()
    } catch (error) { ElMessage.error('删除失败') }
  }

  // ========================================================================
  //  场景大纲操作
  // ========================================================================
  async function loadSceneOutlines() {
    if (project.value?.content_type !== 'movie_script') return
    try {
      const res = await novelWriterApi.getSceneOutlines(projectId.value)
      if (res.success && res.data) {
        const scenes = res.data.scenes || []
        sceneOutlines.value = scenes.map(sc => ({
          scene_number: sc.scene_number,
          scene_title: sc.scene_title || sc.location || `第${sc.scene_number}场`,
          location: sc.location,
          has_detailed: sc.status === 'generated' || sc.status === 'edited',
          content_status: sc.content_status || null,
          content_word_count: sc.content_word_count || 0,
          ...sc
        }))
      }
    } catch (error) { console.error('加载场景大纲失败', error) }
  }

  async function handleGenerateAllSceneOutlines(sceneNumbers = null) {
    const totalSc = totalSceneOutlineCount.value
    if (totalSc === 0) { ElMessage.warning('请先设置场景数'); return }

    let pendingScenes
    if (sceneNumbers && Array.isArray(sceneNumbers)) {
      pendingScenes = sceneNumbers
    } else {
      const existingScenes = sceneOutlines.value.filter(sc => sc.has_detailed).map(sc => sc.scene_number)
      const allScenes = Array.from({ length: totalSc }, (_, i) => i + 1)
      pendingScenes = allScenes.filter(sc => !existingScenes.includes(sc))
    }

    if (pendingScenes.length === 0) { ElMessage.success('全部场景大纲已生成'); return }

    try {
      await ElMessageBox.confirm(
        pendingScenes.length !== totalSc
          ? `将生成第 ${Math.min(...pendingScenes)} 至第 ${Math.max(...pendingScenes)} 场，共 ${pendingScenes.length} 场。确定继续吗？`
          : `确定要生成全部 ${pendingScenes.length} 场的详细大纲吗？`,
        '确认生成', { type: 'info' }
      )

      _taskStore.value.setTask({
        project_id: projectId.value, task_type: 'scene_outline', status: 'running',
        total_count: pendingScenes.length, completed_count: 0
      })

      generatingSceneOutlines.value = true
      _abortController.value = new AbortController()
      _startTaskPolling.value()

      const res = await novelWriterApi.generateAllSceneOutlines(projectId.value, {
        scene_numbers: pendingScenes, stop_on_error: true
      }, _abortController.value.signal)

      _stopTaskPolling.value()

      if (res.success) {
        ElMessage.success(`场景大纲生成完成！成功 ${res.data.completed_count} 场，失败 ${res.data.failed_count} 场`)
        await _loadProject.value(); await loadSceneOutlines()
      }
    } catch (error) {
      _stopTaskPolling.value()
      if (error === 'cancel' || error?.cancelled) return
      console.error('生成场景大纲失败:', error)
      ElMessage.error('生成场景大纲失败')
    } finally {
      generatingSceneOutlines.value = false
      _abortController.value = null
      _taskStore.value.clearTask()
    }
  }

  async function handleGenerateSingleSceneOutline(sceneNum) {
    generatingSingleSceneOutline.value = sceneNum
    try {
      ElMessage.info(`正在生成第 ${sceneNum} 场详细大纲...`)
      const res = await novelWriterApi.generateOutlineWithIntervention(projectId.value, sceneNum, {
        content_type: 'movie_script'
      })
      if (res.success) {
        const status = res.data?.status
        if (status === 'need_intervention') {
          showInterventionDialog(sceneNum, res.data)
          return
        } else if (status === 'success' || status === 'completed') {
          ElMessage.success(`第 ${sceneNum} 场详细大纲生成成功`)
          await _loadProject.value(); await loadSceneOutlines()
        } else if (status === 'skipped') {
          ElMessage.info(`第 ${sceneNum} 场已跳过`)
        } else {
          ElMessage.error(res.data?.message || '生成失败')
        }
      } else {
        ElMessage.error(res.data?.error_message || res.data?.message || '生成失败')
      }
    } catch (error) {
      if (error?.cancelled) return
      console.error('生成场景大纲失败:', error)
      ElMessage.error(`第 ${sceneNum} 场详细大纲生成失败`)
    } finally {
      generatingSingleSceneOutline.value = null
    }
  }

  async function showSceneOutlineDetail(outline) {
    try {
      const res = await novelWriterApi.getSceneOutline(projectId.value, outline.scene_number)
      if (res.success && res.data) {
        currentSceneOutlineDetail.value = {
          scene_number: outline.scene_number,
          scene_title: outline.scene_title || `第${outline.scene_number}场`,
          raw_content: res.data.detailed_outline || ''
        }
        sceneOutlineDetailVisible.value = true
      }
    } catch (error) {
      console.error('获取场景大纲详情失败', error)
      ElMessage.error('获取大纲详情失败')
    }
  }

  function startEditSceneOutline() {
    sceneOutlineEditContent.value = currentSceneOutlineDetail.value.raw_content
    sceneOutlineEditTitle.value = currentSceneOutlineDetail.value.scene_title
    sceneOutlineEditMode.value = true
  }

  function cancelEditSceneOutline() {
    sceneOutlineEditMode.value = false
    sceneOutlineEditContent.value = ''
    sceneOutlineEditTitle.value = ''
  }

  async function saveSceneOutlineEdit() {
    if (!sceneOutlineEditContent.value.trim()) { ElMessage.warning('大纲内容不能为空'); return }
    savingSceneOutlineEdit.value = true
    try {
      const res = await novelWriterApi.updateSceneOutline(
        projectId.value, currentSceneOutlineDetail.value.scene_number,
        { scene_title: sceneOutlineEditTitle.value, detailed_outline: sceneOutlineEditContent.value }
      )
      if (res.success) {
        currentSceneOutlineDetail.value.scene_title = sceneOutlineEditTitle.value
        currentSceneOutlineDetail.value.raw_content = sceneOutlineEditContent.value
        sceneOutlineEditMode.value = false
        await loadSceneOutlines()
        ElMessage.success('大纲已保存')
      }
    } catch (error) {
      console.error('保存场景大纲失败', error)
      ElMessage.error('保存失败')
    } finally {
      savingSceneOutlineEdit.value = false
    }
  }

  function downloadSingleSceneOutline() {
    const content = currentSceneOutlineDetail.value.raw_content
    if (!content) { ElMessage.warning('暂无内容可下载'); return }
    const sceneNum = currentSceneOutlineDetail.value.scene_number
    const sceneTitle = currentSceneOutlineDetail.value.scene_title
    downloadBlob(content, `${project.value?.title || '电影剧本'}_第${sceneNum}场_${sceneTitle}.md`, 'text/markdown;charset=utf-8')
    ElMessage.success('下载成功')
  }

  async function downloadSceneOutline(outline) {
    try {
      const res = await novelWriterApi.getSceneOutline(projectId.value, outline.scene_number)
      if (res.success && res.data?.detailed_outline) {
        downloadBlob(res.data.detailed_outline,
          `${project.value?.title || '电影剧本'}_第${outline.scene_number}场_${outline.scene_title}.md`,
          'text/markdown;charset=utf-8')
        ElMessage.success('下载成功')
      } else { ElMessage.warning('暂无内容可下载') }
    } catch (error) { console.error('下载场景大纲失败', error); ElMessage.error('下载失败') }
  }

  async function downloadAllSceneOutlines() {
    const generatedOutlines = sceneOutlines.value.filter(s => s.has_detailed)
    if (generatedOutlines.length === 0) { ElMessage.warning('暂无已生成的大纲可下载'); return }
    try {
      const promises = generatedOutlines.map(o => novelWriterApi.getSceneOutline(projectId.value, o.scene_number))
      const results = await Promise.all(promises)
      let mergedContent = `# ${project.value?.title || '电影剧本'} - 场景详细大纲\n\n> 共 ${generatedOutlines.length} 场\n\n---\n\n`
      results.forEach((res, index) => {
        const outline = generatedOutlines[index]
        if (res.success && res.data?.detailed_outline) {
          mergedContent += `## 第${outline.scene_number}场 ${outline.scene_title}\n\n${res.data.detailed_outline}\n\n---\n\n`
        }
      })
      downloadBlob(mergedContent, `${project.value?.title || '电影剧本'}_场景详细大纲_全场.md`, 'text/markdown;charset=utf-8')
      ElMessage.success(`已下载 ${generatedOutlines.length} 场大纲`)
    } catch (error) { console.error('下载全部场景大纲失败', error); ElMessage.error('下载失败') }
  }

  async function downloadAllSceneContent() {
    const generatedContents = sceneOutlines.value.filter(s => s.content_status === 'generated')
    if (generatedContents.length === 0) { ElMessage.warning('暂无已生成的正文可下载'); return }
    try {
      ElMessage.info('正在获取正文内容...')
      const res = await novelWriterApi.getAllScriptContent(projectId.value)
      if (!res?.success || !res?.data) { ElMessage.warning('暂无内容可下载'); return }

      const { project_title, contents, ai_resources, total_count } = res.data
      const safeTitle = (project_title || '电影剧本').replace(/[\\/:*?"<>|]/g, '_')

      // 文件1: 场景正文
      let scriptMd = `\uFEFF# ${project_title || '电影剧本'} - 场景正文\n\n> 共 ${contents?.length || 0} 场\n\n---\n\n`
      if (contents && contents.length > 0) {
        contents.forEach(item => {
          scriptMd += `## 第${item.unit_index}场 ${item.unit_title}\n\n${item.content}\n\n---\n\n`
        })
      } else {
        scriptMd += `*暂无正文内容*\n\n`
      }
      downloadBlob(scriptMd, `${safeTitle}_剧本正文_全集.md`, 'text/markdown;charset=utf-8')

      // 文件2: AI资源提示词
      let aiMd = `\uFEFF# ${project_title || '电影剧本'} - AI资源提示词\n\n> 共 ${total_count || 0} 场\n\n---\n\n`
      if (ai_resources && ai_resources.length > 0) {
        ai_resources.forEach(item => {
          aiMd += `## 第${item.unit_index}场 ${item.unit_title}\n\n${item.content}\n\n---\n\n`
        })
      } else {
        aiMd += `*暂无AI资源内容*\n\n`
      }
      setTimeout(() => {
        downloadBlob(aiMd, `${safeTitle}_AI资源提示词_全集.md`, 'text/markdown;charset=utf-8')
        ElMessage.success(`已下载 ${contents?.length || 0} 场正文 + AI资源`)
      }, 200)
    } catch (error) { console.error('下载全部场景正文失败', error); ElMessage.error('下载失败') }
  }

  function startEditSceneOutlineTitle(outline) {
    editingSceneOutlineTitle.value = outline.scene_number
    editSceneOutlineTitleValue.value = outline.scene_title || ''
  }

  function cancelEditSceneOutlineTitle() {
    editingSceneOutlineTitle.value = null
    editSceneOutlineTitleValue.value = ''
  }

  async function saveSceneOutlineTitle(outline) {
    if (!editSceneOutlineTitleValue.value.trim()) { ElMessage.warning('标题不能为空'); return }
    if (editSceneOutlineTitleValue.value === outline.scene_title) { editingSceneOutlineTitle.value = null; return }
    try {
      const res = await novelWriterApi.updateSceneOutline(
        projectId.value, outline.scene_number,
        { scene_title: editSceneOutlineTitleValue.value }
      )
      if (res.success) {
        outline.scene_title = editSceneOutlineTitleValue.value
        editingSceneOutlineTitle.value = null
        ElMessage.success('场景标题已更新')
      }
    } catch (error) { console.error('更新场景标题失败', error); ElMessage.error('更新失败') }
  }

  async function handleDeleteSceneContent(outline) {
    try {
      await novelWriterApi.deleteSceneContent(projectId.value, outline.scene_number)
      ElMessage.success(`第${outline.scene_number}场正文已删除`)
      await loadSceneOutlines()
    } catch (error) { ElMessage.error('删除失败') }
  }

  async function handleDeleteSceneOutline(outline) {
    try {
      await novelWriterApi.deleteSceneOutline(projectId.value, outline.scene_number)
      ElMessage.success(`第${outline.scene_number}场大纲已删除`)
      await loadSceneOutlines()
    } catch (error) { ElMessage.error('删除失败') }
  }

  // ========================================================================
  //  用户干预
  // ========================================================================
  function showInterventionDialog(unitNumber, data) {
    interventionData.value = {
      unit_number: unitNumber,
      content_type: project.value?.content_type || 'novel',
      inferred_summary: data.inferred_summary || '',
      reference_info: data.reference_info || null,
      message: data.message || '缺少原始概要，请选择处理方式'
    }
    interventionUserChoice.value = ''
    interventionUserGuidance.value = ''
    interventionDialogVisible.value = true
  }

  async function handleInterventionConfirm() {
    if (!interventionUserChoice.value) { ElMessage.warning('请选择处理方式'); return }
    if (interventionUserChoice.value === 'provide' && !interventionUserGuidance.value.trim()) {
      ElMessage.warning('请输入章节概要内容'); return
    }
    interventionLoading.value = true
    try {
      const res = await novelWriterApi.generateOutlineWithIntervention(
        projectId.value, interventionData.value.unit_number,
        {
          content_type: interventionData.value.content_type,
          user_choice: interventionUserChoice.value,
          user_guidance: interventionUserChoice.value === 'provide' ? interventionUserGuidance.value.trim() : null
        }
      )
      if (res.success) {
        const status = res.data?.status
        if (status === 'success' || status === 'completed') {
          ElMessage.success(`第 ${interventionData.value.unit_number} 单元详细大纲生成成功`)
          interventionDialogVisible.value = false
          await _loadProject.value(); await loadChapterOutlines()
        } else if (status === 'skipped') {
          ElMessage.info(`第 ${interventionData.value.unit_number} 单元已跳过`)
          interventionDialogVisible.value = false
          await loadChapterOutlines()
        } else if (status === 'show_reference') {
          interventionData.value.reference_info = { prev_unit: res.data.previous_unit, next_unit: res.data.next_unit }
          ElMessage.info('已获取相邻章节信息，请参考后选择处理方式')
        } else if (status === 'need_guidance') {
          ElMessage.warning('请输入章节概要内容')
        } else {
          ElMessage.error(res.data?.message || '处理失败')
        }
      } else {
        ElMessage.error(res.data?.message || '处理失败')
      }
    } catch (error) {
      console.error('干预处理失败:', error)
      ElMessage.error('处理失败')
    } finally {
      interventionLoading.value = false
    }
  }

  function handleInterventionCancel() {
    interventionDialogVisible.value = false
    generatingSingleChapterOutline.value = null
  }

  return {
    // 初始化
    initProject,
    // 分集
    episodeOutlines, generatingEpisodeOutlines, generatingSingleEpisode,
    outlineDetailVisible, currentOutlineDetail,
    outlineEditMode, outlineEditContent, outlineEditTitle,
    savingOutlineEdit, editingEpisodeTitle, editEpisodeTitleValue,
    loadEpisodeOutlines, handleGenerateAllEpisodeOutlines,
    handleGenerateSingleEpisodeOutline, showEpisodeOutlineDetail,
    startEditOutline, cancelEditOutline, saveOutlineEdit,
    downloadSingleEpisodeOutline, downloadEpisodeOutline,
    downloadAllEpisodeOutlines, downloadAllEpisodeContent,
    startEditEpisodeTitle, cancelEditEpisodeTitle, saveEpisodeTitle,
    handleDeleteEpisodeContent, handleDeleteEpisodeOutline,
    // 章节
    chapterOutlines, generatingChapterOutlines, generatingSingleChapterOutline,
    chapterOutlineDetailVisible, currentChapterOutlineDetail,
    chapterOutlineRevisionCompareVisible, chapterOutlineOriginalContent,
    chapterOutlineRevisedContent, chapterOutlineRevisionInfo,
    chapterOutlineRevisionViewMode,
    chapterOutlineEditMode, chapterOutlineEditContent, chapterOutlineEditTitle,
    savingChapterOutlineEdit, editingChapterOutlineTitle, editChapterOutlineTitleValue,
    loadChapterOutlines, handleGenerateAllChapterOutlines,
    handleGenerateSingleChapterOutline,
    showChapterOutlineDetail, showChapterOutlineRevisionCompare,
    startEditChapterOutline, cancelEditChapterOutline, saveChapterOutlineEdit,
    downloadSingleChapterOutline, downloadChapterOutline,
    downloadAllChapterOutlines, downloadAllChapterContent,
    startEditChapterOutlineTitle, cancelEditChapterOutlineTitle,
    saveChapterOutlineTitle,
    handleDeleteChapterContent, handleDeleteChapterOutline,
    // 场景
    sceneOutlines, generatingSceneOutlines, generatingSingleSceneOutline,
    sceneOutlineDetailVisible, currentSceneOutlineDetail,
    sceneOutlineEditMode, sceneOutlineEditContent, sceneOutlineEditTitle,
    savingSceneOutlineEdit, editingSceneOutlineTitle, editSceneOutlineTitleValue,
    loadSceneOutlines, handleGenerateAllSceneOutlines,
    handleGenerateSingleSceneOutline, showSceneOutlineDetail,
    startEditSceneOutline, cancelEditSceneOutline, saveSceneOutlineEdit,
    downloadSingleSceneOutline, downloadSceneOutline,
    downloadAllSceneOutlines, downloadAllSceneContent,
    startEditSceneOutlineTitle, cancelEditSceneOutlineTitle,
    saveSceneOutlineTitle,
    handleDeleteSceneContent, handleDeleteSceneOutline,
    // 干预
    interventionDialogVisible, interventionData, interventionLoading,
    interventionUserChoice, interventionUserGuidance, interventionOptions,
    showInterventionDialog, handleInterventionConfirm, handleInterventionCancel,
    // 计算属性
    totalEpisodeCount, totalChapterOutlineCount, totalSceneOutlineCount,
    generatedEpisodeCount, generatedChapterOutlineCount, generatedSceneOutlineCount,
    generatedEpisodeContentCount, generatedChapterContentCount, generatedSceneContentCount,
    unitLabel,
    // 辅助
    downloadBlob
  }
})
