/**
 * 修正处理 composable
 * 管理全局大纲修正、单元概述修正的确认/取消处理，以及单元内容更新和重复清理
 */
import { ElMessage } from 'element-plus'
import { globalOutlineQCApi, unitSummariesQCApi } from '@/api'
import { computeDiffHtml } from '@/utils/diffUtils'

export function useReviseHandlers(deps) {
  const {
    type,
    useTwoStageMode,
    globalOutlineContent,
    generatedContent,
    unitSummaries,
    editingGlobalOutline,
    editingGlobalOutlineContent,
    generationId,
    qcApplied,
    qcReportData,
    issuesFixed,
    qcProgress,
    showGlobalOutlineReviseDialog,
    globalOutlineReviseData,
    showUnitSummariesReviseDialog,
    unitSummariesReviseData,
    unitSummariesOriginalSnapshot,
    revisingIssueId,
    globalOutlineQCReport,
    stopQCSSEConnection
  } = deps

  // ==================== 差异对比 ====================

  function getRevisionDiffHtml(unit) {
    if (!unit?.original_summary || !unit?.revised_summary) return ''
    return computeDiffHtml(unit.original_summary, unit.revised_summary)
  }

  // ==================== 单元概述质控反馈 ====================

  /**
   * 处理单元概述质控用户反馈
   */
  function handleUnitSummariesFeedback({ issue, feedbackType }) {
    console.log('[GenerateForm] 单元概述质控反馈:', {
      issue_id: issue.id,
      feedback_type: feedbackType
    })
  }

  /**
   * 处理应用单元概述修正
   */
  function handleApplyUnitSummariesRevision(revisedData) {
    try {
      console.log('[GenerateForm] 应用单元概述修正:', revisedData)

      if (revisedData.revisedParsed) {
        unitSummaries.value = revisedData.revisedParsed
      }

      if (revisedData.revisedContent) {
        generatedContent.value = revisedData.revisedContent
      }

      if (revisedData.qualityReport) {
        qcReportData.value = revisedData.qualityReport
      }

      ElMessage.success('修正已应用')
    } catch (error) {
      console.error('[GenerateForm] 应用单元概述修正失败:', error)
      ElMessage.error('应用修正失败: ' + (error.message || '未知错误'))
    }
  }

  // ==================== 全局大纲修正 ====================

  /**
   * 处理全局大纲修正 (v2.2优化: 显示对比对话框)
   */
  async function handleGlobalOutlineRevise({ issue, qualityReport: report }) {
    try {
      if (!issue || !report) {
        ElMessage.error('修正参数不完整')
        return
      }

      revisingIssueId.value = issue.id

      const projectId = useTwoStageMode.value ? 0 : (generationId.value || 0)

      console.log('[全局大纲修正] 开始修正问题:', issue.id, 'projectId:', projectId)

      const originalContent = editingGlobalOutline.value
        ? editingGlobalOutlineContent.value
        : globalOutlineContent.value

      const response = await globalOutlineQCApi.revise(projectId, {
        quality_report: report,
        issues_to_fix: [issue.id]
      })

      if (response?.success) {
        const revisedContent = response.data.revised_content
        if (revisedContent) {
          globalOutlineReviseData.value = {
            originalContent: originalContent,
            revisedContent: revisedContent,
            changes: response.data.changes || [],
            issueId: issue.id,
            issueDescription: issue.description,
            originalLength: response.data.original_length,
            revisedLength: response.data.revised_length
          }
          showGlobalOutlineReviseDialog.value = true
          ElMessage.success('修正完成！请确认是否应用修改')
        }
      } else {
        ElMessage.error(response?.message || '修正失败')
      }
    } catch (error) {
      console.error('[全局大纲修正] 修正失败:', error)

      if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
        ElMessage.error('修正超时（20分钟），LLM处理耗时较长，请稍后重试。')
      } else {
        ElMessage.error('修正失败: ' + (error.message || ''))
      }
    } finally {
      revisingIssueId.value = null
    }
  }

  // ==================== 修正确认/取消 ====================

  /**
   * 确认应用全局大纲修正
   */
  function handleConfirmGlobalOutlineRevise() {
    const issueId = globalOutlineReviseData.value.issueId

    globalOutlineContent.value = globalOutlineReviseData.value.revisedContent
    generatedContent.value = globalOutlineReviseData.value.revisedContent
    if (editingGlobalOutline.value) {
      editingGlobalOutlineContent.value = globalOutlineReviseData.value.revisedContent
    }

    qcApplied.value = true
    issuesFixed.value = globalOutlineReviseData.value.changes?.length || 0

    if (issueId === 'auto_revise_imported') {
      console.log('[全局大纲修正] 导入大纲场景，使用已有质控报告')
    } else {
      qcReportData.value = globalOutlineQCReport.value
    }

    qcProgress.value = null
    stopQCSSEConnection()

    showGlobalOutlineReviseDialog.value = false

    if (issueId === 'auto_revise_imported') {
      ElMessage.success(
        `已应用导入大纲修正！共修正 ${issuesFixed.value} 个问题 ` +
        `(${globalOutlineReviseData.value.originalLength}字 → ${globalOutlineReviseData.value.revisedLength}字)`
      )
    } else {
      ElMessage.success(
        `已应用全局辩证修正！共修正 ${issuesFixed.value} 个问题 ` +
        `(${globalOutlineReviseData.value.originalLength}字 → ${globalOutlineReviseData.value.revisedLength}字)`
      )
    }

    console.log('[全局大纲修正] 修正已应用, issueId:', issueId)
  }

  /**
   * 取消应用全局大纲修正
   */
  function handleCancelGlobalOutlineRevise() {
    ElMessage.info('已取消修正，保留原始内容')
    console.log('[全局大纲修正] 修正已取消')
  }

  /**
   * 处理单元概述修正确认
   */
  async function handleConfirmUnitSummariesRevise() {
    const reviseData = unitSummariesReviseData.value

    if (!reviseData) {
      ElMessage.error('修正数据为空，无法应用修正')
      return
    }

    // v3.1新增: 保存修正前的原始版本快照（用于后续对比）
    unitSummariesOriginalSnapshot.value = {
      content: generatedContent.value || '',
      parsed: { ...unitSummaries.value }
    }

    // 1. 更新 unitSummaries
    // 后端的 revisedParsed (merged_parsed) 已经包含所有单元的完整数据：
    // - 已修正单元：{ ...original, summary, full_content, revision_reason, revised_at }
    // - 未修正单元：原始数据的完整拷贝
    // 直接替换整个 unitSummaries，避免复杂的单元差异对比逻辑
    if (reviseData.revisedParsed && Object.keys(reviseData.revisedParsed).length > 0) {
      unitSummaries.value = { ...reviseData.revisedParsed }
      console.log('[单元概述修正] unitSummaries已更新,键数:', Object.keys(unitSummaries.value).length)
    } else {
      console.warn('[单元概述修正] revisedParsed为空，无法更新unitSummaries')
    }

    // 2. 重建完整的 generatedContent（用于下载）
    const unitLabel = type.value === 'novel' ? '章' : '集'
    const allChapterTexts = Object.keys(unitSummaries.value)
      .sort((a, b) => parseInt(a) - parseInt(b))
      .map(num => {
        const unit = unitSummaries.value[num]
        const content = unit.full_content || unit.summary || ''
        if (!content) return null

        // 检查内容是否已经包含Markdown标题，避免重复添加
        const titlePattern = new RegExp(`^#{1,3}\\s*第${num}${unitLabel}`)
        if (!titlePattern.test(content)) {
          return `### 第${num}${unitLabel}：${unit.title || ''}\n${content}`
        }
        return content
      })
      .filter(Boolean)

    generatedContent.value = allChapterTexts.join('\n\n')

    console.log('[单元概述修正] generatedContent已更新,长度:', generatedContent.value.length)

    // 3. 标记已应用质控修正
    qcApplied.value = true
    issuesFixed.value = reviseData.qualityReport?.issues?.filter(i => i.severity === 'critical').length || 0
    qcReportData.value = reviseData.qualityReport

    showUnitSummariesReviseDialog.value = false

    ElMessage.success('已应用单元概述修正')
    console.log('[单元概述修正] 修正已应用，当前单元数:', Object.keys(unitSummaries.value).length)
  }

  /**
   * 处理单元概述修正取消
   */
  function handleCancelUnitSummariesRevise() {
    unitSummariesReviseData.value = {
      originalContent: '',
      revisedContent: '',
      revisedParsed: null,
      qualityReport: null
    }

    ElMessage.info('已取消修正，保留原始内容')
    console.log('[单元概述修正] 修正已取消，数据已清理')
  }

  /**
   * v3.1新增：打开单元概述版本对比窗口
   * 允许用户在任何时候查看修正前后的差异
   */
  function handleOpenUnitSummariesDiff() {
    const snapshot = unitSummariesOriginalSnapshot.value

    if (!snapshot.content && !snapshot.parsed) {
      ElMessage.warning('尚未应用过修正，无法对比。请先执行质控修正。')
      return
    }

    // 填充对比数据：原始版本来自快照，修正后版本来自当前内容
    unitSummariesReviseData.value = {
      originalContent: snapshot.content,
      revisedContent: generatedContent.value || '',
      revisedParsed: { ...unitSummaries.value },
      qualityReport: qcReportData.value,
      changes: []
    }

    showUnitSummariesReviseDialog.value = true
    console.log('[单元概述对比] 打开版本对比窗口，原始长度:', snapshot.content.length, '，修正后长度:', generatedContent.value?.length || 0)
  }

  // ==================== 重复章节清理 ====================

  /**
   * 处理清理单元概述质控报告中的重复单元（手动模式）
   */
  function handleRemoveUnitSummariesQCDuplicates({ duplicates, unitSummaries: summaries }) {
    try {
      console.log('[GenerateForm] 清理单元概述重复单元:', duplicates.length, '组')

      if (!generatedContent.value) {
        ElMessage.warning('没有可清理的内容')
        return
      }

      const chapterRegex = /###\s*第([\u4e00二三四五六七八九十百千万\d]+)[章集场][：:]\s*(.+?)\n([\s\S]*?)(?=###\s*第|$)/g
      const chapters = []
      let match

      while ((match = chapterRegex.exec(generatedContent.value)) !== null) {
        chapters.push({
          unitNumber: match[1],
          title: match[2].trim(),
          content: match[3].trim(),
          fullMatch: match[0],
          startIndex: match.index,
          endIndex: match.index + match[0].length
        })
      }

      if (chapters.length === 0) {
        ElMessage.warning('未解析到章节内容')
        return
      }

      const indicesToRemove = new Set()

      duplicates.forEach(group => {
        for (let i = 1; i < group.duplicates.length; i++) {
          const dup = group.duplicates[i]
          const chapterIndex = chapters.findIndex(ch =>
            ch.unitNumber === dup.unitNumber &&
            ch.title === dup.title &&
            ch.content === dup.content &&
            !indicesToRemove.has(chapters.indexOf(ch))
          )
          if (chapterIndex !== -1) {
            indicesToRemove.add(chapterIndex)
          }
        }
      })

      let cleanedContent = generatedContent.value
      const sortedIndices = Array.from(indicesToRemove).sort((a, b) => b - a)

      sortedIndices.forEach(index => {
        const chapter = chapters[index]
        cleanedContent = cleanedContent.substring(0, chapter.startIndex) +
                         cleanedContent.substring(chapter.endIndex)
      })

      cleanedContent = cleanedContent.replace(/\n{3,}/g, '\n\n').trim()

      generatedContent.value = cleanedContent

      const removedCount = sortedIndices.length

      console.log('[GenerateForm] 已清理', removedCount, '个重复单元')
      ElMessage.success(`已清理 ${removedCount} 个重复单元`)
    } catch (error) {
      console.error('[GenerateForm] 清理重复单元失败:', error)
      ElMessage.error('清理失败: ' + (error.message || '未知错误'))
    }
  }

  /**
   * 处理单元概述重复章节清理（对比对话框中使用）
   */
  function handleRemoveUnitSummariesDuplicates({ duplicates, revisedContent }) {
    if (!revisedContent) {
      ElMessage.error('修正内容为空')
      return
    }

    console.log('[重复章节清理] 开始清理，重复组数:', duplicates.length)

    const chapterRegex = /###\s*第([\u4e00二三四五六七八九十百千万\d]+)[章集场][：:]\s*(.+?)\n([\s\S]*?)(?=###\s*第|$)/g
    const chapters = []
    let match

    while ((match = chapterRegex.exec(revisedContent)) !== null) {
      chapters.push({
        unitNumber: match[1],
        title: match[2].trim(),
        content: match[3].trim(),
        fullMatch: match[0],
        startIndex: match.index,
        endIndex: match.index + match[0].length
      })
    }

    if (chapters.length === 0) {
      ElMessage.error('未解析到章节内容')
      return
    }

    const indicesToRemove = new Set()

    duplicates.forEach(group => {
      for (let i = 1; i < group.duplicates.length; i++) {
        const dup = group.duplicates[i]
        const chapterIndex = chapters.findIndex(ch =>
          ch.unitNumber === dup.unitNumber &&
          ch.title === dup.title &&
          ch.content === dup.content
        )
        if (chapterIndex !== -1) {
          indicesToRemove.add(chapterIndex)
        }
      }
    })

    let cleanedContent = revisedContent
    const chaptersArray = Array.from(indicesToRemove).sort((a, b) => b - a)

    chaptersArray.forEach(index => {
      const chapter = chapters[index]
      cleanedContent = cleanedContent.substring(0, chapter.startIndex) +
                       cleanedContent.substring(chapter.endIndex)
    })

    cleanedContent = cleanedContent.replace(/\n{3,}/g, '\n\n').trim()

    unitSummariesReviseData.value.revisedContent = cleanedContent

    // 重新解析单元概述
    try {
      const parsed = parseUnitSummaries(cleanedContent)
      if (parsed && Object.keys(parsed).length > 0) {
        unitSummariesReviseData.value.revisedParsed = parsed
        console.log('[重复章节清理] 清理完成，清理前章节数:', chapters.length,
                    '清理后章节数:', Object.keys(parsed).length)
        ElMessage.success(`已清理 ${indicesToRemove.size} 个重复章节`)
      } else {
        ElMessage.warning('清理后解析失败，请检查内容')
      }
    } catch (error) {
      console.error('[重复章节清理] 解析失败:', error)
      ElMessage.error('清理后解析失败: ' + error.message)
    }
  }

  // ==================== 单元内容更新 ====================

  /**
   * 处理单元内容更新（质控修正应用）
   */
  function handleUpdateUnitContent({ chapter_number, unit_id, content }) {
    console.log('=== 更新单元内容 ===')
    console.log('chapter_number:', chapter_number)
    console.log('unit_id:', unit_id)
    console.log('新内容长度:', content?.length, '字')

    if (!chapter_number || !content) {
      console.error('缺少chapter_number或content')
      return
    }

    const key = String(chapter_number)

    // 优先使用unit_id精确定位
    if (unit_id && unitSummaries.value[key]) {
      console.log('使用unit_id精确定位')
      unitSummaries.value[key].summary = content
      unitSummaries.value[key].full_content = content

      updateGeneratedContentUnit(chapter_number, content)

      ElMessage.success(`第${chapter_number}单元已更新`)
      return
    }

    // 降级方案：仅使用chapter_number定位
    if (unitSummaries.value[key]) {
      console.log('使用chapter_number定位')
      unitSummaries.value[key].summary = content
      unitSummaries.value[key].full_content = content

      updateGeneratedContentUnit(chapter_number, content)

      ElMessage.success(`第${chapter_number}单元已更新`)
      return
    }

    console.error(`未找到第${chapter_number}单元`)
    ElMessage.error(`未找到第${chapter_number}单元`)
  }

  /**
   * 辅助函数: 更新generatedContent中的指定单元
   */
  function updateGeneratedContentUnit(chapterNumber, newContent) {
    if (!generatedContent.value) return

    const isMovie = generatedContent.value.includes('场') && !generatedContent.value.includes('集')

    const patterns = isMovie
      ? [
          new RegExp(`(\\*\\*第${chapterNumber}场[\\s\\S]*?\\*\\*)(?:[\\s\\S]*?)(?=\\*\\*第${chapterNumber + 1}场|$)`),
        ]
      : [
          new RegExp(`(###\\s*第${chapterNumber}(?:章|集)[\\s\\S]*?)(?=###\\s*第${chapterNumber + 1}(?:章|集)|$)`),
        ]

    for (const pattern of patterns) {
      const match = generatedContent.value.match(pattern)
      if (match) {
        const titlePart = match[1]
        const oldContent = match[0]
        const newFullContent = titlePart + '\n' + newContent

        generatedContent.value = generatedContent.value.replace(oldContent, newFullContent)
        console.log('已更新generatedContent中的单元内容')
        return
      }
    }

    console.warn('未能在generatedContent中找到对应单元')
  }

  /**
   * 解析单元概述内容
   */
  function parseUnitSummaries(content) {
    if (!content) return {}

    const unitLabel = type.value === 'novel' ? '章' : '集'
    const regex = new RegExp(`###\\s*第([\\u4e00二三四五六七八九十百千\\d\\w]+)${unitLabel}[：:]\\s*(.+?)\\n([\\s\\S]*?)(?=###\\s*第|$)`, 'g')
    const result = {}
    let match

    while ((match = regex.exec(content)) !== null) {
      const unitNum = match[1]
      const title = match[2].trim()
      const fullContent = match[3].trim()

      result[unitNum] = {
        title: title,
        summary: fullContent.substring(0, 500),
        full_content: fullContent
      }
    }

    return result
  }

  return {
    getRevisionDiffHtml,
    handleUnitSummariesFeedback,
    handleApplyUnitSummariesRevision,
    handleGlobalOutlineRevise,
    handleConfirmGlobalOutlineRevise,
    handleCancelGlobalOutlineRevise,
    handleConfirmUnitSummariesRevise,
    handleCancelUnitSummariesRevise,
    handleOpenUnitSummariesDiff,
    handleRemoveUnitSummariesQCDuplicates,
    handleRemoveUnitSummariesDuplicates,
    handleUpdateUnitContent,
    updateGeneratedContentUnit,
    parseUnitSummaries
  }
}
