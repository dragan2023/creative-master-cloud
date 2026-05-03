/**
 * useContentQualityControl - 正文写作质控逻辑
 * 
 * 功能：
 * 1. 单单元质控检测与修正
 * 2. 批量质控检测与进度监控
 * 3. 选择性应用修正
 * 4. 撤销修正
 * 
 * 与单元概述质控(useQualityControl)完全独立，专注于正文内容的质量管控。
 */
import { ref, computed, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { api } from '@/api/_axios'

// ==================== 导出的常量 ====================

// 六维度定义
export const QC_DIMENSIONS = [
  { key: 'structure', name: '宏观结构层', description: '情节节奏、伏笔回收、卷末情绪' },
  { key: 'character', name: '人物塑造层', description: '角色一致性、台词指纹、配角活跃度' },
  { key: 'scene', name: '场景与感官层', description: '五感平衡、时空跳跃、动作逻辑' },
  { key: 'prose', name: '文笔与修辞层', description: '高频词疲劳、陈词滥调、被动语态' },
  { key: 'experience', name: '阅读体验层', description: '章末悬念、金句密度、段落舒适度' },
  { key: 'technical', name: '技术性排雷层', description: '视角越界、时代穿帮、合规检查' }
]

// 问题严重度颜色映射
export const SEVERITY_COLORS = {
  critical: '#f56c6c',
  warning: '#e6a23c',
  info: '#909399'
}

// ==================== 导出的工具函数 ====================

/**
 * 获取得分对应的颜色
 */
export function getScoreColor(score) {
  if (score >= 80) return '#67c23a'
  if (score >= 60) return '#e6a23c'
  return '#f56c6c'
}

/**
 * 获取问题严重度对应的Tag类型
 */
export function getSeverityType(severity) {
  if (severity === 'critical' || severity === '严重') return 'danger'
  if (severity === 'warning' || severity === '中等') return 'warning'
  return 'info'
}

/**
 * 获取维度名称
 */
export function getDimensionName(key) {
  const dim = QC_DIMENSIONS.find(d => d.key === key)
  return dim ? dim.name : key
}

/**
 * 正文质控Composable
 * @param {Object} props - 组件props
 * @param {Ref} props.projectId - 项目ID
 * @param {Ref} props.taskId - 任务ID
 * @param {Ref} props.units - 单元列表
 * @param {Ref} props.project - 项目信息（用于质控上下文）
 */
export function useContentQualityControl(props) {
  const projectId = props.projectId
  const taskId = props.taskId
  const units = props.units
  const project = props.project

  // ==================== 状态 ====================
  
  // 质控进度状态
  const qcLoading = ref(false)
  const batchQCRunning = ref(false)
  const batchQCProgress = ref({
    current: 0,
    total: 0,
    currentUnit: null,
    status: 'idle' // idle, running, completed, failed
  })

  // 当前选中的单元质控报告
  const activeUnitReport = ref(null)
  const activeUnitIndex = ref(null)

  // 修正预览状态
  const fixPreviewData = ref(null)
  const showFixDialog = ref(false)

  // 质控报告缓存（按单元索引）
  const unitQCReports = ref({})

  // ==================== 计算属性 ====================
  
  // 单元质控状态汇总
  const qcSummary = computed(() => {
    if (!units.value || units.value.length === 0) {
      return { completed: 0, pending: 0, running: 0, failed: 0, avgScore: 0 }
    }
    
    let completed = 0, pending = 0, running = 0, failed = 0
    let totalScore = 0, scoreCount = 0
    
    units.value.forEach(unit => {
      const qcStatus = unit.quality_control?.status || 'pending'
      if (qcStatus === 'completed') {
        completed++
        const score = unit.quality_control?.score || 0
        if (score > 0) {
          totalScore += score
          scoreCount++
        }
      } else if (qcStatus === 'running') {
        running++
      } else if (qcStatus === 'failed') {
        failed++
      } else {
        pending++
      }
    })
    
    return {
      completed,
      pending,
      running,
      failed,
      avgScore: scoreCount > 0 ? Math.round(totalScore / scoreCount) : 0,
      total: units.value.length
    }
  })

  // 可以执行质控的单元（已完成且未质控或有内容的单元）
  const unitsAvailableForQC = computed(() => {
    return units.value.filter(unit => {
      // 已完成的单元或已有内容的单元都可以质控
      const hasContent = unit.final_content && unit.final_content.length > 100
      const needsQC = unit.quality_control?.status === 'pending' || 
                      unit.quality_control?.status === 'failed'
      return (unit.status === 'completed' || hasContent) && needsQC
    })
  })

  // ==================== API方法 ====================

  /**
   * 触发单单元质控检测
   * @param {number} unitIndex - 单元序号
   * @param {Object} options - 配置选项
   * @returns {Promise<Object>} 质控结果
   */
  async function triggerUnitQC(unitIndex, options = {}) {
    const unit = units.value.find(u => u.unit_index === unitIndex)
    if (!unit) {
      ElMessage.warning(`未找到单元 ${unitIndex}`)
      return null
    }

    const content = unit.final_content
    if (!content || content.length < 100) {
      ElMessage.warning('单元内容不足，无法进行质控')
      return null
    }

    qcLoading.value = true
    
    try {
      const response = await api.post(
        `/api/v1/novel-writer/quality-control/unit/${projectId.value}/${unitIndex}`,
        {
          content,
          dimensions: options.dimensions || QC_DIMENSIONS.map(d => d.key),
          depth: options.depth || 'standard',
          auto_fix: options.autoFix !== false, // 默认开启自动修正
          auto_fix_threshold: options.threshold || 0.8
        },
        { timeout: 300000 } // 5分钟超时
      )

      if (response.data?.success) {
        const result = response.data.data
        
        // 更新单元质控报告缓存
        unitQCReports.value[unitIndex] = result
        
        // 更新单元状态
        updateUnitQCState(unitIndex, {
          status: 'completed',
          score: result.score,
          issues_count: result.issues_count,
          fixed_count: result.fixed_count,
          issues: result.issues,
          fixes_applied: result.fixes_applied,
          report: result.report
        })

        ElMessage.success(`单元 ${unitIndex} 质控完成，得分: ${result.score}`)
        return result
      } else {
        throw new Error(response.data?.message || '质控失败')
      }
    } catch (error) {
      console.error('[正文质控] 单单元质控失败:', error)
      updateUnitQCState(unitIndex, { status: 'failed' })
      ElMessage.error(error.response?.data?.detail || error.message || '质控检测失败')
      return null
    } finally {
      qcLoading.value = false
    }
  }

  /**
   * 批量质控检测
   * @param {Object} options - 配置选项
   * @returns {Promise<Object>} 批量质控结果
   */
  async function triggerBatchQC(options = {}) {
    const availableUnits = unitsAvailableForQC.value
    if (availableUnits.length === 0) {
      ElMessage.info('所有单元已完成质控或暂无可质控内容')
      return null
    }

    batchQCRunning.value = true
    batchQCProgress.value = {
      current: 0,
      total: availableUnits.length,
      currentUnit: null,
      status: 'running'
    }

    const results = []
    const failedUnits = []

    try {
      for (const unit of availableUnits) {
        batchQCProgress.value.currentUnit = unit.unit_index
        
        // 更新单元质控状态为running
        updateUnitQCState(unit.unit_index, { status: 'running' })

        const result = await triggerUnitQC(unit.unit_index, options)
        
        batchQCProgress.value.current++
        
        if (result) {
          results.push({
            unit_index: unit.unit_index,
            score: result.score,
            issues_count: result.issues_count,
            fixed_count: result.fixed_count
          })
        } else {
          failedUnits.push(unit.unit_index)
        }
      }

      batchQCProgress.value.status = failedUnits.length > 0 ? 'partial' : 'completed'
      
      // 批量质控完成
      const summary = {
        total: availableUnits.length,
        completed: results.length,
        failed: failedUnits.length,
        avgScore: results.length > 0 
          ? Math.round(results.reduce((sum, r) => sum + r.score, 0) / results.length)
          : 0,
        results,
        failedUnits
      }

      ElMessage.success(
        `批量质控完成: ${results.length}/${availableUnits.length}个单元，平均得分: ${summary.avgScore}`
      )

      return summary
    } catch (error) {
      console.error('[正文质控] 批量质控失败:', error)
      batchQCProgress.value.status = 'failed'
      ElMessage.error('批量质控异常中断')
      return null
    } finally {
      batchQCRunning.value = false
    }
  }

  /**
   * 预览修正效果
   * @param {number} unitIndex - 单元序号
   * @param {string} fixId - 修正ID
   * @returns {Promise<Object>} 修正预览数据
   */
  async function previewFix(unitIndex, fixId) {
    try {
      const response = await api.get(
        `/api/v1/novel-writer/quality-control/content/unit/${unitIndex}/preview-fix`,
        { params: { fix_id: fixId, project_id: projectId.value } },
        { timeout: 60000 }
      )

      if (response.data?.success) {
        fixPreviewData.value = response.data.data
        showFixDialog.value = true
        return response.data.data
      } else {
        throw new Error(response.data?.message || '获取预览失败')
      }
    } catch (error) {
      console.error('[正文质控] 预览修正失败:', error)
      ElMessage.error(error.message || '获取修正预览失败')
      return null
    }
  }

  /**
   * 选择性应用修正
   * @param {number} unitIndex - 单元序号
   * @param {Array<string>} fixIds - 要应用的修正ID列表
   * @returns {Promise<Object>} 应用结果
   */
  async function applySelectedFixes(unitIndex, fixIds) {
    try {
      const response = await api.post(
        `/api/v1/novel-writer/quality-control/content/unit/${unitIndex}/apply-selected?project_id=${projectId.value}`,
        { fix_ids: fixIds },
        { timeout: 300000 }
      )

      if (response.data?.success) {
        const result = response.data.data
        
        // 更新单元状态
        updateUnitQCState(unitIndex, {
          fixed_count: result.applied_count,
          fixes_applied: result.applied_fixes,
          original_content: result.original_content,
          fixed_content: result.fixed_content
        })

        ElMessage.success(`已应用 ${result.applied_count} 个修正`)
        return result
      } else {
        throw new Error(response.data?.message || '应用修正失败')
      }
    } catch (error) {
      console.error('[正文质控] 应用修正失败:', error)
      ElMessage.error(error.message || '应用修正失败')
      return null
    }
  }

  /**
   * 撤销修正
   * @param {number} unitIndex - 单元序号
   * @param {string} fixId - 可选，撤销特定修正；为空则撤销全部
   * @returns {Promise<Object>} 撤销结果
   */
  async function revertFix(unitIndex, fixId = null) {
    try {
      const confirmText = fixId 
        ? '确认撤销该修正？' 
        : '确认撤销该单元所有修正？修正后的内容将被恢复为原始内容。'
      
      await ElMessageBox.confirm(confirmText, '撤销修正', {
        confirmButtonText: '确认撤销',
        cancelButtonText: '取消',
        type: 'warning'
      })

      const response = await api.post(
        `/api/v1/novel-writer/quality-control/unit/${projectId.value}/${unitIndex}/revert-fix`,
        { fix_id: fixId },
        { timeout: 60000 }
      )

      if (response.data?.success) {
        const result = response.data.data
        
        // 更新单元状态
        updateUnitQCState(unitIndex, {
          fixed_count: 0,
          fixes_applied: [],
          original_content: null
        })

        ElMessage.success('修正已撤销')
        return result
      } else {
        throw new Error(response.data?.message || '撤销失败')
      }
    } catch (error) {
      if (error !== 'cancel') {
        console.error('[正文质控] 撤销修正失败:', error)
        ElMessage.error(error.message || '撤销修正失败')
      }
      return null
    }
  }

  /**
   * 获取单元质控报告
   * @param {number} unitIndex - 单元序号
   * @returns {Promise<Object>} 质控报告
   */
  async function fetchUnitReport(unitIndex) {
    // 先检查缓存
    if (unitQCReports.value[unitIndex]) {
      return unitQCReports.value[unitIndex]
    }

    // 从单元数据中获取
    const unit = units.value.find(u => u.unit_index === unitIndex)
    if (unit?.quality_control?.report) {
      unitQCReports.value[unitIndex] = unit.quality_control
      return unit.quality_control
    }

    return null
  }

  // ==================== 状态更新 ====================

  /**
   * 更新单元质控状态（内部方法）
   */
  function updateUnitQCState(unitIndex, qcData) {
    const unitIdx = units.value.findIndex(u => u.unit_index === unitIndex)
    if (unitIdx === -1) return

    const oldUnit = units.value[unitIdx]
    const newQC = {
      ...oldUnit.quality_control,
      ...qcData,
      updated_at: Date.now()
    }

    // 使用splice确保响应式更新
    units.value.splice(unitIdx, 1, {
      ...oldUnit,
      quality_control: newQC
    })

    // 更新缓存
    unitQCReports.value[unitIndex] = newQC
  }

  /**
   * 处理WebSocket质控消息
   */
  function handleQCMessage(msgType, msgData) {
    switch (msgType) {
      case 'unit_quality_control':
        // 单单元质控完成
        if (msgData) {
          updateUnitQCState(msgData.unit_index, {
            status: msgData.status,
            score: msgData.score,
            issues_count: msgData.issues_count,
            fixed_count: msgData.fixed_count,
            issues: msgData.issues,
            fixes_applied: msgData.fixes_applied,
            report: msgData.report
          })
        }
        break

      case 'content_qc_progress':
        // 批量质控进度
        if (msgData) {
          batchQCProgress.value = {
            current: msgData.completed || batchQCProgress.value.current,
            total: msgData.total || batchQCProgress.value.total,
            currentUnit: msgData.current_unit,
            status: 'running'
          }
        }
        break

      case 'content_qc_batch_complete':
        // 批量质控完成
        batchQCRunning.value = false
        batchQCProgress.value.status = 'completed'
        break
    }
  }

  /**
   * 设置当前查看的单元报告
   */
  function setActiveUnit(unitIndex) {
    activeUnitIndex.value = unitIndex
    if (unitIndex) {
      fetchUnitReport(unitIndex).then(report => {
        activeUnitReport.value = report
      })
    } else {
      activeUnitReport.value = null
    }
  }

  // ==================== 返回 ====================
  
  return {
    // 状态
    qcLoading,
    batchQCRunning,
    batchQCProgress,
    activeUnitReport,
    activeUnitIndex,
    fixPreviewData,
    showFixDialog,
    unitQCReports,
    qcSummary,
    unitsAvailableForQC,

    // 常量
    QC_DIMENSIONS,
    SEVERITY_COLORS,

    // API方法
    triggerUnitQC,
    triggerBatchQC,
    previewFix,
    applySelectedFixes,
    revertFix,
    fetchUnitReport,

    // 状态更新
    updateUnitQCState,
    handleQCMessage,
    setActiveUnit,

    // 工具方法
    getScoreColor,
    getSeverityType,
    getDimensionName
  }
}