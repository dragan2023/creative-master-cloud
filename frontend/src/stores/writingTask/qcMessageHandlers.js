/**
 * 多Agent协作文学作品生成系统 - 写作任务状态管理（质控消息处理部分）
 *
 * 模块: writing-engine
 * 文件: writingTask/qcMessageHandlers.js
 * 功能: 处理WebSocket质控类消息（unit_quality_control与content_qc_*批量质控），
 *       从websocket.js拆分而来，业务逻辑保持一致
 *
 * 创建时间: 2026-07-18（自websocket.js拆分）
 */

/**
 * 构造单元的quality_control记录（更新已有单元场景）
 * 保留版本字段保护逻辑：content_after_generation 永不因 revert 清除
 * @param {Object} qcData - WS消息中的质控数据
 * @param {Object} oldUnit - 现有单元对象
 * @returns {Object} 新的quality_control对象
 */
function buildQualityControlRecord(qcData, oldUnit) {
  const oldQC = oldUnit.quality_control || {}
  // v3.1: 质控状态为 'reverted' 时清除修正稿，显示退回初稿
  const isReverted = qcData.status === 'reverted'
  // [修复] 版本字段保护：WS消息可能不包含 content_after_generation
  // 优先WS值 → 回退旧quality_control → 回退单元顶层字段；初稿永久保留
  const preservedDraft = qcData.content_after_generation
    || oldQC.content_after_generation
    || oldUnit.content_after_generation
    || null

  return {
    status: qcData.status,
    score: qcData.score || 0,
    issues_count: qcData.issues_count || 0,
    fixed_count: qcData.fixed_count || 0,
    compliance_issue_count: qcData.compliance_issue_count || 0,
    message: qcData.message || '',
    report: qcData.report || null,
    issues: qcData.issues || [],
    fixes_applied: qcData.fixes_applied || [],
    original_content: qcData.original_content || null,
    fixed_content: isReverted ? null : (qcData.fixed_content || null),
    // v3.0: 六维度分数与版本内容
    dimension_scores: qcData.dimension_scores || {},
    change_list: qcData.change_list || [],
    context_summary: qcData.context_summary || '',
    content_after_generation: preservedDraft,
    content_after_qc_fix: isReverted ? null : (qcData.content_after_qc_fix || oldQC.content_after_qc_fix || null),
    content_after_self_revise: qcData.content_after_self_revise || oldQC.content_after_self_revise || null,
    updated_at: Date.now(),
    _from_ws: true // 标记数据来自WebSocket，优先级高于API数据
  }
}

/**
 * 质控修正完成/撤销后，同步单元的final_content与word_count
 * 确保WritingWorkbench页面实时显示修正后的正文内容
 * @param {Object} unit - 目标单元对象（就地修改）
 * @param {Object} qcData - WS消息中的质控数据
 * @param {number} unitIndex - 单元索引（日志用）
 */
function syncUnitFinalContent(unit, qcData, unitIndex) {
  const isReverted = qcData.status === 'reverted'
  if (isReverted) {
    const revertedContent = qcData.reverted_content || qcData.original_content || ''
    unit.final_content = revertedContent
    unit.word_count = revertedContent.length
    console.log(
      '[WritingTask Store] 修正已撤销，恢复初稿: unit=%d, word_count=%d',
      unitIndex, revertedContent.length
    )
  } else if (qcData.fixed_content && qcData.status === 'completed') {
    unit.final_content = qcData.fixed_content
    unit.word_count = qcData.fixed_content.length
    console.log(
      '[WritingTask Store] 质控修正内容已同步: unit=%d, word_count=%d',
      unitIndex, qcData.fixed_content.length
    )
  }
}

/**
 * 构造带质控信息的新单元（单元尚未出现在列表中的场景）
 * @param {Object} qcData - WS消息中的质控数据
 * @param {number} unitIndex - 单元索引
 * @returns {Object} 新单元对象
 */
function buildUnitWithQualityControl(qcData, unitIndex) {
  const isReverted = qcData.status === 'reverted'
  const newUnit = {
    unit_index: unitIndex,
    unit_title: qcData.unit_title || `第${unitIndex}章`,
    status: qcData.status === 'running' ? 'processing' : 'completed',
    progress: qcData.status === 'running' ? 0 : 100,
    word_count: qcData.fixed_content ? qcData.fixed_content.length : 0,
    quality_control: {
      status: qcData.status,
      score: qcData.score || 0,
      issues_count: qcData.issues_count || 0,
      fixed_count: qcData.fixed_count || 0,
      compliance_issue_count: qcData.compliance_issue_count || 0,
      message: qcData.message || '',
      report: qcData.report || null,
      issues: qcData.issues || [],
      fixes_applied: qcData.fixes_applied || [],
      original_content: qcData.original_content || null,
      fixed_content: isReverted ? null : (qcData.fixed_content || null),
      dimension_scores: qcData.dimension_scores || {},
      change_list: qcData.change_list || [],
      context_summary: qcData.context_summary || '',
      content_after_generation: qcData.content_after_generation || null,
      content_after_qc_fix: isReverted ? null : (qcData.content_after_qc_fix || null),
      content_after_self_revise: qcData.content_after_self_revise || null,
      updated_at: Date.now(),
      _from_ws: true
    }
  }
  // 质控修正完成/撤销后，同步设置 final_content
  if (isReverted) {
    newUnit.final_content = qcData.reverted_content || qcData.original_content || ''
  } else if (qcData.fixed_content && qcData.status === 'completed') {
    newUnit.final_content = qcData.fixed_content
  }
  return newUnit
}

/**
 * 处理 unit_quality_control 消息（v2.0实时质控）
 * @param {Object} state - 写作任务状态引用集合
 * @param {Object} qcData - msg.data
 */
export function applyUnitQualityControl(state, qcData) {
  if (!qcData) return
  console.log('[WritingTask Store] 收到unit_quality_control消息:', JSON.stringify(qcData).substring(0, 200))

  const unitIndex = qcData.unit_index
  const unitIdx = state.units.value.findIndex(u => u.unit_index === unitIndex)
  console.log('[WritingTask Store] 查找单元:', unitIndex, '找到索引:', unitIdx)

  if (unitIdx !== -1) {
    // 使用splice替换整个对象，确保Vue响应式系统能可靠检测到变化
    const oldUnit = state.units.value[unitIdx]
    const updatedUnit = {
      ...oldUnit,
      quality_control: buildQualityControlRecord(qcData, oldUnit)
    }
    syncUnitFinalContent(updatedUnit, qcData, unitIndex)
    state.units.value.splice(unitIdx, 1, updatedUnit)
    console.log('[WritingTask Store] 单元质控信息已更新(splice):', updatedUnit.quality_control)
  } else {
    // 单元尚未在列表中(可能unit_progress消息还未到达)，创建带质控信息的新单元
    console.log('[WritingTask Store] 单元未找到，创建带质控信息的新单元:', unitIndex)
    state.units.value.push(buildUnitWithQualityControl(qcData, unitIndex))
  }

  console.log(
    `[WritingTask Store] 单元质控更新完成: unit=${unitIndex}, ` +
    `status=${qcData.status}, score=${qcData.score || 0}, ` +
    `units总数=${state.units.value.length}`
  )
}

/**
 * 处理 content_qc_started 消息（v2.2批量质控开始）
 */
export function applyContentQcStarted(state, msgData) {
  console.log('[WritingTask Store] 批量质控开始:', msgData)
  if (msgData && state.batchQCProgress) {
    state.batchQCProgress.value = {
      status: 'running',
      current: 0,
      total: msgData.total || 0,
      currentUnit: null,
      startedAt: Date.now()
    }
  }
}

/**
 * 处理 content_qc_progress 消息（v2.2批量质控进度更新）
 */
export function applyContentQcProgress(state, msgData) {
  console.log('[WritingTask Store] 批量质控进度:', msgData)
  if (!msgData || !state.batchQCProgress) return
  const progressData = msgData
  state.batchQCProgress.value = {
    status: 'running',
    current: progressData.current || 0,
    total: progressData.total || state.batchQCProgress.value?.total || 0,
    currentUnit: progressData.current_unit,
    percent: progressData.progress || Math.round((progressData.current / progressData.total) * 100)
  }

  // 更新当前单元的质控状态为running
  if (progressData.current_unit) {
    const unitIdx = state.units.value.findIndex(u => u.unit_index === progressData.current_unit)
    if (unitIdx !== -1) {
      const oldUnit = state.units.value[unitIdx]
      state.units.value.splice(unitIdx, 1, {
        ...oldUnit,
        quality_control: {
          ...oldUnit.quality_control,
          status: 'running',
          updated_at: Date.now(),
          _from_ws: true
        }
      })
    }
  }
}

/**
 * 处理 content_qc_unit_complete 消息（批量任务中的单个单元质控完成）
 */
export function applyContentQcUnitComplete(state, msgData) {
  console.log('[WritingTask Store] 批量任务单元质控完成:', msgData)
  if (!msgData) return
  const unitIndex = msgData.unit_index || msgData.data?.unit_index
  const status = msgData.status || 'success'

  const unitIdx = state.units.value.findIndex(u => u.unit_index === unitIndex)
  if (unitIdx === -1) return
  const oldUnit = state.units.value[unitIdx]
  const qcUpdate = {
    status: status === 'success' ? 'completed' : 'failed',
    updated_at: Date.now(),
    _from_ws: true
  }
  if (status === 'success') {
    qcUpdate.score = msgData.score || msgData.data?.score || 0
    qcUpdate.issues_count = msgData.issues_count || msgData.data?.issues_count || 0
    qcUpdate.fixed_count = msgData.fixed_count || msgData.data?.fixed_count || 0
  }
  state.units.value.splice(unitIdx, 1, {
    ...oldUnit,
    quality_control: {
      ...oldUnit.quality_control,
      ...qcUpdate
    }
  })
}

/**
 * 处理 content_qc_batch_complete 消息（批量质控完成）
 */
export function applyContentQcBatchComplete(state, msgData) {
  console.log('[WritingTask Store] 批量质控完成:', msgData)
  if (!state.batchQCProgress) return
  const summaryData = msgData || {}
  state.batchQCProgress.value = {
    status: 'completed',
    current: summaryData.completed || summaryData.total || 0,
    total: summaryData.total || 0,
    currentUnit: null,
    completedUnits: summaryData.completed_units || [],
    failedUnits: summaryData.failed_units || [],
    avgScore: summaryData.avg_score || 0,
    completedAt: Date.now()
  }
}
