/**
 * 流式处理逻辑 composable
 * 管理 EventSource 连接、流式生成状态和两阶段大纲生成
 */
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { generateApi } from '@/api'
import { API_BASE_URL } from '@/config'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

export function useStreamHandler(type, form, globalOutlineContent, generatedContent, workflowSteps, handleWorkflowEvent, currentEventSource, titleStyleData = { styleId: '', styleName: '' }) {
  // 生成状态
  const generating = ref(false)
  const showResult = ref(false)
  const currentGenerationId = ref(null)
  const generationDuration = ref(null)
  const currentSessionId = ref(null)

  // 两阶段大纲生成状态
  const outlineStage = ref(0)
  const globalOutlineGenerating = ref(false)
  const unitSummaries = ref({})
  const unitSummariesGenerating = ref(false)

  // 逻辑检测状态
  const logicChecking = ref(false)
  const logicCheckResult = ref(null)
  const showLogicIssuesDialog = ref(false)

  // 修正详情对话框状态
  const showRevisionDetailDialog = ref(false)
  const currentRevisionUnit = ref(null)
  const revisionViewMode = ref('diff')

  // 编辑状态
  const editingUnitNumber = ref(null)
  const editingUnitContent = ref('')
  const editingGlobalOutline = ref(false)
  const editingGlobalOutlineContent = ref('')

  // 灵活介入流程状态
  const showImportDialog = ref(false)
  const importType = ref('global')
  const importContent = ref('')
  const startFromUnit = ref(1)
  const showStartUnitDialog = ref(false)

  // 是否使用两阶段生成模式
  const useTwoStageMode = computed(() => type.value === 'novel' || type.value === 'movie-outline' || type.value === 'series-outline')

  // 渲染全局大纲
  const renderedGlobalOutline = computed(() => {
    if (!globalOutlineContent.value) return ''
    return DOMPurify.sanitize(marked(globalOutlineContent.value))
  })

  // 开始编辑全局大纲
  const startEditGlobalOutline = () => {
    editingGlobalOutlineContent.value = globalOutlineContent.value
    editingGlobalOutline.value = true
  }

  // 保存全局大纲编辑
  const saveGlobalOutlineEdit = () => {
    globalOutlineContent.value = editingGlobalOutlineContent.value
    editingGlobalOutline.value = false
    ElMessage.success('全局大纲已修改')
  }

  // 取消编辑全局大纲
  const cancelEditGlobalOutline = () => {
    editingGlobalOutline.value = false
    editingGlobalOutlineContent.value = ''
  }

  // 构建大纲输入参数
  const buildOutlineInputParams = () => {
    if (type.value === 'novel') {
      const lengthMap = { 'short': '短篇', 'medium': '中篇', 'long': '长篇' }
      return {
        title: form.value.title || '',
        length: lengthMap[form.value.length] || '中篇',
        genre: Array.isArray(form.value.genre) ? form.value.genre.join('、') : (form.value.genre || '言情'),
        target_platform: form.value.target_platform || '起点',
        tone: form.value.tone || '正剧',
        synopsis: form.value.description,
        theme: form.value.theme || '',
        unique_selling_point: form.value.unique_selling_point || '',
        chapter_count: form.value.chapter_count || '50',
        custom_outline: form.value.custom_outline || ''
      }
    }
    return {}
  }

  // 从内容中解析单元概述
  const parseUnitSummariesFromContent = (content) => {
    const result = {}
    const isMovie = content.includes('场') && !content.includes('集')
    
    const pattern = isMovie
      ? /\*\*第(\d+)场[：:]\s*(.+?)(?:\n|$)/g
      : /###\s*第(\d+)(?:章|集)[：:]\s*(.+?)(?:\n|$)/g
    
    let match
    while ((match = pattern.exec(content)) !== null) {
      const unitNum = parseInt(match[1])
      const title = match[2].trim()
      
      const summaryPattern = isMovie
        ? new RegExp(`\\*\\*本场梗概\\*\\*[：:]\\s*(.+?)(?:\\n\\n|\\n\\*\\*|$)`, 's')
        : new RegExp(`\\*\\*本(?:章|集)梗概\\*\\*[：:]\\s*(.+?)(?:\\n\\n|\\n\\*\\*|$)`, 's')
      
      const summaryMatch = content.slice(match.index, match.index + 500).match(summaryPattern)
      const summary = summaryMatch ? summaryMatch[1].trim() : ''
      
      result[unitNum.toString()] = {
        unit_number: unitNum,
        title: title,
        summary: summary,
        status: 'completed'
      }
    }
    
    return result
  }

  // 开始两阶段生成（第一阶段：全局大纲）
  const handleTwoStageGenerate = async (apiKeyStore, router, kbParams = {}) => {
    // API Key 检查逻辑需要在主组件中处理
    const workflowComplete = ref(false)
    
    // 重置工作流程状态
    workflowSteps.value = [
      { step: 'model', status: 'running', message: '正在加载AI模型...', icon: 'Cpu' }
    ]
    workflowComplete.value = false
    
    // 开始第一阶段
    outlineStage.value = 1
    globalOutlineGenerating.value = true
    globalOutlineContent.value = ''
    showResult.value = true
    generatedContent.value = ''
    
    try {
      const inputParams = buildOutlineInputParams()
      
      setTimeout(() => {
        if (globalOutlineGenerating.value) {
          const modelIndex = workflowSteps.value.findIndex(s => s.step === 'model')
          if (modelIndex >= 0) {
            workflowSteps.value[modelIndex] = { step: 'model', status: 'done', message: '已加载模型', icon: 'Cpu' }
          }
          workflowSteps.value.push({ step: 'prompt', status: 'running', message: '正在准备提示词...', icon: 'Document' })
        }
      }, 500)
      
      setTimeout(() => {
        if (globalOutlineGenerating.value) {
          const promptIndex = workflowSteps.value.findIndex(s => s.step === 'prompt')
          if (promptIndex >= 0) {
            workflowSteps.value[promptIndex] = { step: 'prompt', status: 'done', message: '提示词准备完成', icon: 'Document' }
          }
        }
      }, 1000)
      
      // 获取知识库参数（默认enable_knowledge为false，由用户主动控制）
      const enableKnowledge = kbParams.enableKnowledge || false
      
      // 获取自动质控参数（默认false，由用户主动控制）
      const enableAutoQC = kbParams.enableAutoQC || false
      
      const result = await generateApi.generateGlobalOutlineStream(
        {
          content_type: type.value,
          input_params: inputParams,
          provider: null,
          model: null,
          temperature: 0.7,
          enable_knowledge: enableKnowledge,  // 传递用户选择的知识库修正选项
          enable_auto_qc: enableAutoQC  // 传递用户选择的自动质控选项
        },
        (chunk, fullContent) => {
          globalOutlineContent.value = fullContent
          generatedContent.value = fullContent
        },
        (abortController) => {
          currentEventSource.value = abortController
        },
        (event) => {
          handleWorkflowEvent(event)
        },
        (newContent, message) => {
          globalOutlineContent.value = newContent
          generatedContent.value = newContent
          ElMessage.success(message || '内容已优化')
        }
      )
      
      if (result && !result.cancelled) {
        const generateIndex = workflowSteps.value.findIndex(s => s.step === 'generate')
        if (generateIndex >= 0) {
          workflowSteps.value[generateIndex] = { step: 'generate', status: 'done', message: '全局大纲生成完成', icon: 'MagicStick' }
        }
        workflowComplete.value = true
        
        outlineStage.value = 2
        ElMessage.success('全局大纲生成完成，请审核后继续生成单元概述')
      }
    } catch (error) {
      console.error('全局大纲生成失败:', error)
      const runningStep = workflowSteps.value.find(s => s.status === 'running')
      if (runningStep) {
        runningStep.status = 'error'
        runningStep.message = '生成失败: ' + (error.message || '未知错误')
      }
      ElMessage.error('全局大纲生成失败：' + (error.message || '未知错误'))
      outlineStage.value = 0
    } finally {
      globalOutlineGenerating.value = false
    }
    
    return workflowComplete.value
  }

  // 从全局大纲中解析章节数（辅助函数）
  const parseChapterCountFromOutline = (outlineContent) => {
    if (!outlineContent) return null
    
    const patterns = [
      /共(\d+)章/,
      /总计(\d+)章/,
      /(\d+)章.*全书/,
      /全书.*?(\d+)章/,
      /章节总数[：:]\s*(\d+)/,
      /总章节数[：:]\s*(\d+)/,
    ]
    
    for (const pattern of patterns) {
      const match = outlineContent.match(pattern)
      if (match) {
        const count = parseInt(match[1])
        if (count > 0 && count <= 1000) {
          return count
        }
      }
    }
    
    // 尝试找最大的章节号
    const chapterPattern = /第(\d+)章/g
    let maxChapter = 0
    let match
    while ((match = chapterPattern.exec(outlineContent)) !== null) {
      const chapterNum = parseInt(match[1])
      if (chapterNum > maxChapter) {
        maxChapter = chapterNum
      }
    }
    
    return maxChapter > 0 ? maxChapter : null
  }

  // 开始第二阶段：生成单元概述
  const handleGenerateUnitSummaries = async () => {
    if (!globalOutlineContent.value) {
      ElMessage.warning('请先生成全局大纲')
      return
    }
    
    // 智能获取章节数：优先使用表单值，其次从全局大纲中解析
    const formChapterCount = type.value === 'novel' 
      ? parseInt(form.value.chapter_count) || null
      : parseInt(form.value.episode_count) || null
    
    const outlineChapterCount = formChapterCount ? null : parseChapterCountFromOutline(globalOutlineContent.value)
    
    // 默认值：表单未填写且大纲未解析到时使用默认值
    const unitCount = formChapterCount || outlineChapterCount || (type.value === 'novel' ? 50 : 24)
    
    console.log(`[useStreamHandler] 章节数计算: 表单=${formChapterCount || '未填写'}, 大纲=${outlineChapterCount || '未找到'}, 最终=${unitCount}`)
    
    currentSessionId.value = `unit_summaries_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    
    outlineStage.value = 3
    unitSummariesGenerating.value = true
    unitSummaries.value = {}
    
    try {
      const result = await generateApi.generateUnitSummariesStream(
        {
          content_type: type.value,
          global_outline: globalOutlineContent.value,
          unit_count: unitCount,
          series_type: null,
          episode_duration_range: null,
          provider: null,
          model: null,
          temperature: 0.3,  // 降低到0.3，减少创造性，增强对全局大纲的遵循性（v2.5）
          enable_quality_control: true,  // 启用3维质量管控
          // 标题风格参数（新增）
          title_style: titleStyleData.styleId || null,
          title_style_name: titleStyleData.styleName || null
        },
        (chunk, fullContent) => {
          generatedContent.value = fullContent
        },
        (abortController) => {
          currentEventSource.value = abortController
        },
        currentSessionId.value,
        (event) => {
          handleWorkflowEvent(event)
        },
        (newContent, message) => {
          // replace_content事件：每章生成完成后发送完整累积内容
          // 用于确保前端始终显示全部已生成章节（防止流式传输中断导致内容丢失）
          if (newContent && newContent.length > (generatedContent.value || '').length) {
            generatedContent.value = newContent
          }
          // 阶段3流式生成时不显示成功提示，避免频繁弹窗
          if (message && outlineStage.value !== 3) {
            ElMessage.success(message)
          }
        }
      )
      
      if (result && !result.cancelled) {
        unitSummaries.value = parseUnitSummariesFromContent(result.content)
        // 质量管控已在流式生成过程中自动执行，无需再次调用
        outlineStage.value = 4
        ElMessage.success('单元概述生成完成')
      } else if (result && result.cancelled) {
        ElMessage.info('生成已取消')
        if (result.content) {
          unitSummaries.value = parseUnitSummariesFromContent(result.content)
          outlineStage.value = 4
        } else {
          outlineStage.value = 2
        }
      }
    } catch (error) {
      console.error('单元概述生成失败:', error)
      ElMessage.error('单元概述生成失败：' + (error.message || '未知错误'))
      outlineStage.value = 2
    } finally {
      unitSummariesGenerating.value = false
      currentSessionId.value = null
    }
  }

  // 执行逻辑检测
  const performLogicCheck = async () => {
    if (!globalOutlineContent.value || Object.keys(unitSummaries.value).length === 0) {
      return
    }
    
    logicChecking.value = true
    logicCheckResult.value = null
    
    try {
      const response = await generateApi.checkOutlineLogic({
        content_type: type.value,
        global_outline: globalOutlineContent.value,
        unit_summaries: unitSummaries.value,
        provider: null,
        temperature: 0.7
      })
      
      if (response.success && response.data) {
        logicCheckResult.value = response.data
        
        if (response.data.has_issues) {
          if (response.data.revised_units && Object.keys(response.data.revised_units).length > 0) {
            const originalUnits = response.data.original_units || {}
            const revisedUnits = response.data.revised_units
            
            for (const [unitNum, revisedContent] of Object.entries(revisedUnits)) {
              if (unitSummaries.value[unitNum]) {
                unitSummaries.value[unitNum].original_summary = originalUnits[unitNum]?.summary || unitSummaries.value[unitNum].summary
                unitSummaries.value[unitNum].summary = revisedContent
                unitSummaries.value[unitNum].logic_fixed = true
                unitSummaries.value[unitNum].revised_summary = revisedContent
              }
            }
            ElMessage.success(`逻辑检测完成，已修正 ${Object.keys(revisedUnits).length} 个单元的问题`)
          } else {
            ElMessage.warning(`逻辑检测发现 ${response.data.issues?.length || 0} 个潜在问题，但未自动修正`)
          }
        } else {
          ElMessage.success('逻辑检测通过，未发现严重问题')
        }
      }
    } catch (error) {
      console.error('逻辑检测失败:', error)
      
      // 区分超时和其他错误
      if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
        ElMessage.warning('逻辑检测超时，跳过此步骤。您可以稍后手动执行逻辑检测。')
      } else {
        ElMessage.warning('逻辑检测失败，跳过此步骤。您可以稍后手动执行逻辑检测。')
      }
      
      // 不阻断流程，继续后续步骤
      logicCheckResult.value = {
        has_issues: false,
        issues: [],
        error: error.message
      }
    } finally {
      logicChecking.value = false
    }
  }

  // 取消单元概述生成
  const cancelUnitSummariesGeneration = async () => {
    if (!currentSessionId.value) {
      if (currentEventSource.value && currentEventSource.value.abort) {
        currentEventSource.value.abort()
      }
      return
    }
    
    try {
      await generateApi.cancelGeneration(currentSessionId.value)
      if (currentEventSource.value && currentEventSource.value.abort) {
        currentEventSource.value.abort()
      }
      ElMessage.info('正在取消生成...')
    } catch (error) {
      console.error('取消生成失败:', error)
      if (currentEventSource.value && currentEventSource.value.abort) {
        currentEventSource.value.abort()
      }
    }
  }

  // 中断生成
  const handleStop = async (userStore) => {
    if (currentEventSource.value && currentEventSource.value.abort) {
      currentEventSource.value.abort()
      currentEventSource.value = null
    }
    
    if (currentSessionId.value) {
      try {
        await fetch(`${API_BASE_URL}/api/v1/generate/cancel/${currentSessionId.value}`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${userStore.token}`,
            'Content-Type': 'application/json'
          }
        })
      } catch (error) {
        console.warn('发送取消请求失败:', error)
      }
    }
    
    generating.value = false
    globalOutlineGenerating.value = false
    unitSummariesGenerating.value = false
    
    workflowSteps.value.push({
      step: 'stopped',
      status: 'error',
      message: '生成已被用户中断',
      icon: 'CircleClose'
    })
    
    ElMessage.warning('已中断生成')
  }

  // 编辑单元概述
  const editUnitSummary = (unitNum) => {
    editingUnitNumber.value = unitNum.toString()
    editingUnitContent.value = unitSummaries.value[unitNum.toString()]?.summary || ''
  }

  // 保存单元概述修改
  const saveUnitSummary = () => {
    if (editingUnitNumber.value && unitSummaries.value[editingUnitNumber.value]) {
      unitSummaries.value[editingUnitNumber.value].summary = editingUnitContent.value
      editingUnitNumber.value = null
      editingUnitContent.value = ''
      ElMessage.success('单元概述已更新')
    }
  }

  // 取消编辑单元概述
  const cancelEditUnitSummary = () => {
    editingUnitNumber.value = null
    editingUnitContent.value = ''
  }

  // 下载大纲
  const downloadOutline = () => {
    const content = outlineStage.value === 2 ? globalOutlineContent.value : generatedContent.value
    const blob = new Blob([content], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${form.value.title || '大纲'}_${outlineStage.value === 2 ? '全局大纲' : '完整大纲'}.md`
    a.click()
    URL.revokeObjectURL(url)
  }

  // 重置两阶段生成状态
  const resetTwoStageOutline = () => {
    outlineStage.value = 0
    globalOutlineContent.value = ''
    unitSummaries.value = {}
    globalOutlineGenerating.value = false
    unitSummariesGenerating.value = false
    showResult.value = false
    generatedContent.value = ''
    startFromUnit.value = 1
  }

  // 打开导入对话框
  const openImportDialog = () => {
    importType.value = 'global'
    importContent.value = ''
    showImportDialog.value = true
  }

  // 确认导入内容
  const confirmImport = () => {
    if (!importContent.value.trim()) {
      ElMessage.warning('请粘贴要导入的大纲内容')
      return
    }
    
    if (importType.value === 'global') {
      globalOutlineContent.value = importContent.value.trim()
      generatedContent.value = importContent.value.trim()
      outlineStage.value = 2
      showResult.value = true
      ElMessage.success('全局大纲已导入，您可以编辑后继续生成单元概述')
    } else {
      try {
        const parsed = parseUnitSummariesFromContent(importContent.value)
        if (Object.keys(parsed).length > 0) {
          unitSummaries.value = parsed
          // v2.4: 兼容加粗标记的章节标题
          const globalOutlineMatch = importContent.value.match(/^([\s\S]*?)(?=###\s*\*{0,2}\s*第\d+(?:章|集)\s*\*{0,2}[：:])/)
          if (globalOutlineMatch) {
            globalOutlineContent.value = globalOutlineMatch[1].trim()
          } else {
            globalOutlineContent.value = importContent.value.split('###')[0].trim()
          }
          generatedContent.value = importContent.value
          outlineStage.value = 4
          showResult.value = true
          ElMessage.success('完整大纲已导入，您可以编辑后下载')
        } else {
          globalOutlineContent.value = importContent.value.trim()
          generatedContent.value = importContent.value.trim()
          outlineStage.value = 2
          showResult.value = true
          ElMessage.warning('无法解析单元概述，已作为全局大纲导入')
        }
      } catch (error) {
        console.error('解析导入内容失败:', error)
        globalOutlineContent.value = importContent.value.trim()
        generatedContent.value = importContent.value.trim()
        outlineStage.value = 2
        showResult.value = true
        ElMessage.warning('导入内容已作为全局大纲处理')
      }
    }
    
    showImportDialog.value = false
  }

  // 打开从指定单元开始的对话框
  const openStartUnitDialog = () => {
    const unitCount = type.value === 'novel'
      ? parseInt(form.value.chapter_count) || 50
      : parseInt(form.value.episode_count) || 24
    startFromUnit.value = Math.min(startFromUnit.value, unitCount)
    showStartUnitDialog.value = true
  }

  // 从指定单元开始生成
  const handleGenerateFromUnit = async () => {
    if (!globalOutlineContent.value) {
      ElMessage.warning('请先导入或生成全局大纲')
      return
    }
    
    // 智能获取章节数
    const outlineChapterCount = parseChapterCountFromOutline(globalOutlineContent.value)
    const formChapterCount = type.value === 'novel'
      ? parseInt(form.value.chapter_count) || 50
      : parseInt(form.value.episode_count) || 24
    
    const unitCount = outlineChapterCount || formChapterCount
    
    if (startFromUnit.value < 1 || startFromUnit.value > unitCount) {
      ElMessage.warning(`请输入有效的单元编号（1-${unitCount}）`)
      return
    }
    
    showStartUnitDialog.value = false
    outlineStage.value = 3
    unitSummariesGenerating.value = true
    
    try {
      let existingContext = ''
      if (Object.keys(unitSummaries.value).length > 0) {
        existingContext = '\n\n【已生成的单元概述】\n'
        for (const [num, unit] of Object.entries(unitSummaries.value)) {
          if (parseInt(num) < startFromUnit.value) {
            existingContext += `单元${num}: ${unit.title}\n${unit.summary}\n\n`
          }
        }
      }
      
      const modifiedOutline = globalOutlineContent.value + existingContext +
        `\n\n【生成要求】从第${startFromUnit.value}单元开始生成后续单元概述。`
      
      const result = await generateApi.generateUnitSummariesStream(
        {
          content_type: type.value,
          global_outline: modifiedOutline,
          unit_count: unitCount,  // 传递总章节数，后端会计算需要生成的数量
          series_type: null,
          episode_duration_range: null,
          provider: null,
          model: null,
          temperature: 0.7,
          enable_quality_control: true,  // 启用3维质量管控
          // 续生成参数
          existing_content: generatedContent.value || '',
          existing_parsed: unitSummaries.value,
          start_from_unit: startFromUnit.value,
          // 标题风格参数（新增）
          title_style: titleStyleData.styleId || null,
          title_style_name: titleStyleData.styleName || null
        },
        (chunk, fullContent) => {
          generatedContent.value = fullContent
        },
        (abortController) => {
          currentEventSource.value = abortController
        },
        null,
        (event) => {
          handleWorkflowEvent(event)
        },
        (newContent, message) => {
          // replace_content事件：确保前端显示完整内容
          if (newContent && newContent.length > (generatedContent.value || '').length) {
            generatedContent.value = newContent
          }
          // 流式生成时不显示成功提示，避免频繁弹窗
          if (message && outlineStage.value !== 3) {
            ElMessage.success(message)
          }
        }
      )
      
      if (result && !result.cancelled) {
        const newUnits = parseUnitSummariesFromContent(result.content)
        for (const [num, unit] of Object.entries(newUnits)) {
          const actualNum = parseInt(num) + startFromUnit.value - 1
          unitSummaries.value[actualNum.toString()] = {
            ...unit,
            unit_number: actualNum
          }
        }
        outlineStage.value = 4
        ElMessage.success(`从第${startFromUnit.value}单元开始的生成已完成`)
      }
    } catch (error) {
      console.error('单元概述生成失败:', error)
      ElMessage.error('单元概述生成失败：' + (error.message || '未知错误'))
      outlineStage.value = 2
    } finally {
      unitSummariesGenerating.value = false
    }
  }

  // 打开修正详情对话框
  const openRevisionDetail = (unitNum) => {
    currentRevisionUnit.value = unitNum.toString()
    revisionViewMode.value = 'diff'
    showRevisionDetailDialog.value = true
  }

  return {
    // 状态
    generating,
    showResult,
    currentGenerationId,
    generationDuration,
    currentSessionId,
    
    // 两阶段大纲
    outlineStage,
    globalOutlineGenerating,
    unitSummaries,
    unitSummariesGenerating,
    
    // 逻辑检测
    logicChecking,
    logicCheckResult,
    showLogicIssuesDialog,
    
    // 修正详情
    showRevisionDetailDialog,
    currentRevisionUnit,
    revisionViewMode,
    
    // 编辑状态
    editingUnitNumber,
    editingUnitContent,
    editingGlobalOutline,
    editingGlobalOutlineContent,
    
    // 灵活介入
    showImportDialog,
    importType,
    importContent,
    startFromUnit,
    showStartUnitDialog,
    
    // 计算属性
    useTwoStageMode,
    renderedGlobalOutline,
    
    // 方法
    startEditGlobalOutline,
    saveGlobalOutlineEdit,
    cancelEditGlobalOutline,
    buildOutlineInputParams,
    parseUnitSummariesFromContent,
    handleTwoStageGenerate,
    handleGenerateUnitSummaries,
    performLogicCheck,
    cancelUnitSummariesGeneration,
    handleStop,
    editUnitSummary,
    saveUnitSummary,
    cancelEditUnitSummary,
    downloadOutline,
    resetTwoStageOutline,
    openImportDialog,
    confirmImport,
    openStartUnitDialog,
    handleGenerateFromUnit,
    openRevisionDetail
  }
}
