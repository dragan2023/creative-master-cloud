/**
 * useStyleManagement - 文风管理
 * 从 WritingWorkbench.vue 中提取的文风选择与风格文档管理逻辑
 * 支持：小说文风、剧集风格、电影风格
 */
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { novelWriterApi } from '@/api/novel-writer'
import { getAuthHeaders } from '@/utils/authStorage'

export function useStyleManagement(projectId, projectData) {
  // ==================== 状态 ====================
  const showModelConfigDialog = ref(false)
  const styleDocumentInfo = ref(null)
  const showStyleDocumentDetail = ref(false)
  const aiEliminationEnabled = ref(true)
  const aiEliminationThreshold = ref(50)

  // 小说文风选择器状态
  const showStyleSelector = ref(false)
  const selectedStyleIds = ref([])
  const selectedStyleNames = ref([])
  const styleIntensity = ref(0.7)
  const styleGuide = ref({})

  // 剧集/电影风格选择器状态（多维风格）
  const showScriptStyleSelector = ref(false)
  const scriptStyleData = ref({
    styleType: '',       // 'movie' | 'series'
    seriesSubType: 'long',
    dimensions: {},
    selectedNames: [],
    intensity: 0.7
  })

  // 当前内容类型
  // [修复] 使用独立的 _contentType ref 而非依赖外部传入的 ref(null) projectData
  // 在 restoreStyleConfigFromProject 中动态更新，确保 saveStyleConfig 分支正确
  const _contentType = ref('novel')

  const currentContentType = computed(() => {
    return _contentType.value || projectData?.value?.content_type || projectData?.content_type || 'novel'
  })

  // 是否为剧本类型
  const isScriptType = computed(() => {
    return currentContentType.value === 'series_script' || currentContentType.value === 'movie_script'
  })

  // 已选风格数量（兼容两种模式）
  const selectedStyleCount = computed(() => {
    if (isScriptType.value) {
      return scriptStyleData.value.selectedNames?.length || 0
    }
    return selectedStyleIds.value.length
  })

  // 风格文档上传地址
  const styleUploadAction = computed(() => {
    return `${import.meta.env.VITE_API_BASE_URL || ''}/api/v1/novel-writer/projects/${projectId.value}/style-document`
  })

  // 上传请求头（通过集中化存储层）
  const uploadHeaders = computed(() => getAuthHeaders())

  // ==================== 方法 ====================

  // 保存文风配置到项目
  async function saveStyleConfig() {
    if (!projectId.value) return
    try {
      if (isScriptType.value) {
        // 保存剧本风格配置
        const configKey = currentContentType.value === 'movie_script' ? 'movie_script_config' : 'series_script_config'
        const styleConfig = {
          script_style_dimensions: scriptStyleData.value.dimensions || {},
          script_style_names: scriptStyleData.value.selectedNames || [],
          script_style_intensity: scriptStyleData.value.intensity || 0.7,
          script_style_type: scriptStyleData.value.styleType || '',
          script_series_sub_type: scriptStyleData.value.seriesSubType || 'long'
        }
        await novelWriterApi.updateProject(projectId.value, {
          [configKey]: {
            style_selector_config: styleConfig
          }
        })
        console.log('[StyleMgmt] 剧本风格配置已保存:', styleConfig)
      } else {
        // 保存小说文风配置
        const styleLibraryConfig = {
          selected_style_ids: selectedStyleIds.value,
          selected_style_names: selectedStyleNames.value,
          style_intensity: styleIntensity.value,
          style_guide: styleGuide.value
        }
        await novelWriterApi.updateProject(projectId.value, {
          novel_config: {
            style_library_config: styleLibraryConfig
          }
        })
        console.log('[StyleMgmt] 文风配置已保存:', styleLibraryConfig)
      }
    } catch (error) {
      console.error('[StyleMgmt] 保存配置失败:', error)
    }
  }

  // 处理文风选择确认（小说）
  function handleStyleSelectionConfirm(data) {
    selectedStyleIds.value = data.styleIds || []
    selectedStyleNames.value = data.styleNames || []
    styleIntensity.value = data.intensity || 0.7
    styleGuide.value = data.styleGuide || {}
    
    ElMessage.success(`已选择 ${selectedStyleNames.value.length} 种文风: ${selectedStyleNames.value.join(' + ')}`)
    
    // 保存文风配置到后端
    saveStyleConfig()
    
    console.log('文风配置:', {
      styleIds: selectedStyleIds.value,
      styleNames: selectedStyleNames.value,
      intensity: styleIntensity.value,
      styleGuide: styleGuide.value
    })
  }

  // 处理剧本风格选择确认（电影/剧集）
  function handleScriptStyleConfirm(data) {
    scriptStyleData.value = {
      styleType: data.styleType || '',
      seriesSubType: data.seriesSubType || 'long',
      dimensions: data.dimensions || {},
      selectedNames: data.selectedNames || [],
      intensity: data.intensity || 0.7
    }
    
    const label = data.styleType === 'movie' ? '电影' : '剧集'
    ElMessage.success(`已选择 ${scriptStyleData.value.selectedNames.length} 个维度的${label}风格: ${scriptStyleData.value.selectedNames.join('、')}`)
    
    // 保存配置到后端
    saveStyleConfig()
    
    console.log('[StyleMgmt] 剧本风格配置:', scriptStyleData.value)
  }

  // 移除已选文风
  function removeSelectedStyle(index) {
    selectedStyleIds.value.splice(index, 1)
    selectedStyleNames.value.splice(index, 1)
    if (selectedStyleIds.value.length === 0) {
      ElMessage.info('已清空文风选择')
    }
    // 保存更改
    saveStyleConfig()
  }

  // 移除已选剧本风格维度
  function removeScriptStyle(dimName) {
    const dims = scriptStyleData.value.dimensions || {}
    if (dims[dimName]) {
      delete dims[dimName]
      scriptStyleData.value.dimensions = { ...dims }
    }
    // 更新 selectedNames
    scriptStyleData.value.selectedNames = scriptStyleData.value.selectedNames.filter(
      name => !name.startsWith(dimName + ':')
    )
    if (Object.keys(dims).length === 0) {
      ElMessage.info('已清空剧本风格选择')
    }
    // 保存更改
    saveStyleConfig()
  }

  // 从项目数据恢复文风配置
  function restoreStyleConfigFromProject(data) {
    // 优先使用传入的 data 参数，其次使用 projectData.value
    const projectDataValue = data || projectData?.value
    if (!projectDataValue) return

    const contentType = projectDataValue.content_type

    // [修复] 同步更新 _contentType，确保 saveStyleConfig 等依赖 currentContentType 的逻辑正确
    if (contentType) {
      _contentType.value = contentType
    }

    // ==================== 恢复 AI文风消除 配置 ====================
    // 从项目数据中恢复 ai_elimination_enabled 和 ai_elimination_threshold
    // 注意：后端 getProject() 现在返回这两个字段（后端 schema 已添加）
    if (projectDataValue.ai_elimination_enabled !== undefined && projectDataValue.ai_elimination_enabled !== null) {
      aiEliminationEnabled.value = projectDataValue.ai_elimination_enabled
    }
    if (projectDataValue.ai_elimination_threshold !== undefined && projectDataValue.ai_elimination_threshold !== null) {
      aiEliminationThreshold.value = projectDataValue.ai_elimination_threshold
    }
    console.log('[StyleMgmt] 从项目恢复AI文风消除配置:', {
      enabled: aiEliminationEnabled.value,
      threshold: aiEliminationThreshold.value
    })

    if (contentType === 'movie_script' || contentType === 'series_script') {
      // 恢复剧本风格配置
      const configKey = contentType === 'movie_script' ? 'movie_script_config' : 'series_script_config'
      const config = projectDataValue[configKey]?.style_selector_config
      if (config) {
        scriptStyleData.value = {
          styleType: config.script_style_type || '',
          seriesSubType: config.script_series_sub_type || 'long',
          dimensions: config.script_style_dimensions || {},
          selectedNames: config.script_style_names || [],
          intensity: config.script_style_intensity || 0.7
        }
        console.log('[StyleMgmt] 从项目恢复剧本风格配置:', scriptStyleData.value)
      }
    } else {
      // 恢复小说文风配置
      const novelConfig = projectDataValue.novel_config
      if (!novelConfig?.style_library_config) return

      const config = novelConfig.style_library_config
      selectedStyleIds.value = config.selected_style_ids || []
      selectedStyleNames.value = config.selected_style_names || []
      styleIntensity.value = config.style_intensity ?? 0.7
      styleGuide.value = config.style_guide || {}

      console.log('[StyleMgmt] 从项目恢复文风配置:', {
        styleIds: selectedStyleIds.value,
        intensity: styleIntensity.value
      })
    }
  }

  // 监听 projectData 变化，自动恢复配置
  watch(() => projectData?.value, () => {
    restoreStyleConfigFromProject()
  }, { immediate: true })

  // 加载风格文档信息
  async function loadStyleDocumentInfo() {
    if (!projectId.value) return
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

  // 刷新风格文档信息
  async function handleRefreshStyleDocument() {
    await loadStyleDocumentInfo()
    ElMessage.success('风格文档数据已刷新')
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
    try {
      await ElMessageBox.confirm(
        '确定要删除风格文档吗？删除后AI将无法模仿该文档的写作风格。',
        '确认删除',
        { confirmButtonText: '确定', cancelButtonText: '取消', type: 'warning' }
      )
      const res = await novelWriterApi.deleteStyleDocument(projectId.value)
      if (res.success) {
        ElMessage.success('风格文档已删除')
        styleDocumentInfo.value = null
      } else {
        ElMessage.error(res.message || '删除失败')
      }
    } catch (error) {
      if (error !== 'cancel') {
        ElMessage.error('删除失败')
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

  return {
    // 状态
    showModelConfigDialog,
    styleDocumentInfo,
    showStyleDocumentDetail,
    aiEliminationEnabled,
    aiEliminationThreshold,
    // 小说文风
    showStyleSelector,
    selectedStyleIds,
    selectedStyleNames,
    styleIntensity,
    styleGuide,
    // 剧本风格
    showScriptStyleSelector,
    scriptStyleData,
    isScriptType,
    selectedStyleCount,
    currentContentType,
    // 上传
    styleUploadAction,
    uploadHeaders,
    // 方法
    handleStyleSelectionConfirm,
    handleScriptStyleConfirm,
    removeSelectedStyle,
    removeScriptStyle,
    loadStyleDocumentInfo,
    handleRefreshStyleDocument,
    handleStyleUploadSuccess,
    handleStyleUploadError,
    handleDeleteStyleDocument,
    handleAiEliminationChange,
    handleThresholdChange,
    restoreStyleConfigFromProject
  }
}
