/**
 * 修订模式 composable
 * 管理修订模式的进入/退出、本地修订、远程修订和最终确认逻辑
 */
import { ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { revisionApi, generateApi } from '@/api'
import { applyDiffInstructions, validateDiffInstructions } from '@/utils/diffApplier'

export function useRevisionMode(deps) {
  const {
    type,
    form,
    useTwoStageMode,
    isRevisionMode,
    currentRevisionRound,
    revisionInput,
    revising,
    revisionContent,
    revisionMessages,
    revisionHistory,
    generationId,
    currentGenerationId,
    globalOutlineContent,
    generatedContent,
    knowledgeRevising,
    buildOutlineInputParams,
    unitSummaries  // 单元概述数据（用于单元概述对话修订）
  } = deps

  // 修订模式类型：'global' | 'units'
  const revisionMode = ref('global')

  /**
   * 标准化单元概述的 ID（确保所有单元都有正确的 unit_number）
   * 通过正则匹配 "第X章/集/场" 从 title 或 full_content 中提取编号
   */
  function normalizeUnitSummariesIds() {
    if (!unitSummaries?.value || typeof unitSummaries.value !== 'object') return

    const typeVal = type.value
    const unitPatterns = {
      novel: /第(\d+)章/,
      series: /第(\d+)集/,
      movie: /第(\d+)场/
    }

    // 根据内容类型选择匹配模式，回退检测
    let pattern
    if (typeVal === 'novel') pattern = unitPatterns.novel
    else if (typeVal === 'series-outline' || typeVal === 'series_outline') pattern = unitPatterns.series
    else if (typeVal === 'movie-outline' || typeVal === 'movie_outline') pattern = unitPatterns.movie
    else pattern = unitPatterns.novel // default to novel

    const newDict = {}
    for (const [key, unit] of Object.entries(unitSummaries.value)) {
      if (!unit || typeof unit !== 'object') continue

      let unitNum = unit.unit_number

      // 如果 unit_number 缺失，从 title 或 full_content 中提取
      if (!unitNum) {
        const searchText = unit.title || unit.full_content || unit.summary || ''
        const match = searchText.match(pattern)
        if (match) {
          unitNum = parseInt(match[1])
        }
      }

      // 如果仍然没有，尝试从 key 推断
      if (!unitNum && !isNaN(parseInt(key))) {
        unitNum = parseInt(key)
      }

      if (unitNum) {
        unit.unit_number = unitNum
        newDict[String(unitNum)] = { ...unit }
      } else {
        // 保留原始 key
        newDict[key] = unit
      }
    }

    // 更新为标准化后的字典（使用 unit_number 作为 key）
    if (Object.keys(newDict).length > 0) {
      unitSummaries.value = newDict
      console.log('[NormalizeIds] 单元概述 ID 已标准化，单元数:', Object.keys(newDict).length)
    }
  }

  /**
   * 进入修订模式
   * @param {string} mode - 'global' 全局大纲 | 'units' 单元概述
   */
  function startRevision(mode = 'global') {
    // 检查知识库修正是否正在进行中
    if (knowledgeRevising.value) {
      ElMessage.warning('知识库修正进行中，请稍候...')
      return
    }

    isRevisionMode.value = true
    currentRevisionRound.value = 0
    revisionMessages.value = []
    revisionHistory.value = []
    revisionMode.value = mode

    if (mode === 'units') {
      // 先标准化 ID（确保所有单元都有正确的 unit_number）
      normalizeUnitSummariesIds()
      // 单元概述对话修订模式：构建格式化文本用于预览
      const unitData = unitSummaries?.value || {}
      const unitsList = Object.entries(unitData).sort((a, b) => parseInt(a[0]) - parseInt(b[0]))
      if (unitsList.length === 0) {
        ElMessage.warning('没有可修订的单元概述')
        isRevisionMode.value = false
        return
      }
      // 构建纯文本用于预览显示
      const lines = []
      const typeVal = type.value
      const unitLabel = typeVal === 'novel' ? '章' :
        (typeVal === 'movie-outline' || typeVal === 'movie_outline') ? '场' : '集'
      for (const [, unit] of unitsList) {
        const title = unit.title || ''
        const fullContent = unit.full_content || unit.summary || ''
        lines.push(`### 第${unit.unit_number || '?'}${unitLabel}：${title}\n\n${fullContent}`)
      }
      revisionContent.value = lines.join('\n\n---\n\n')
      generationId.value = null
      console.log('[Revision] Starting unit summaries revision, units count:', unitsList.length)
    } else if (useTwoStageMode.value) {
      // 两阶段大纲生成：修订全局大纲
      revisionContent.value = globalOutlineContent.value || ''
      generationId.value = null
      console.log('[Revision] Starting revision for global outline, content length:', globalOutlineContent.value?.length || 0)
    } else {
      // 普通模式：使用生成的内容
      revisionContent.value = generatedContent.value
      generationId.value = currentGenerationId.value
      console.log('[Revision] Starting revision for generated content, generationId:', generationId.value)
    }

    const modeTextMap = { 'units': '单元概述修订模式', 'global': useTwoStageMode.value ? '全局大纲修订模式' : '修订模式' }
    const modeText = modeTextMap[mode] || '修订模式'
    ElMessage.info(`已进入${modeText}，请输入修改意见`)
  }

  /**
   * 提交修订
   */
  async function submitRevision(userFeedback) {
    console.log('[Revision] submitRevision 被调用, userFeedback:', userFeedback)
    console.log('[Revision] userFeedback 类型:', typeof userFeedback)
    console.log('[Revision] userFeedback 内容:', JSON.stringify(userFeedback))
    
    // 修复：支持对象格式 { input: '...', files: [...] } 和字符串格式
    let feedback
    if (typeof userFeedback === 'string') {
      feedback = userFeedback
      console.log('[Revision] 使用字符串格式, feedback:', feedback)
    } else if (userFeedback && typeof userFeedback === 'object') {
      // RevisionDialog 传递的是对象格式
      feedback = userFeedback.input || ''
      console.log('[Revision] 使用对象格式, feedback:', feedback)
    } else {
      // 从 revisionInput 读取（兼容旧版）
      feedback = revisionInput.value
      console.log('[Revision] 使用revisionInput, feedback:', feedback)
    }

    console.log('[Revision] 最终 feedback:', feedback)
    console.log('[Revision] feedback.trim():', feedback.trim())
    console.log('[Revision] !feedback.trim():', !feedback.trim())

    if (!feedback.trim()) {
      console.warn('[Revision] feedback 为空，弹出警告')
      ElMessage.warning('请输入修改意见')
      return
    }

    console.log('[Revision] Submitting revision, feedback:', feedback.substring(0, 50))

    // 单元概述对话修订：调用专属流式API
    if (revisionMode.value === 'units') {
      submitUnitSummariesRevision(feedback)
      return
    }

    // 两阶段大纲生成：使用本地简单修订（不调用后端API）
    if (useTwoStageMode.value) {
      submitLocalRevision(feedback)
      return
    }

    // 普通模式：调用后端修订API
    await submitRemoteRevision(feedback)
  }

  /**
   * 本地修订（两阶段大纲生成使用）
   */
  async function submitLocalRevision(userFeedback) {
    revising.value = true

    const currentFeedback = userFeedback || revisionInput.value

    // 添加用户消息
    revisionMessages.value.push({
      role: 'user',
      content: currentFeedback,
      timestamp: new Date()
    })

    try {
      // [2026-05-12 修复] content_type 连字符→下划线映射（后端只认下划线格式）
      const contentTypeMap = { 'movie-outline': 'movie_outline', 'series-outline': 'series_outline' }
      const contentTypeForApi = contentTypeMap[type.value] || type.value

      await generateApi.reviseGlobalOutlineStream(
        {
          content_type: contentTypeForApi,
          current_content: revisionContent.value,
          user_feedback: currentFeedback,
          revision_history: revisionHistory.value.map(h => ({
            round: h.round_number,
            feedback: h.user_feedback,
            summary: h.diff_summary
          })),
          input_params: buildOutlineInputParams(),
          provider: null,
          temperature: 0.7
        },
        (fullContent, chunk) => {
          console.log('[Revision] onMessage called, fullContent length:', fullContent?.length, 'chunk:', chunk?.substring(0, 50))

          if (fullContent) {
            revisionContent.value = fullContent

            // 两阶段模式：同步更新全局大纲显示
            if (useTwoStageMode.value) {
              globalOutlineContent.value = fullContent
            }

            console.log('[Revision] Content updated, length:', revisionContent.value.length)
          }
        },
        (event) => {
          console.log('[Revision] Workflow event:', event)
          if (event.type === 'diff_complete') {
            try {
              const diffInstructions = event.data

              revisionHistory.value.push({
                round_number: currentRevisionRound.value,
                user_feedback: currentFeedback,
                diff_summary: diffInstructions.summary || '已修改'
              })

              currentRevisionRound.value++
              revisionInput.value = ''

              revisionMessages.value.push({
                role: 'assistant',
                content: diffInstructions.summary || '修改完成'
              })

              ElMessage.success(`第${currentRevisionRound.value}轮修订完成`)
            } catch (e) {
              console.error('[Revision] Parse diff_complete failed:', e)
              ElMessage.error('解析修订结果失败')
            }
          } else if (event.type === 'error') {
            console.error('[Revision] Revision error:', event.data)
            ElMessage.error('修订失败: ' + (event.data?.data || event.data?.message || '未知错误'))
          }
        },
        () => {
          console.log('[Revision] Stream started')
        },
        null
      )
    } catch (error) {
      console.error('[Revision] submitLocalRevision error:', error)
      ElMessage.error('修订失败: ' + (error.message || '未知错误'))
    } finally {
      revising.value = false
    }
  }

  /**
   * 单元概述对话修订（调用流式API，LLM输出改动单元的JSON）
   */
  async function submitUnitSummariesRevision(userFeedback) {
    revising.value = true

    const currentFeedback = userFeedback || revisionInput.value

    // 添加用户消息
    revisionMessages.value.push({
      role: 'user',
      content: currentFeedback,
      timestamp: new Date()
    })

    // 添加临时加载消息（在AI回复之前显示）
    const loadingMsgIdx = revisionMessages.value.length
    revisionMessages.value.push({
      role: 'assistant',
      content: 'AI正在分析修订...',
      loading: true,
      timestamp: new Date()
    })

    try {
      const contentTypeMap = { 'movie-outline': 'movie_outline', 'series-outline': 'series_outline' }
      const contentTypeForApi = contentTypeMap[type.value] || type.value

      await generateApi.reviseUnitSummariesStream(
        {
          content_type: contentTypeForApi,
          global_outline: globalOutlineContent.value || '',
          unit_summaries: unitSummaries?.value || {},
          user_feedback: currentFeedback,
          revision_history: revisionHistory.value.map(h => ({
            round: h.round_number,
            feedback: h.user_feedback,
            summary: h.diff_summary
          })),
          provider: null,
          temperature: 0.7
        },
        (fullContent, chunk) => {
          console.log('[UnitSummariesRevise] onContent, fullContent length:', fullContent?.length)
          // 单元概述修订模式：LLM 输出可读的 markdown 格式（修改后的单元全文）
          // 流式更新预览区，让用户实时看到修订内容（参照全局大纲修订的表现形式）
          revisionContent.value = fullContent
        },
        (event) => {
          console.log('[UnitSummariesRevise] onDone event:', event)

          // 移除临时加载消息
          if (loadingMsgIdx < revisionMessages.value.length) {
            revisionMessages.value.splice(loadingMsgIdx, 1)
          }

          if (event.type === 'diff_complete') {
            const eventData = event.data

            // 保存修订历史
            revisionHistory.value.push({
              round_number: currentRevisionRound.value,
              user_feedback: currentFeedback,
              diff_summary: eventData.summary || '已修改'
            })

            currentRevisionRound.value++
            revisionInput.value = ''

            // 如果有解析后的 revisions，即时应用到 unitSummaries
            if (eventData.revisions && typeof eventData.revisions === 'object') {
              const appliedCount = applyUnitSummariesRevision(eventData.revisions)
              // 修订后重新标准化 ID
              normalizeUnitSummariesIds()
              // 刷新预览区内容（显示修订后的单元概述）
              refreshUnitSummariesPreview()

              revisionMessages.value.push({
                role: 'assistant',
                content: `${eventData.summary || '修订完成'}（已更新 ${appliedCount} 个单元）`
              })
            } else {
              console.warn('[UnitSummariesRevise] diff_complete 中无有效 revisions 数据:', eventData)
              revisionMessages.value.push({
                role: 'assistant',
                content: eventData.summary || '修订完成，但未能解析到具体修改内容，请重试'
              })
            }

            ElMessage.success(`第${currentRevisionRound.value}轮修订完成`)
          } else if (event.type === 'error') {
            console.error('[UnitSummariesRevise] Revision error:', event.data)
            revisionMessages.value.push({
              role: 'assistant',
              content: '修订失败: ' + (event.data?.data || event.data?.message || '未知错误')
            })
            ElMessage.error('修订失败: ' + (event.data?.data || event.data?.message || '未知错误'))
          }
        },
        (error) => {
          console.error('[UnitSummariesRevise] onError:', error)
          // 移除临时加载消息
          if (loadingMsgIdx < revisionMessages.value.length) {
            revisionMessages.value.splice(loadingMsgIdx, 1)
          }
          revisionMessages.value.push({
            role: 'assistant',
            content: '修订请求失败: ' + (error.message || '未知错误')
          })
        }
      )
    } catch (error) {
      console.error('[UnitSummariesRevise] submitUnitSummariesRevision error:', error)
      // 移除临时加载消息
      if (loadingMsgIdx < revisionMessages.value.length) {
        revisionMessages.value.splice(loadingMsgIdx, 1)
      }
      revisionMessages.value.push({
        role: 'assistant',
        content: '修订失败: ' + (error.message || '未知错误')
      })
      ElMessage.error('修订失败: ' + (error.message || '未知错误'))
    } finally {
      revising.value = false
    }
  }

  /**
   * 将 LLM 返回的 revisions 合并到 unitSummaries 字典中
   * @param {Object} revisions - { "1": { summary, full_content, reason }, ... }
   */
  function applyUnitSummariesRevision(revisions) {
    if (!unitSummaries?.value) {
      console.warn('[UnitSummariesRevise] unitSummaries 不存在，无法应用修订')
      return 0
    }

    let appliedCount = 0
    for (const [unitNum, revisionData] of Object.entries(revisions)) {
      if (!revisionData || typeof revisionData !== 'object') continue

      // 尝试多种键格式匹配（字符串 "1" 和数字 1）
      let existing = unitSummaries.value[unitNum]
      if (!existing && !isNaN(parseInt(unitNum))) {
        // 尝试数字键
        existing = unitSummaries.value[parseInt(unitNum)]
        if (!existing) {
          // 尝试字符串键
          existing = unitSummaries.value[String(unitNum)]
        }
      }
      if (!existing) {
        console.warn(`[UnitSummariesRevise] 单元 ${unitNum} 不存在于当前数据中，跳过。当前键: ${Object.keys(unitSummaries.value).join(', ')}`)
        continue
      }

      // 合并修订数据（保留原有字段，用新值覆盖）
      const merged = { ...existing }
      if (revisionData.summary) {
        merged.summary = revisionData.summary
      }
      if (revisionData.full_content) {
        merged.full_content = revisionData.full_content
      }
      if (revisionData.title) {
        merged.title = revisionData.title
      }
      // 记录修订信息
      merged.revision_reason = revisionData.reason || ''
      merged.revised_at = new Date().toISOString()

      unitSummaries.value[unitNum] = merged
      appliedCount++
    }

    console.log(`[UnitSummariesRevise] 已应用 ${appliedCount} 个单元的修订，当前 keys: ${Object.keys(unitSummaries.value).join(', ')}`)
    return appliedCount
  }

  /**
   * 从 unitSummaries 构建格式化的 markdown 全文
   * @returns {string} 格式化后的 markdown 文本
   */
  function buildFormattedUnitSummariesText() {
    if (!unitSummaries?.value) return ''
    const unitData = unitSummaries.value
    const unitsList = Object.entries(unitData).sort((a, b) => parseInt(a[0]) - parseInt(b[0]))
    if (unitsList.length === 0) return ''

    const lines = []
    const typeVal = type.value
    const unitLabel = typeVal === 'novel' ? '章' :
      (typeVal === 'movie-outline' || typeVal === 'movie_outline') ? '场' : '集'
    for (const [, unit] of unitsList) {
      const title = unit.title || ''
      const fullContent = unit.full_content || unit.summary || ''
      lines.push(`### 第${unit.unit_number || '?'}${unitLabel}：${title}\n\n${fullContent}`)
    }
    return lines.join('\n\n---\n\n')
  }

  /**
   * 刷新单元概述预览区内容（用于修订后更新显示）
   * 同时同步 generatedContent，确保主显示区（ResultViewer）也更新
   */
  function refreshUnitSummariesPreview() {
    const formatted = buildFormattedUnitSummariesText()
    if (!formatted) return

    // 更新对话修订预览区
    revisionContent.value = formatted
    // 同步更新 generatedContent，确保确认修订后主显示区展示最新内容
    if (generatedContent) {
      generatedContent.value = formatted
    }
    console.log('[UnitSummariesRevise] 预览区已刷新，generatedContent 已同步更新')
  }

  /**
   * 远程修订（普通模式使用后端API）
   */
  async function submitRemoteRevision(feedback) {
    if (!generationId.value) {
      ElMessage.error('未找到生成记录ID')
      return
    }

    const currentFeedback = feedback || revisionInput.value

    console.log('[Revision] Starting remote revision, generationId:', generationId.value)
    console.log('[Revision] Revision round:', currentRevisionRound.value + 1)
    console.log('[Revision] User feedback:', currentFeedback)

    revising.value = true
    currentRevisionRound.value++

    // 添加用户消息
    revisionMessages.value.push({
      role: 'user',
      content: currentFeedback
    })

    // 添加超时机制
    let timeoutId = null
    const timeoutPromise = new Promise((_, reject) => {
      timeoutId = setTimeout(() => {
        reject(new Error('修订请求超时（60秒），请检查网络连接或后端服务'))
      }, 60000)
    })

    try {
      // 显示"正在生成"提示
      revisionMessages.value.push({
        role: 'assistant',
        content: '正在生成修改指令...'
      })

      console.log('[Revision] Calling revisionApi.revise()')

      await Promise.race([
        revisionApi.revise(
          generationId.value,
          {
            generation_id: generationId.value,
            user_feedback: currentFeedback,
            current_content: revisionContent.value,
            original_params: form.value,
            module: type.value,
            round_number: currentRevisionRound.value
          },
          (chunk) => {
            console.log('[Revision] Received SSE chunk:', chunk.substring(0, 100))
            if (chunk.startsWith('event: diff_chunk\ndata: ')) {
              try {
                const jsonStr = chunk.split('data: ', 2)[1].trim()
                if (jsonStr) {
                  const data = JSON.parse(jsonStr)
                  console.log('[Revision] Received diff_chunk')
                }
              } catch (e) {
                console.error('Parse diff_chunk failed:', e)
              }
            } else if (chunk.startsWith('event: diff_complete\ndata: ')) {
              try {
                const jsonStr = chunk.split('data: ', 2)[1].trim()
                if (jsonStr) {
                  const diffInstructions = JSON.parse(jsonStr)
                  console.log('[Revision] Received diff_complete:', diffInstructions.summary)

                  if (!validateDiffInstructions(diffInstructions)) {
                    throw new Error('差异指令格式无效')
                  }

                  const newContent = applyDiffInstructions(
                    revisionContent.value,
                    diffInstructions
                  )

                  revisionContent.value = newContent

                  const lastMsgIndex = revisionMessages.value.length - 1
                  if (lastMsgIndex >= 0 &&
                      revisionMessages.value[lastMsgIndex].content === '正在生成修改指令...') {
                    revisionMessages.value.pop()
                  }

                  revisionMessages.value.push({
                    role: 'assistant',
                    content: diffInstructions.summary || '修改完成'
                  })

                  revisionHistory.value.push({
                    round_number: currentRevisionRound.value,
                    user_feedback: currentFeedback,
                    diff_summary: diffInstructions.summary
                  })

                  revisionInput.value = ''

                  ElMessage.success(`第${currentRevisionRound.value}轮修订完成`)
                }
              } catch (e) {
                console.error('Parse diff_complete failed:', e)
                ElMessage.error('解析差异指令失败')
              }
            } else if (chunk.startsWith('event: error\ndata: ')) {
              try {
                const jsonStr = chunk.split('data: ', 2)[1].trim()
                if (jsonStr) {
                  const data = JSON.parse(jsonStr)
                  throw new Error(data.data || data.message || '未知错误')
                }
              } catch (e) {
                console.error('Revision error:', e)
                ElMessage.error('修订失败: ' + e.message)
              }
            }
          },
          () => {
            console.log('[Revision] Stream completed')
            if (timeoutId) clearTimeout(timeoutId)
            revising.value = false
          },
          (error) => {
            console.error('[Revision] Stream error:', error)
            if (timeoutId) clearTimeout(timeoutId)
            revising.value = false
            ElMessage.error('修订失败: ' + (error.message || '未知错误'))
          }
        ),
        timeoutPromise
      ])

      console.log('[Revision] Revision completed successfully')
    } catch (error) {
      console.error('[Revision] Revision failed:', error)
      if (timeoutId) clearTimeout(timeoutId)
      revising.value = false
      ElMessage.error('修订失败: ' + error.message)
    }
  }

  /**
   * 最终确认内容
   */
  async function finalizeContent() {
    try {
      if (useTwoStageMode.value) {
        finalizeLocalContent()
        return
      }

      await finalizeRemoteContent()
    } catch (error) {
      console.error('最终确认失败:', error)
      ElMessage.error('最终确认失败: ' + error.message)
    }
  }

  /**
   * 本地最终确认（两阶段大纲生成使用）
   */
  function finalizeLocalContent() {
    if (revisionMode.value === 'units') {
      // 单元概述修订：修订结果已在每轮实时应用到 unitSummaries
      // 确保 generatedContent 与当前 unitSummaries 同步
      const formatted = buildFormattedUnitSummariesText()
      if (formatted && generatedContent) {
        generatedContent.value = formatted
      }
      isRevisionMode.value = false
      ElMessage.success('单元概述修订已保存')
      return
    }

    if (useTwoStageMode.value) {
      globalOutlineContent.value = revisionContent.value
      console.log('[Revision] Local finalize: global outline updated, length:', revisionContent.value.length)
    } else {
      generatedContent.value = revisionContent.value
    }

    isRevisionMode.value = false

    ElMessage.success('大纲已保存')
  }

  /**
   * 远程最终确认（普通模式使用后端API）
   */
  async function finalizeRemoteContent() {
    try {
      const result = await revisionApi.finalize(generationId.value, {
        generation_id: generationId.value,
        final_content: revisionContent.value,
        enable_knowledge_check: true,
        enable_self_reflection: true
      })

      if (result.code === 200) {
        ElMessage.success('最终优化完成!')

        revisionContent.value = result.data.final_content
        generatedContent.value = result.data.final_content

        isRevisionMode.value = false

        if (result.data.knowledge_issues && result.data.knowledge_issues.length > 0) {
          console.log('知识库问题:', result.data.knowledge_issues)
        }
        if (result.data.reflection_suggestions && result.data.reflection_suggestions.length > 0) {
          console.log('自反思建议:', result.data.reflection_suggestions)
        }
      } else {
        throw new Error(result.message || '最终确认失败')
      }
    } catch (error) {
      ElMessage.error('最终确认失败: ' + error.message)
    }
  }

  /**
   * 退出修订模式
   */
  function exitRevision() {
    if (revisionMessages.value.length > 0) {
      ElMessageBox.confirm(
        '退出后将保留当前修改后的内容，是否继续?',
        '提示',
        {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        }
      ).then(() => {
        if (revisionMode.value === 'units') {
          // 单元概述修订模式：修订结果已在每轮实时应用，直接退出
          isRevisionMode.value = false
        } else {
          generatedContent.value = revisionContent.value
          isRevisionMode.value = false
        }
      }).catch(() => {
        // 用户取消
      })
    } else {
      isRevisionMode.value = false
    }
  }

  return {
    revisionMode,
    startRevision,
    submitRevision,
    finalizeContent,
    exitRevision,
    applyUnitSummariesRevision
  }
}
