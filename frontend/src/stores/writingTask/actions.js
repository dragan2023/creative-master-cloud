/**
 * 多Agent协作文学作品生成系统 - 写作任务状态管理（动作部分）
 * 
 * 模块: writing-engine
 * 文件: writingTask/actions.js
 * 功能: 定义写作任务的所有操作方法
 * 
 * 创建时间: 2026-03-27
 * 最后修改: 2026-04-26
 */

import { writingTaskApi } from '@/api/writing-task'

export function useWritingTaskActions(state, connectWS, disconnectWS) {
  // ==================== Actions ====================
  
  /**
   * 创建写作任务
   * @param {string} projectId - 项目ID
   * @param {Object} payload - 任务配置
   * @returns {Promise<Object>} 创建的任务
   */
  async function createTask(projectId, payload = {}) {
    state.loading.value = true
    try {
      const res = await writingTaskApi.createTask({
        project_id: projectId,
        start_from: payload.start_from || 1,
        unit_count: payload.unit_count || null,
        config: payload.config || {}
      })
      state.currentTask.value = res.data
      // 创建成功后连接WebSocket
      connectWS(res.data.id)
      return res.data
    } finally {
      state.loading.value = false
    }
  }
  
  /**
   * 获取任务详情
   * @param {string} taskId - 任务ID
   * @returns {Promise<Object>} 任务详情
   */
  async function fetchTask(taskId) {
    try {
      const res = await writingTaskApi.getTask(taskId)
      state.currentTask.value = res.data
      return res.data
    } catch (error) {
      console.error('[WritingTask Store] 获取任务失败:', error)
      throw error
    }
  }
  
  /**
   * 获取项目的当前任务（用于组件初始化）
   * @param {number} projectId - 项目ID
   * @returns {Promise<Object|null>} 当前任务或null
   */
  async function fetchCurrentTask(projectId) {
    try {
      // 先尝试获取运行中的任务
      const res = await writingTaskApi.listTasks({ status: 'running', page: 1, page_size: 10 })
      if (res.data?.items) {
        const task = res.data.items.find(t => t.project_id === projectId)
        if (task) {
          state.currentTask.value = task
          // 连接WebSocket
          connectWS(task.id)
          // 加载单元列表
          await fetchUnits(task.id)
          return task
        }
      }

      // 当前项目没有运行中任务：关闭上一项目/上一任务的实时连接，
      // 避免路由复用 WritingWorkbench 时遗留孤儿 WebSocket。
      disconnectWS()
      
      // 如果没有运行中的任务，获取最近的一个任务
      const listRes = await writingTaskApi.listTasks({ page: 1, page_size: 1 })
      if (listRes.data?.items) {
        const task = listRes.data.items.find(t => t.project_id === projectId)
        if (task) {
          state.currentTask.value = task
          await fetchUnits(task.id)
          return task
        }
      }
      
      state.currentTask.value = null
      return null
    } catch (error) {
      console.error('[WritingTask Store] 获取当前任务失败:', error)
      return null
    }
  }
  
  /**
   * 获取任务列表
   * @param {Object} params - 查询参数
   * @returns {Promise<Array>} 任务列表
   */
  async function fetchTaskList(params = {}) {
    state.loading.value = true
    try {
      const res = await writingTaskApi.listTasks(params)
      const listData = res.data || { items: [], total: 0 }
      state.taskList.value = listData.items || []
      return listData
    } finally {
      state.loading.value = false
    }
  }
  
  /**
   * 中断任务
   * @param {string} taskId - 任务ID
   * @returns {Promise} 操作结果
   */
  async function interruptTask(taskId) {
    try {
      const res = await writingTaskApi.interruptTask(taskId)
      if (state.currentTask.value?.id === taskId) {
        // 不立即更新状态，等待WebSocket推送状态变更
      }
      // 不立即断开WebSocket，等待服务器推送最终状态
      return res
    } catch (error) {
      console.error('[WritingTask Store] 中断任务失败:', error)
      throw error
    }
  }
  
  /**
   * 恢复任务
   * @param {string} taskId - 任务ID
   * @returns {Promise} 操作结果
   */
  async function resumeTask(taskId) {
    try {
      const res = await writingTaskApi.resumeTask(taskId)
      if (state.currentTask.value?.id === taskId) {
        state.currentTask.value.status = 'running'
        // 重新连接WebSocket
        connectWS(taskId)
      }
      return res
    } catch (error) {
      console.error('[WritingTask Store] 恢复任务失败:', error)
      throw error
    }
  }
  
  /**
   * 继续生成任务
   * @param {string} taskId - 任务ID
   * @param {number} unitCount - 继续生成的单元数量
   * @returns {Promise} 操作结果
   */
  async function continueTask(taskId, unitCount) {
    try {
      const res = await writingTaskApi.continueTask(taskId, unitCount)
      if (state.currentTask.value?.id === taskId) {
        state.currentTask.value.status = 'running'
        // 重新连接WebSocket
        connectWS(taskId)
      }
      return res
    } catch (error) {
      console.error('[WritingTask Store] 继续生成任务失败:', error)
      throw error
    }
  }
  
  /**
   * 获取任务单元列表
   * @param {string} taskId - 任务ID
   * @returns {Promise<Array>} 单元列表
   */
  async function fetchUnits(taskId) {
    try {
      const res = await writingTaskApi.getTaskUnits(taskId)
      // 保留已有单元的quality_control数据（API返回的数据不包含质控信息）
      const existingQCMap = new Map()
      state.units.value.forEach(u => {
        if (u.quality_control) {
          existingQCMap.set(u.unit_index, u.quality_control)
        }
      })
      
      state.units.value = res.data.map(unit => {
        // 将后端返回的质控字段映射为quality_control对象
        let qcData = existingQCMap.get(unit.unit_index) || unit.quality_control || null
        
        // 如果后端返回了质控数据且比现有数据新，优先使用后端数据
        if (unit.quality_control_status && unit.quality_control_status !== 'pending') {
          // 从report中提取问题列表
          const reportIssues = unit.quality_control_report?.issues || []
          
          const backendQC = {
            status: unit.quality_control_status,
            score: unit.quality_control_score || 0,
            issues_count: reportIssues.length,
            fixed_count: unit.quality_control_fixes?.length || 0,
            message: unit.quality_control_status === 'completed' 
                     ? `质控完成: 得分${unit.quality_control_score || 0}, 发现${reportIssues.length}个问题`
                     : unit.quality_control_status === 'running' ? '质控检测中...'
                     : unit.quality_control_status === 'failed' ? '质控失败'
                     : '',
            report: unit.quality_control_report || null,
            issues: reportIssues,
            fixes_applied: unit.quality_control_fixes || [],
            original_content: unit.original_content_before_fix || null,
            fixed_content: unit.final_content || null,
            // v4.0: 版本内容字段从API顶层映射到 quality_control 对象
            content_after_generation: unit.content_after_generation || null,
            content_after_qc_fix: unit.content_after_qc_fix || null,
            content_after_self_revise: unit.content_after_self_revise || null,
            updated_at: unit.updated_at ? new Date(unit.updated_at).getTime() : Date.now()
          }
          // [修复] 即使存在_ws标记，也合并版本字段（WS消息可能不包含完整的版本内容）
          if (qcData && qcData._from_ws) {
            // WS数据的QC状态/分数优先保留，但版本字段从API补充
            qcData = {
              ...qcData,
              // 版本字段：WS有值用WS，无值用API（API字段更可靠，因WS消息常不包含版本内容）
              content_after_generation: qcData.content_after_generation || backendQC.content_after_generation,
              content_after_qc_fix: qcData.content_after_qc_fix || backendQC.content_after_qc_fix,
              content_after_self_revise: qcData.content_after_self_revise || backendQC.content_after_self_revise,
            }
          } else if (!qcData || !qcData._from_ws) {
            // 无WS数据，使用API数据
            qcData = backendQC
          }
        }
        
        return {
          ...unit,
          quality_control: qcData
        }
      })
      
      console.log('[WritingTask Store] fetchUnits完成, 单元数:', state.units.value.length, '有QC数据的:', state.units.value.filter(u => u.quality_control).length)
      return res.data
    } catch (error) {
      console.error('[WritingTask Store] 获取单元失败:', error)
      throw error
    }
  }
  
  /**
   * 获取单元场景列表
   * @param {string} taskId - 任务ID
   * @param {number} unitIndex - 单元索引
   * @returns {Promise<Array>} 场景列表
   */
  async function fetchScenes(taskId, unitIndex) {
    try {
      const res = await writingTaskApi.getUnitScenes(taskId, unitIndex)
      state.scenes.value[unitIndex] = res.data
      return res.data
    } catch (error) {
      console.error('[WritingTask Store] 获取场景失败:', error)
      throw error
    }
  }
  
  /**
   * 获取任务统计信息
   * @param {string} taskId - 任务ID
   * @returns {Promise<Object>} 统计信息
   */
  async function fetchStats(taskId) {
    try {
      const res = await writingTaskApi.getTaskStats(taskId)
      state.stats.value = res.data
      return res.data
    } catch (error) {
      console.error('[WritingTask Store] 获取统计失败:', error)
      throw error
    }
  }
  
  /**
   * 删除任务
   * @param {string} taskId - 任务ID
   * @returns {Promise} 操作结果
   */
  async function deleteTask(taskId) {
    try {
      const res = await writingTaskApi.deleteTask(taskId)
      // 如果删除的是当前任务，清除状态
      if (state.currentTask.value?.id === taskId) {
        disconnectWS()
        state.currentTask.value = null
        state.units.value = []
        state.scenes.value = {}
        state.stats.value = null
        state.progressMessages.value = []
      }
      // 从列表中移除
      const index = state.taskList.value.findIndex(t => t.id === taskId)
      if (index !== -1) {
        state.taskList.value.splice(index, 1)
      }
      return res
    } catch (error) {
      console.error('[WritingTask Store] 删除任务失败:', error)
      throw error
    }
  }
  
  // ==================== Agent配置 ====================
  
  /**
   * 获取Agent配置
   * @returns {Promise<Object>} 配置信息
   */
  async function fetchAgentConfig() {
    try {
      const res = await writingTaskApi.getAgentConfig()
      state.agentConfig.value = res.data
      return res.data
    } catch (error) {
      console.error('[WritingTask Store] 获取Agent配置失败:', error)
      throw error
    }
  }
  
  /**
   * 更新Agent配置
   * @param {Object} config - 配置数据
   * @returns {Promise<Object>} 更新后的配置
   */
  async function updateAgentConfig(config) {
    try {
      const res = await writingTaskApi.updateAgentConfig(config)
      state.agentConfig.value = res.data
      return res.data
    } catch (error) {
      console.error('[WritingTask Store] 更新Agent配置失败:', error)
      throw error
    }
  }
  
  /**
   * 重置Agent配置
   * @returns {Promise<Object>} 重置后的配置
   */
  async function resetAgentConfig() {
    try {
      const res = await writingTaskApi.resetAgentConfig()
      state.agentConfig.value = res.data
      return res.data
    } catch (error) {
      console.error('[WritingTask Store] 重置Agent配置失败:', error)
      throw error
    }
  }

  /**
   * 测试Agent模型连接
   * @param {Object} config - 测试配置 { model_id, provider }
   * @returns {Promise<Object>} 测试结果
   */
  async function testConnection(config) {
    try {
      const res = await writingTaskApi.testAgentConnection(config)
      return res.data?.data || res.data
    } catch (error) {
      console.error('[WritingTask Store] 测试连接失败:', error)
      throw error
    }
  }

  /**
   * 清除进度消息
   */
  function clearProgress() {
    state.progressMessages.value = []
  }
  
  /**
   * 重置Store状态
   */
  function $reset() {
    state.currentTask.value = null
    state.taskList.value = []
    state.units.value = []
    state.scenes.value = {}
    state.stats.value = null
    state.progressMessages.value = []
    disconnectWS()
  }

  return {
    // Actions
    createTask,
    fetchTask,
    fetchCurrentTask,
    fetchTaskList,
    interruptTask,
    resumeTask,
    continueTask,
    fetchUnits,
    fetchScenes,
    fetchStats,
    deleteTask,
    fetchAgentConfig,
    updateAgentConfig,
    resetAgentConfig,
    testConnection,
    clearProgress,
    $reset
  }
}
