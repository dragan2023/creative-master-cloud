/**
 * useOutlineManagement - 向后兼容适配器
 *
 * 所有逻辑已迁移到 Pinia store: @/stores/outline.js
 * 此文件仅作为桥接层，委托给 useOutlineStore，
 * 避免一次性修改所有调用方。
 *
 * 迁移时间: 2026-04-26
 * 原始行数: 985行 (30+参数)
 * 重构后: 适配器模式，ProjectDetail.vue 无需修改
 */
import { useOutlineStore } from '@/stores/outline'

export function useOutlineManagement(options) {
  const store = useOutlineStore()

  // 初始化 store 的外部依赖
  const {
    projectId, project, taskStore, abortController,
    loadProject, loadChapters,
    startTaskPolling, stopTaskPolling
  } = options

  store.initProject({
    projectId,
    project,
    taskStore,
    abortController,
    loadProject,
    loadChapters,
    startTaskPolling,
    stopTaskPolling
  })

  // 返回与原始 useOutlineManagement 完全一致的接口
  return {
    // Episode
    loadEpisodeOutlines: () => store.loadEpisodeOutlines(),
    handleGenerateAllEpisodeOutlines: (...args) => store.handleGenerateAllEpisodeOutlines(...args),
    handleGenerateSingleEpisodeOutline: (...args) => store.handleGenerateSingleEpisodeOutline(...args),
    showEpisodeOutlineDetail: (...args) => store.showEpisodeOutlineDetail(...args),
    startEditOutline: () => store.startEditOutline(),
    cancelEditOutline: () => store.cancelEditOutline(),
    saveOutlineEdit: () => store.saveOutlineEdit(),
    downloadSingleEpisodeOutline: () => store.downloadSingleEpisodeOutline(),
    downloadEpisodeOutline: (...args) => store.downloadEpisodeOutline(...args),
    downloadAllEpisodeOutlines: () => store.downloadAllEpisodeOutlines(),
    downloadAllEpisodeContent: () => store.downloadAllEpisodeContent(),
    startEditEpisodeTitle: (...args) => store.startEditEpisodeTitle(...args),
    cancelEditEpisodeTitle: () => store.cancelEditEpisodeTitle(),
    saveEpisodeTitle: (...args) => store.saveEpisodeTitle(...args),
    handleDeleteEpisodeContent: (...args) => store.handleDeleteEpisodeContent(...args),
    handleDeleteEpisodeOutline: (...args) => store.handleDeleteEpisodeOutline(...args),
    // Chapter
    loadChapterOutlines: () => store.loadChapterOutlines(),
    handleGenerateAllChapterOutlines: (...args) => store.handleGenerateAllChapterOutlines(...args),
    handleGenerateSingleChapterOutline: (...args) => store.handleGenerateSingleChapterOutline(...args),
    showInterventionDialog: (...args) => store.showInterventionDialog(...args),
    handleInterventionConfirm: () => store.handleInterventionConfirm(),
    handleInterventionCancel: () => store.handleInterventionCancel(),
    showChapterOutlineDetail: (...args) => store.showChapterOutlineDetail(...args),
    showChapterOutlineRevisionCompare: () => store.showChapterOutlineRevisionCompare(),
    startEditChapterOutline: () => store.startEditChapterOutline(),
    cancelEditChapterOutline: () => store.cancelEditChapterOutline(),
    saveChapterOutlineEdit: () => store.saveChapterOutlineEdit(),
    downloadSingleChapterOutline: () => store.downloadSingleChapterOutline(),
    downloadChapterOutline: (...args) => store.downloadChapterOutline(...args),
    downloadAllChapterOutlines: () => store.downloadAllChapterOutlines(),
    downloadAllChapterContent: () => store.downloadAllChapterContent(),
    startEditChapterOutlineTitle: (...args) => store.startEditChapterOutlineTitle(...args),
    cancelEditChapterOutlineTitle: () => store.cancelEditChapterOutlineTitle(),
    saveChapterOutlineTitle: (...args) => store.saveChapterOutlineTitle(...args),
    handleDeleteChapterContent: (...args) => store.handleDeleteChapterContent(...args),
    handleDeleteChapterOutline: (...args) => store.handleDeleteChapterOutline(...args),
    // Scene
    loadSceneOutlines: () => store.loadSceneOutlines(),
    handleGenerateAllSceneOutlines: (...args) => store.handleGenerateAllSceneOutlines(...args),
    handleGenerateSingleSceneOutline: (...args) => store.handleGenerateSingleSceneOutline(...args),
    showSceneOutlineDetail: (...args) => store.showSceneOutlineDetail(...args),
    startEditSceneOutline: () => store.startEditSceneOutline(),
    cancelEditSceneOutline: () => store.cancelEditSceneOutline(),
    saveSceneOutlineEdit: () => store.saveSceneOutlineEdit(),
    downloadSingleSceneOutline: () => store.downloadSingleSceneOutline(),
    downloadSceneOutline: (...args) => store.downloadSceneOutline(...args),
    downloadAllSceneOutlines: () => store.downloadAllSceneOutlines(),
    downloadAllSceneContent: () => store.downloadAllSceneContent(),
    startEditSceneOutlineTitle: (...args) => store.startEditSceneOutlineTitle(...args),
    cancelEditSceneOutlineTitle: () => store.cancelEditSceneOutlineTitle(),
    saveSceneOutlineTitle: (...args) => store.saveSceneOutlineTitle(...args),
    handleDeleteSceneContent: (...args) => store.handleDeleteSceneContent(...args),
    handleDeleteSceneOutline: (...args) => store.handleDeleteSceneOutline(...args),
    // Helper
    downloadBlob: (...args) => store.downloadBlob(...args)
  }
}
    } catch (error) { ElMessage.error('删除失败') }
  }

  async function handleDeleteSceneOutline(outline) {
    try {
      await novelWriterApi.deleteSceneOutline(projectId.value, outline.scene_number)
      ElMessage.success(`第${outline.scene_number}场大纲已删除`)
      await loadSceneOutlines()
    } catch (error) { ElMessage.error('删除失败') }
  }

  // 辅助: 下载Blob
  function downloadBlob(content, fileName, mimeType) {
    const blob = new Blob([content], { type: mimeType })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url; a.download = fileName; a.click()
    URL.revokeObjectURL(url)
  }

  return {
    // Episode
    loadEpisodeOutlines, handleGenerateAllEpisodeOutlines,
    handleGenerateSingleEpisodeOutline, showEpisodeOutlineDetail,
    startEditOutline, cancelEditOutline, saveOutlineEdit,
    downloadSingleEpisodeOutline, downloadEpisodeOutline,
    downloadAllEpisodeOutlines, downloadAllEpisodeContent,
    startEditEpisodeTitle, cancelEditEpisodeTitle, saveEpisodeTitle,
    handleDeleteEpisodeContent, handleDeleteEpisodeOutline,
    // Chapter
    loadChapterOutlines, handleGenerateAllChapterOutlines,
    handleGenerateSingleChapterOutline, showInterventionDialog,
    handleInterventionConfirm, handleInterventionCancel,
    showChapterOutlineDetail, showChapterOutlineRevisionCompare,
    startEditChapterOutline, cancelEditChapterOutline, saveChapterOutlineEdit,
    downloadSingleChapterOutline, downloadChapterOutline,
    downloadAllChapterOutlines, downloadAllChapterContent: downloadAllChapterContentFn,
    startEditChapterOutlineTitle, cancelEditChapterOutlineTitle, saveChapterOutlineTitle,
    handleDeleteChapterContent, handleDeleteChapterOutline,
    // Scene
    loadSceneOutlines, handleGenerateAllSceneOutlines,
    handleGenerateSingleSceneOutline, showSceneOutlineDetail,
    startEditSceneOutline, cancelEditSceneOutline, saveSceneOutlineEdit,
    downloadSingleSceneOutline, downloadSceneOutline,
    downloadAllSceneOutlines, downloadAllSceneContent: downloadAllSceneContentFn,
    startEditSceneOutlineTitle, cancelEditSceneOutlineTitle, saveSceneOutlineTitle,
    handleDeleteSceneContent, handleDeleteSceneOutline,
    // Helper
    downloadBlob
  }
}
