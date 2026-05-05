/**
 * 单元概述生成 composable
 * 管理两阶段生成中的单元概述生成、续生成、逻辑检测等逻辑
 */
import { ElMessage, ElMessageBox } from 'element-plus'
import { generateApi } from '@/api'
import { parseChapterCountFromOutline, parseUnitSummariesFromContent } from '../utils/outlineParser'

export function useUnitSummariesGeneration(deps) {
  const {
    type,
    form,
    globalOutlineContent,
    generatedContent,
    unitSummaries,
    outlineStage,
    currentSessionId,
    currentEventSource,
    unitSummariesGenerating,
    globalOutlineGenerating,
    showResult,
    titleStyleData,
    startFromUnit,
    showStartUnitDialog,
    expectedUnitCount,
    backendResumeInfo,
    logicChecking,
    logicCheckResult,
    generationId,
    handleWorkflowEvent,
  } = deps

  // 前端路由参数格式（连字符）→ 后端 content_type 格式（下划线）
  function toBackendContentType(t) {
    const map = { 'movie-outline': 'movie_outline', 'series-outline': 'series_outline' }
    return map[t] || t
  }

  // ==================== 两阶段生成（第二阶段：单元概述） ====================

  async function handleGenerateUnitSummaries() {
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

    console.log(`[GenerateForm] 章节数计算:`)
    console.log(`  - 表单设置: ${formChapterCount || '未填写'}`)
    console.log(`  - 从大纲解析: ${outlineChapterCount || '未找到'}`)
    console.log(`  - 最终使用: ${unitCount}`)

    currentSessionId.value = `unit_summaries_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

    outlineStage.value = 3
    unitSummariesGenerating.value = true
    unitSummaries.value = {}

    try {
      const result = await generateApi.generateUnitSummariesStream(
        {
          content_type: toBackendContentType(type.value),
          global_outline: globalOutlineContent.value,
          unit_count: unitCount,
          series_type: null,
          episode_duration_range: null,
          provider: null,
          model: null,
          temperature: 0.3,  // 降低到0.3，减少创造性，增强对全局大纲的遵循性（v2.5）
          enable_quality_control: true,  // 启用3维质量管控
          qc_mode: 'auto',  // 始终自动修正（v3.0）
          project_id: generationId?.value || null,  // [2026-05-05] 传递project_id使后端能保存到NovelProject.unit_summaries
          // 标题风格参数
          title_style: titleStyleData.value.styleId || null,
          title_style_name: titleStyleData.value.styleName || null,
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
          generatedContent.value = newContent
          ElMessage.success(message || '内容已更新')
        }
      )

      if (result && !result.cancelled) {
        unitSummaries.value = parseUnitSummariesFromContent(result.content, toBackendContentType(type.value))
        outlineStage.value = 4
        ElMessage.success('单元概述生成完成')
      } else if (result && result.cancelled) {
        ElMessage.info('生成已取消')
        if (result.content) {
          unitSummaries.value = parseUnitSummariesFromContent(result.content, toBackendContentType(type.value))
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

  // ==================== 逻辑检测 ====================

  async function performLogicCheck() {
    if (!globalOutlineContent.value || Object.keys(unitSummaries.value).length === 0) {
      return
    }

    const logicChecking = deps.logicChecking
    const logicCheckResult = deps.logicCheckResult

    logicChecking.value = true
    logicCheckResult.value = null

    try {
      const response = await generateApi.checkOutlineLogic({
        content_type: toBackendContentType(type.value),
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

      if (error.code === 'ECONNABORTED' || error.message.includes('timeout')) {
        ElMessage.warning('逻辑检测超时，跳过此步骤。您可以稍后手动执行逻辑检测。')
      } else {
        ElMessage.warning('逻辑检测失败，跳过此步骤。您可以稍后手动执行逻辑检测。')
      }

      logicCheckResult.value = {
        has_issues: false,
        issues: [],
        error: error.message
      }
    } finally {
      logicChecking.value = false
    }
  }

  // ==================== 取消生成 ====================

  async function cancelUnitSummariesGeneration() {
    if (!currentSessionId.value) {
      if (currentEventSource.value && currentEventSource.value.abort) {
        currentEventSource.value.abort()
      }
      return
    }

    try {
      // 后端取消请求（10秒超时，不阻塞本地流中断）
      try {
        await generateApi.cancelGeneration(currentSessionId.value)
      } catch (cancelApiErr) {
        // 后端取消超时是预期行为（模型推理可能无法立即中断），静默处理
        console.debug('[cancelUnitSummariesGeneration] 后端取消API调用完成（可能超时，本地流已中断）:', cancelApiErr.message)
      }
      // 中断本地 SSE 流连接
      if (currentEventSource.value && currentEventSource.value.abort) {
        currentEventSource.value.abort()
      }
      ElMessage.info('生成已取消')
    } catch (error) {
      console.error('取消生成失败:', error)
      if (currentEventSource.value && currentEventSource.value.abort) {
        currentEventSource.value.abort()
      }
    }
  }

  // ==================== 断点续生成（核心方法） ====================

  async function handleResumeUnitSummaries() {
    if (!unitSummaries.value || Object.keys(unitSummaries.value).length === 0) {
      ElMessage.warning('没有已生成的单元概述，无法续生成')
      return
    }

    if (!globalOutlineContent.value) {
      ElMessage.warning('缺少全局大纲，无法续生成')
      return
    }

    const existingCount = Object.keys(unitSummaries.value).length
    const unitCount = expectedUnitCount.value
    const startFrom = existingCount + 1
    const remainingCount = unitCount - existingCount

    if (existingCount >= unitCount) {
      ElMessage.info('所有章节已生成完成，无需续生成')
      return
    }

    if (unitSummariesGenerating.value) {
      ElMessage.warning('正在生成中，请稍候...')
      return
    }

    // 确认对话框
    try {
      await ElMessageBox.confirm(
        `当前已生成 ${existingCount} 章，目标 ${unitCount} 章。\n将从第 ${startFrom} 章继续生成剩余 ${remainingCount} 章。\n\n已有内容不会被清除，续生成内容将与前文自然衔接。`,
        '断点续生成',
        {
          confirmButtonText: '开始续生成',
          cancelButtonText: '取消',
          type: 'info'
        }
      )
    } catch {
      return  // 用户取消
    }

    unitSummariesGenerating.value = true
    currentSessionId.value = `unit_summaries_resume_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`
    outlineStage.value = 3

    try {
      const requestData = {
        content_type: toBackendContentType(type.value),
        global_outline: globalOutlineContent.value,
        unit_count: unitCount,
        series_type: null,
        episode_duration_range: null,
        provider: null,
        model: null,
        temperature: 0.3,  // 降低到0.3，减少创造性，增强对全局大纲的遵循性（v2.5）
        enable_quality_control: true,
        qc_mode: 'auto',
        existing_content: generatedContent.value || '',
        existing_parsed: unitSummaries.value,
        start_from_unit: startFrom,
        project_id: generationId?.value || null,  // [2026-05-05] 传递project_id使后端能保存locked_chapters
        title_style: titleStyleData.value.styleId || null,
        title_style_name: titleStyleData.value.styleName || null,
      }

      console.log(`[handleResumeUnitSummaries] 续生成参数:`)
      console.log(`  - 已有: ${existingCount}章`)
      console.log(`  - 目标: ${unitCount}章`)
      console.log(`  - 起始: 第${startFrom}章`)
      console.log(`  - 剩余: ${remainingCount}章`)

      const result = await generateApi.generateUnitSummariesStream(
        requestData,
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
          generatedContent.value = newContent
          if (message) {
            ElMessage.success(message)
          }
        }
      )

      if (result && !result.cancelled) {
        const allParsed = parseUnitSummariesFromContent(result.content, toBackendContentType(type.value))
        const mergedSummaries = { ...unitSummaries.value }
        for (const [num, unit] of Object.entries(allParsed)) {
          if (!mergedSummaries[num]) {
            mergedSummaries[num] = unit
          } else if (allParsed[num].full_content && allParsed[num].full_content.length > (mergedSummaries[num].full_content?.length || 0)) {
            mergedSummaries[num] = unit
          }
        }
        unitSummaries.value = mergedSummaries
        const allChapterTexts = Object.keys(mergedSummaries)
          .sort((a, b) => parseInt(a) - parseInt(b))
          .map(num => mergedSummaries[num].full_content || mergedSummaries[num].summary)
          .filter(Boolean)
        generatedContent.value = allChapterTexts.join('\n\n')
        outlineStage.value = 4

        const newCount = Object.keys(mergedSummaries).length
        if (newCount >= unitCount) {
          ElMessage.success(`续生成完成！全部 ${unitCount} 章已生成`)
        } else {
          ElMessage.warning(`续生成完成，当前共 ${newCount}/${unitCount} 章。如需继续，请再次点击续生成。`)
        }
      } else if (result && result.cancelled) {
        ElMessage.info('续生成已取消')
        if (result.content) {
          const partialParsed = parseUnitSummariesFromContent(result.content, toBackendContentType(type.value))
          const mergedSummaries = { ...unitSummaries.value }
          for (const [num, unit] of Object.entries(partialParsed)) {
            if (!mergedSummaries[num]) {
              mergedSummaries[num] = unit
            }
          }
          unitSummaries.value = mergedSummaries
          const allChapterTexts = Object.keys(mergedSummaries)
            .sort((a, b) => parseInt(a) - parseInt(b))
            .map(num => mergedSummaries[num].full_content || mergedSummaries[num].summary)
            .filter(Boolean)
          generatedContent.value = allChapterTexts.join('\n\n')
          outlineStage.value = 4
        }
      }
    } catch (error) {
      console.error('续生成失败:', error)
      ElMessage.error('续生成失败：' + (error.message || '未知错误'))
      if (Object.keys(unitSummaries.value).length > 0) {
        outlineStage.value = 4
      } else {
        outlineStage.value = 2
      }
    } finally {
      unitSummariesGenerating.value = false
      currentSessionId.value = null
    }
  }

  // 接续生成(兼容旧版入口，转发到 handleResumeUnitSummaries)
  async function handleContinueGeneration() {
    await handleResumeUnitSummaries()
  }

  // ==================== 从后端断点信息续生成 ====================

  async function handleResumeUnitSummariesFromBackend() {
    const backendResumeInfo = deps.backendResumeInfo
    if (!backendResumeInfo?.value?.can_resume) {
      ElMessage.warning('没有可续生成的断点信息')
      return
    }

    if (unitSummariesGenerating.value) {
      ElMessage.warning('正在生成中，请稍候...')
      return
    }

    const { existing_count, expected_count, start_from_unit, remaining_count, global_outline, existing_parsed, existing_content } = backendResumeInfo.value

    // 确认对话框
    try {
      await ElMessageBox.confirm(
        `当前已生成 ${existing_count} 章，目标 ${expected_count} 章。\n将从第 ${start_from_unit} 章继续生成剩余 ${remaining_count} 章。\n\n已有内容不会被清除，续生成内容将与前文自然衔接。`,
        '断点续生成',
        {
          confirmButtonText: '开始续生成',
          cancelButtonText: '取消',
          type: 'info'
        }
      )
    } catch {
      return  // 用户取消
    }

    // 恢复后端数据到前端状态
    globalOutlineContent.value = global_outline || globalOutlineContent.value
    unitSummaries.value = existing_parsed || unitSummaries.value
    generatedContent.value = existing_content || generatedContent.value
    outlineStage.value = 4
    showResult.value = true

    unitSummariesGenerating.value = true
    currentSessionId.value = `unit_summaries_resume_backend_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`

    try {
      const requestData = {
        content_type: toBackendContentType(type.value),
        global_outline: global_outline,
        unit_count: expected_count,
        series_type: null,
        episode_duration_range: null,
        provider: null,
        model: null,
        temperature: 0.3,  // 降低到0.3，减少创造性，增强对全局大纲的遵循性（v2.5）
        enable_quality_control: true,
        qc_mode: 'auto',
        existing_content: existing_content || '',
        existing_parsed: existing_parsed,
        start_from_unit: start_from_unit,
        project_id: generationId?.value || null,  // [2026-05-05] 传递project_id使后端能保存locked_chapters
        title_style: titleStyleData.value.styleId || null,
        title_style_name: titleStyleData.value.styleName || null,
      }

      console.log(`[handleResumeUnitSummariesFromBackend] 续生成参数:`)
      console.log(`  - 已有: ${existing_count}章`)
      console.log(`  - 目标: ${expected_count}章`)
      console.log(`  - 起始: 第${start_from_unit}章`)
      console.log(`  - 剩余: ${remaining_count}章`)

      const result = await generateApi.generateUnitSummariesStream(
        requestData,
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
          generatedContent.value = newContent
          if (message) {
            ElMessage.success(message)
          }
        }
      )

      if (result && !result.cancelled) {
        const allParsed = parseUnitSummariesFromContent(result.content, toBackendContentType(type.value))
        const mergedSummaries = { ...unitSummaries.value }
        for (const [num, unit] of Object.entries(allParsed)) {
          if (!mergedSummaries[num]) {
            mergedSummaries[num] = unit
          } else if (allParsed[num].full_content && allParsed[num].full_content.length > (mergedSummaries[num].full_content?.length || 0)) {
            mergedSummaries[num] = unit
          }
        }
        unitSummaries.value = mergedSummaries
        const allChapterTexts = Object.keys(mergedSummaries)
          .sort((a, b) => parseInt(a) - parseInt(b))
          .map(num => mergedSummaries[num].full_content || mergedSummaries[num].summary)
          .filter(Boolean)
        generatedContent.value = allChapterTexts.join('\n\n')
        outlineStage.value = 4

        const newCount = Object.keys(mergedSummaries).length
        if (newCount >= expected_count) {
          ElMessage.success(`续生成完成！全部 ${expected_count} 章已生成`)
        } else {
          ElMessage.warning(`续生成完成，当前共 ${newCount}/${expected_count} 章。如需继续，请再次点击续生成。`)
        }

        // 清空后端断点信息（已完成续生成）
        backendResumeInfo.value = null
      } else if (result && result.cancelled) {
        ElMessage.info('续生成已取消')
        if (result.content) {
          const partialParsed = parseUnitSummariesFromContent(result.content, toBackendContentType(type.value))
          const mergedSummaries = { ...unitSummaries.value }
          for (const [num, unit] of Object.entries(partialParsed)) {
            if (!mergedSummaries[num]) {
              mergedSummaries[num] = unit
            }
          }
          unitSummaries.value = mergedSummaries
          const allChapterTexts = Object.keys(mergedSummaries)
            .sort((a, b) => parseInt(a) - parseInt(b))
            .map(num => mergedSummaries[num].full_content || mergedSummaries[num].summary)
            .filter(Boolean)
          generatedContent.value = allChapterTexts.join('\n\n')
          outlineStage.value = 4
        }
      }
    } catch (error) {
      console.error('续生成失败:', error)
      ElMessage.error('续生成失败：' + (error.message || '未知错误'))
      if (Object.keys(unitSummaries.value).length > 0) {
        outlineStage.value = 4
      } else {
        outlineStage.value = 2
      }
    } finally {
      unitSummariesGenerating.value = false
      currentSessionId.value = null
    }
  }

  // ==================== 从指定单元开始生成 ====================

  function openStartUnitDialog() {
    const formChapterCount = type.value === 'novel'
      ? parseInt(form.value.chapter_count) || null
      : parseInt(form.value.episode_count) || null

    const outlineChapterCount = formChapterCount ? null : parseChapterCountFromOutline(globalOutlineContent.value)

    const unitCount = formChapterCount || outlineChapterCount || (type.value === 'novel' ? 50 : 24)

    startFromUnit.value = Math.min(startFromUnit.value, unitCount)
    showStartUnitDialog.value = true
  }

  async function handleGenerateFromUnit() {
    if (!globalOutlineContent.value) {
      ElMessage.warning('请先导入或生成全局大纲')
      return
    }

    const formChapterCount = type.value === 'novel'
      ? parseInt(form.value.chapter_count) || null
      : parseInt(form.value.episode_count) || null

    const outlineChapterCount = formChapterCount ? null : parseChapterCountFromOutline(globalOutlineContent.value)

    const unitCount = formChapterCount || outlineChapterCount || (type.value === 'novel' ? 50 : 24)

    console.log(`[GenerateForm.handleGenerateFromUnit] 章节数: 表单=${formChapterCount || '未填写'}, 大纲=${outlineChapterCount || '未找到'}, 最终=${unitCount}`)

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
          content_type: toBackendContentType(type.value),
          global_outline: modifiedOutline,
          unit_count: unitCount,
          series_type: null,
          episode_duration_range: null,
          provider: null,
          model: null,
          temperature: 0.3,  // 降低到0.3，减少创造性，增强对全局大纲的遵循性（v2.5）
          enable_quality_control: true,
          qc_mode: 'auto',
          existing_content: generatedContent.value || '',
          existing_parsed: unitSummaries.value,
          start_from_unit: startFromUnit.value,
          project_id: generationId?.value || null,  // [2026-05-05] 传递project_id使后端能保存locked_chapters
          title_style: titleStyleData.value.styleId || null,
          title_style_name: titleStyleData.value.styleName || null,
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
          generatedContent.value = newContent
          ElMessage.success(message || '内容已更新')
        }
      )

      if (result && !result.cancelled) {
        const newUnits = parseUnitSummariesFromContent(result.content, toBackendContentType(type.value))
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

  return {
    handleGenerateUnitSummaries,
    performLogicCheck,
    cancelUnitSummariesGeneration,
    handleResumeUnitSummaries,
    handleContinueGeneration,
    handleResumeUnitSummariesFromBackend,
    openStartUnitDialog,
    handleGenerateFromUnit
  }
}
