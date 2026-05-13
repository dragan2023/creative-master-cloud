/**
 * 修订模式 composable
 * 管理修订模式的进入/退出、本地修订、远程修订和最终确认逻辑
 */
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
    buildOutlineInputParams
  } = deps

  /**
   * 进入修订模式
   */
  function startRevision() {
    // 检查知识库修正是否正在进行中
    if (knowledgeRevising.value) {
      ElMessage.warning('知识库修正进行中，请稍候...')
      return
    }

    isRevisionMode.value = true
    currentRevisionRound.value = 0
    revisionMessages.value = []
    revisionHistory.value = []

    // 两阶段大纲生成：修订全局大纲
    if (useTwoStageMode.value) {
      revisionContent.value = globalOutlineContent.value || ''
      generationId.value = null
      console.log('[Revision] Starting revision for global outline, content length:', globalOutlineContent.value?.length || 0)
    } else {
      // 普通模式：使用生成的内容
      revisionContent.value = generatedContent.value
      generationId.value = currentGenerationId.value
      console.log('[Revision] Starting revision for generated content, generationId:', generationId.value)
    }

    const modeText = useTwoStageMode.value ? '全局大纲修订模式' : '修订模式'
    ElMessage.info(`已进入${modeText},请输入修改意见`)
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
        '退出后将保留当前修改后的内容,是否继续?',
        '提示',
        {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        }
      ).then(() => {
        generatedContent.value = revisionContent.value
        isRevisionMode.value = false
      }).catch(() => {
        // 用户取消
      })
    } else {
      isRevisionMode.value = false
    }
  }

  return {
    startRevision,
    submitRevision,
    finalizeContent,
    exitRevision
  }
}
