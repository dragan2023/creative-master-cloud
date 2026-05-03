/**
 * 质量控制 composable
 * 管理质控SSE订阅、全局大纲质控、单元概述质控和自动修正逻辑
 */
import { ElMessage } from 'element-plus'
import { globalOutlineQCApi, unitSummariesQCApi } from '@/api'
import { getToken } from '@/utils/authStorage'

export function useQualityControl(deps) {
  const {
    type,
    form,
    useTwoStageMode,
    globalOutlineContent,
    generatedContent,
    unitSummaries,
    editingGlobalOutline,
    editingGlobalOutlineContent,
    generationId,
    importedOutline,
    globalOutlineQCLoading,
    globalOutlineQCReport,
    qcProgress,
    qcSSEConnection,
    revisingIssueId,
    qcApplied,
    qcReportData,
    issuesFixed,
    autoQCLoading,
    unitSummariesQCLoading,
    showGlobalOutlineReviseDialog,
    globalOutlineReviseData,
    showUnitSummariesReviseDialog,
    unitSummariesReviseData
  } = deps

  // ==================== 质控SSE订阅 ====================

  /**
   * 启动质控SSE订阅
   * 实时接收全局大纲质控进度
   */
  function startQCSSESubscription(taskId) {
    // 关闭现有连接
    stopQCSSEConnection()

    const token = getToken()
    const baseURL = import.meta.env.VITE_API_BASE_URL || ''
    const sseURL = `${baseURL}/api/v1/novel-writer/quality-control/global-outline/${taskId}/events${token ? `?token=${encodeURIComponent(token)}` : ''}`

    console.log('[质控SSE] 连接到:', sseURL.replace(/token=[^&]+/, 'token=***'))

    let reconnectAttempts = 0
    const MAX_RECONNECT_ATTEMPTS = 3
    const RECONNECT_DELAY = 2000

    const eventSource = new EventSource(sseURL)
    qcSSEConnection.value = eventSource

    eventSource.onopen = () => {
      console.log('[质控SSE] 连接已建立')
      reconnectAttempts = 0
    }

    eventSource.addEventListener('connected', (event) => {
      console.log('[质控SSE] 服务器确认连接:', event.data)
      reconnectAttempts = 0
    })

    eventSource.addEventListener('progress', (event) => {
      try {
        const data = JSON.parse(event.data)
        console.log('[质控SSE] 进度更新:', data)
        qcProgress.value = data
      } catch (e) {
        console.error('[质控SSE] 解析进度数据失败:', e)
      }
    })

    eventSource.addEventListener('completed', (event) => {
      try {
        const data = JSON.parse(event.data)
        console.log('[质控SSE] 分析完成:', data)
        qcProgress.value = { ...data, status: 'completed' }
        stopQCSSEConnection()
      } catch (e) {
        console.error('[质控SSE] 解析完成数据失败:', e)
      }
    })

    eventSource.addEventListener('error', (event) => {
      console.error('[质控SSE] 事件错误:', event)
      if (event.data) {
        try {
          const data = JSON.parse(event.data)
          qcProgress.value = { ...data, status: 'error' }
        } catch (e) {
          // 忽略解析错误
        }
      }
      stopQCSSEConnection()
    })

    eventSource.onerror = (error) => {
      console.warn('[质控SSE] 连接错误:', error)
      reconnectAttempts++

      if (reconnectAttempts >= MAX_RECONNECT_ATTEMPTS) {
        console.error('[质控SSE] 重连次数已达上限')
        qcProgress.value = {
          status: 'error',
          message: '连接失败，请刷新页面重试',
          reconnect_failed: true
        }
        stopQCSSEConnection()
        ElMessage.warning('质控进度连接中断，但质控仍在后台运行，请稍后查看结果')
      } else {
        console.log(`[质控SSE] 浏览器自动重连中 (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`)
        qcProgress.value = {
          status: 'reconnecting',
          message: `连接中断，正在重连 (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})...`,
          reconnect_attempt: reconnectAttempts
        }
      }
    }
  }

  /**
   * 停止质控SSE连接
   */
  function stopQCSSEConnection() {
    if (qcSSEConnection.value) {
      qcSSEConnection.value.close()
      qcSSEConnection.value = null
      console.log('[质控SSE] 连接已关闭')
    }
  }

  // ==================== 导入大纲质控 ====================

  /**
   * 对导入的单元概述执行质控检测
   */
  async function handleImportedUnitSummariesQC() {
    if (!unitSummaries.value || Object.keys(unitSummaries.value).length === 0) {
      ElMessage.warning('没有可检测的单元概述')
      return
    }

    autoQCLoading.value = true

    try {
      const token = getToken()
      const response = await fetch(
        `${import.meta.env.VITE_API_BASE_URL || ''}/api/v1/novel-writer/quality-control/imported-outline/auto-revise`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({
            outline_content: generatedContent.value,
            content_type: type.value === 'novel' ? 'novel' : (type.value === 'movie-outline' ? 'movie_outline' : 'series_outline'),
            enable_auto_revise: false
          })
        }
      )

      const result = await response.json()

      if (result.success) {
        qcReportData.value = result.data.qc_report
        qcApplied.value = true
        issuesFixed.value = result.data.issues_fixed || 0

        ElMessage.success(`质控检测完成，发现 ${qcReportData.value?.issues?.length || 0} 个问题`)
      } else {
        ElMessage.error(result.message || '质控检测失败')
      }
    } catch (error) {
      console.error('质控检测失败:', error)
      ElMessage.error('质控检测失败: ' + (error.message || '未知错误'))
    } finally {
      autoQCLoading.value = false
    }
  }

  // ==================== 单元概述质控 ====================

  /**
   * 处理单元概述质量检测（手动触发）
   */
  async function handleUnitSummariesQC() {
    if (!unitSummaries.value || Object.keys(unitSummaries.value).length === 0) {
      ElMessage.warning('没有可检测的单元概述')
      return
    }

    if (!globalOutlineContent.value || globalOutlineContent.value.trim().length === 0) {
      ElMessage.warning({
        message: '未检测到全局大纲！质控检测需要全局大纲作为参考标准。',
        duration: 5000,
        group: 'qc-warning'
      })

      const { ElMessageBox } = await import('element-plus')
      try {
        await ElMessageBox.confirm(
          '当前没有全局大纲，质控检测可能不准确。您可以：\n\n1. 点击"取消"，先导入全局大纲\n2. 点击"继续"，使用当前内容检测（效果可能不佳）',
          '缺少全局大纲',
          {
            confirmButtonText: '继续检测',
            cancelButtonText: '取消',
            type: 'warning'
          }
        )
      } catch {
        return
      }
    }

    unitSummariesQCLoading.value = true

    try {
      const result = await unitSummariesQCApi.analyzeAndRevise({
        content_type: type.value === 'novel' ? 'novel' : (type.value === 'movie-outline' ? 'movie_outline' : 'series_outline'),
        global_outline: globalOutlineContent.value || '',
        unit_summaries: unitSummaries.value,
        temperature: 0.7
      })

      if (result.success) {
        const { quality_report, revised_content, revised_parsed, original_content, original_parsed, has_issues, issues_count, changes, auto_revised } = result.data

        qcReportData.value = quality_report
        qcApplied.value = true
        issuesFixed.value = issues_count || 0

        if (auto_revised && revised_content) {
          ElMessage.success(`质控检测完成，发现 ${quality_report?.issues?.length || 0} 个问题，已修正 ${changes?.length || 0} 个问题`)

          // v3.1修复: 优先使用后端返回的original_content（精确的修正前版本）
          // 回退到generatedContent.value（兼容旧版后端未返回original_content的情况）
          const originalBeforeRevise = original_content || generatedContent.value

          unitSummariesReviseData.value = {
            originalContent: originalBeforeRevise,
            revisedContent: revised_content,
            revisedParsed: revised_parsed,
            qualityReport: quality_report,
            changes: changes || []
          }

          showUnitSummariesReviseDialog.value = true
        } else {
          const issueCount = quality_report?.issues?.length || 0
          if (issueCount > 0) {
            ElMessage.warning(`质控检测完成，发现 ${issueCount} 个问题，但未启用自动修正`)
          } else {
            ElMessage.success('质控检测完成，未发现任何问题')
          }
        }
      } else {
        ElMessage.error(result.message || '质控检测失败')
      }
    } catch (error) {
      console.error('单元概述质控检测失败:', error)

      if (error.message && error.message.includes('timeout')) {
        ElMessage.error('质控检测超时（10分钟），请稍后重试或减少单元数量')
      } else {
        const errorMessage = error.message || error.response?.data?.message || '未知错误'
        ElMessage.error('质控检测失败: ' + errorMessage)
      }
    } finally {
      unitSummariesQCLoading.value = false
    }
  }

  // ==================== 全局大纲质控 ====================

  /**
   * 处理全局大纲质量检测
   */
  async function handleGlobalOutlineQC() {
    try {
      if (importedOutline.value) {
        await handleAutoQCForImported()
        return
      }

      globalOutlineQCLoading.value = true
      qcProgress.value = null

      const outlineContent = editingGlobalOutline.value
        ? editingGlobalOutlineContent.value
        : globalOutlineContent.value

      if (!outlineContent || outlineContent.trim().length === 0) {
        ElMessage.warning('全局大纲内容为空，请先生成全局大纲')
        return
      }

      const projectId = useTwoStageMode.value ? 0 : (generationId.value || 0)

      console.log('========== [全局大纲质控] 调试信息 ==========')
      console.log('useTwoStageMode:', useTwoStageMode.value)
      console.log('generationId:', generationId.value)
      console.log('projectId:', projectId)
      console.log('outlineContent length:', outlineContent.length)
      console.log('=============================================')

      const requestData = {
        dimensions: null,
        depth: 'standard'
      }

      if (useTwoStageMode.value) {
        requestData.existing_outline = outlineContent
        console.log('[全局大纲质控] 两阶段模式,传递大纲内容')
      }

      const response = await globalOutlineQCApi.analyze(projectId, requestData)

      if (response?.task_id) {
        console.log('[全局大纲质控] 启动SSE订阅, task_id:', response.task_id)
        startQCSSESubscription(response.task_id)
      }

      if (response?.success) {
        console.log('[全局大纲质控] 响应数据:', response)

        globalOutlineQCReport.value = response.data

        // 强制触发Vue更新
        await new Promise(resolve => setTimeout(resolve, 100))

        const issuesCount = response.data.issues?.length || 0
        ElMessage.success(
          `质量检测完成！综合得分: ${response.data.overall_score?.toFixed(1) || 0}分, ` +
          `发现 ${issuesCount} 个问题`
        )

        if (issuesCount > 0) {
          console.log('[全局大纲质控] 发现问题，开始自动修正...')
          ElMessage.info(`检测到 ${issuesCount} 个问题，正在自动进行全局辩证修正...`)

          await handleAutoGlobalOutlineRevise(response.data, outlineContent)
        }
      } else {
        ElMessage.error(response?.message || '质量检测失败')
      }
    } catch (error) {
      console.error('[全局大纲质控] 错误:', error)

      if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
        ElMessage.error('质量检测超时（20分钟），LLM分析耗时较长，请稍后重试。')
      } else if (error.response?.status === 405) {
        ElMessage.error('API端点不可用，请检查后端服务是否已重启')
      } else if (error.response?.status === 404) {
        ElMessage.error('API端点未找到，请检查后端路由配置')
      } else {
        ElMessage.error('质量检测失败: ' + (error.response?.data?.detail || error.message || ''))
      }
    } finally {
      globalOutlineQCLoading.value = false
    }
  }

  // ==================== 自动全局大纲修正 ====================

  /**
   * 自动全局大纲辩证性整体修正
   */
  async function handleAutoGlobalOutlineRevise(qualityReport, originalContent) {
    try {
      revisingIssueId.value = 'auto_revise_all'

      console.log('[自动全局修正] 开始全局辩证性整体修正...')

      const projectId = useTwoStageMode.value ? 0 : (generationId.value || 0)

      const issuesToFix = qualityReport.issues?.map(issue => issue.id) || []

      if (issuesToFix.length === 0) {
        console.log('[自动全局修正] 没有需要修正的问题')
        return
      }

      console.log(`[自动全局修正] 准备修正 ${issuesToFix.length} 个问题`)

      const qualityReportWithOutline = {
        ...qualityReport,
        original_outline: qualityReport.original_outline || originalContent
      }

      const response = await globalOutlineQCApi.revise(projectId, {
        quality_report: qualityReportWithOutline,
        issues_to_fix: issuesToFix
      })

      if (response?.success) {
        const revisedContent = response.data.revised_content
        console.log('[自动全局修正] 检查修正结果:')
        console.log('  - response.success:', response.success)
        console.log('  - revisedContent存在:', !!revisedContent)
        console.log('  - revisedContent长度:', revisedContent?.length || 0)

        if (revisedContent) {
          console.log('[自动全局修正] 修正完成，准备显示对比对话框...')

          globalOutlineReviseData.value = {
            originalContent: originalContent,
            revisedContent: revisedContent,
            changes: response.data.changes || qualityReport.issues || [],
            issueId: 'auto_revise_all',
            issueDescription: `自动修正 ${issuesToFix.length} 个问题`,
            originalLength: response.data.original_length || originalContent.length,
            revisedLength: response.data.revised_length || revisedContent.length
          }

          console.log('[自动全局修正] 对话框数据已填充')

          showGlobalOutlineReviseDialog.value = true

          console.log('[自动全局修正] 对话框状态:', showGlobalOutlineReviseDialog.value)

          globalOutlineQCReport.value = {
            ...qualityReport,
            revised: true,
            revised_at: new Date().toISOString(),
            revised_issues: issuesToFix
          }
        } else {
          console.error('[自动全局修正] 警告: revisedContent为空!')
          ElMessage.warning('修正完成但未返回修正内容，请检查后端日志')
        }
      } else {
        console.error('[自动全局修正] API返回失败:', response)
        ElMessage.warning(`自动修正失败: ${response?.message || '未知错误'}`)
      }
    } catch (error) {
      console.error('[自动全局修正] 修正失败:', error)

      if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
        ElMessage.warning('全局修正超时（20分钟），LLM处理耗时较长，可稍后手动触发修正。')
      } else {
        ElMessage.warning('全局修正失败: ' + (error.message || ''))
      }
    } finally {
      revisingIssueId.value = null
    }
  }

  /**
   * 导入大纲自动质控（内部方法）
   */
  async function handleAutoQCForImported() {
    try {
      globalOutlineQCLoading.value = true

      const token = getToken()
      const response = await fetch(
        `${import.meta.env.VITE_API_BASE_URL || ''}/api/v1/novel-writer/quality-control/imported-outline/auto-revise`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${token}`
          },
          body: JSON.stringify({
            outline_content: generatedContent.value,
            content_type: type.value === 'novel' ? 'novel' : (type.value === 'movie-outline' ? 'movie_outline' : 'series_outline'),
            enable_auto_revise: true
          })
        }
      )

      const result = await response.json()

      if (result.success) {
        qcReportData.value = result.data.qc_report
        qcApplied.value = true
        issuesFixed.value = result.data.issues_fixed || 0

        if (result.data.revised_content) {
          globalOutlineReviseData.value = {
            originalContent: generatedContent.value,
            revisedContent: result.data.revised_content,
            changes: result.data.changes || [],
            issueId: 'auto_revise_imported',
            issueDescription: `导入大纲自动修正 ${result.data.issues_fixed || 0} 个问题`,
            originalLength: result.data.original_length || generatedContent.value.length,
            revisedLength: result.data.revised_length || result.data.revised_content.length
          }
          showGlobalOutlineReviseDialog.value = true
          ElMessage.success(`导入大纲自动质控完成，修正 ${result.data.issues_fixed || 0} 个问题`)
        } else {
          const issueCount = result.data.qc_report?.issues?.length || 0
          ElMessage.success(`质控检测完成，发现 ${issueCount} 个问题`)
        }
      } else {
        ElMessage.error(result.message || '自动质控失败')
      }
    } catch (error) {
      console.error('导入大纲自动质控失败:', error)
      ElMessage.error('自动质控失败: ' + (error.message || '未知错误'))
    } finally {
      globalOutlineQCLoading.value = false
    }
  }

  return {
    startQCSSESubscription,
    stopQCSSEConnection,
    handleImportedUnitSummariesQC,
    handleUnitSummariesQC,
    handleGlobalOutlineQC,
    handleAutoGlobalOutlineRevise
  }
}
