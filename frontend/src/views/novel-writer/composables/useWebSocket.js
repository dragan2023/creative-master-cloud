/**
 * WebSocket 和进度监控 Composable
 * 
 * 处理 WebSocket 连接、进度消息、Agent流水线状态等工作流监控逻辑
 */
import { ref, computed, watch, nextTick } from 'vue'
import { useWritingTaskStore } from '@/stores/writingTask'
import { agentConfigs } from './useWritingTask'

/**
 * WebSocket 进度监控 Composable
 * @param {Object} projectState - 项目状态 composable 返回的对象
 */
export function useWebSocket(projectState) {
  const writingStore = useWritingTaskStore()

  // ==================== 响应式状态 ====================
  const messagesListRef = ref(null)
  const activeCollapse = ref(['agents'])
  const activeUnits = ref([])
  const loadingScenes = ref({})
  const sceneDialogVisible = ref(false)
  const selectedScene = ref(null)
  const selectedUnit = ref(null)

  // ==================== 计算属性 ====================

  // Agent流水线状态
  // 后端通过 workflow_step 消息（type="workflow_step"，含 agent_name + status 字段）
  // 来推送各Agent的运行状态。task_progress 消息也可能携带 agent_name。
  const agentPipeline = computed(() => {
    const messages = writingStore.progressMessages
    const isRunning = writingStore.isRunning
    const isCompleted = writingStore.isCompleted
    
    const pipeline = agentConfigs.map((agent) => {
      // 查找该Agent的相关消息（优先 workflow_step，其次 task_progress 带agent_name的消息）
      const agentMsgs = messages.filter(
        (m) =>
          (m.type === "workflow_step" && m.data?.agent_name?.includes(agent.label)) ||
          (m.type === "task_progress" && m.agent_name?.includes(agent.label)) ||
          m.data?.agent_role === agent.role ||
          m.data?.agent_name?.includes(agent.label)
      )
      // 取最后一条消息（最新状态），消息通过 push 追加到数组末尾
      const latestMsg = agentMsgs.length > 0 ? agentMsgs[agentMsgs.length - 1] : null

      let status = 'waiting'
      let statusLabel = '等待中'
      let statusType = 'info'

      if (latestMsg) {
        // workflow_step 消息：status 为 "running" | "done" | "error"
        if (latestMsg.type === "workflow_step") {
          if (latestMsg.data?.status === "done") {
            status = 'completed'
            statusLabel = '已完成'
            statusType = 'success'
          } else if (latestMsg.data?.status === "error") {
            status = 'error'
            statusLabel = '失败'
            statusType = 'danger'
          } else if (latestMsg.data?.status === "running") {
            status = 'running'
            statusLabel = '运行中'
            statusType = 'primary'
          }
        }
        // task_progress 消息携带 agent_name 时，使用其 status 字段
        else if (latestMsg.type === "task_progress" && latestMsg.agent_name) {
          if (latestMsg.status === "completed" || latestMsg.status === "done") {
            status = 'completed'
            statusLabel = '已完成'
            statusType = 'success'
          } else if (latestMsg.status === "failed" || latestMsg.status === "error") {
            status = 'error'
            statusLabel = '失败'
            statusType = 'danger'
          } else if (latestMsg.status === "started" || latestMsg.status === "processing") {
            status = 'running'
            statusLabel = '运行中'
            statusType = 'primary'
          }
        }
        // 兼容旧的 agent_complete / agent_error / agent_start 类型（如果后端未来恢复）
        else if (
          latestMsg.type === 'agent_complete' ||
          latestMsg.type === 'unit_complete'
        ) {
          status = 'completed'
          statusLabel = '已完成'
          statusType = 'success'
        } else if (latestMsg.type === 'agent_error') {
          status = 'error'
          statusLabel = '失败'
          statusType = 'danger'
        } else if (
          latestMsg.type === 'agent_start' ||
          latestMsg.data?.message?.includes('开始')
        ) {
          status = 'running'
          statusLabel = '运行中'
          statusType = 'primary'
        }
      } else if (isRunning) {
        // 任务运行中，但该Agent尚未收到任何消息 → 等待调度
        status = 'waiting'
        statusLabel = '等待中'
        statusType = 'info'
      }

      if (isCompleted) {
        status = 'completed'
        statusLabel = '已完成'
        statusType = 'success'
      }

      return {
        ...agent,
        status,
        statusLabel,
        statusType
      }
    })

    return pipeline
  })

  // 当前处理信息
  const currentProcessingInfo = computed(() => {
    const current = writingStore.currentUnit
    if (!current || !writingStore.isRunning) return null

    const msg = writingStore.progressMessages.find(
      (m) => m.data?.unit_index === current.unit_index
    )
    if (msg) {
      return `正在处理: ${current.unit_title || `单元 ${current.unit_index}`} - ${msg.data?.message || ''}`
    }
    return `正在处理: ${current.unit_title || `单元 ${current.unit_index}`}`
  })

  // 工作流步骤
  const workflowSteps = computed(() => {
    const steps = []
    const messages = writingStore.progressMessages

    for (const msg of messages) {
      if (msg.type === 'unit_progress' && msg.data?.status) {
        const status = msg.data.status
        const progress = msg.data.progress || 0

        let stepMessage = ''
        let stepIcon = 'MagicStick'

        switch (status) {
          case 'structuring':
            stepMessage = `单元 ${msg.data.unit_index || ''}: 结构拆解中...`
            stepIcon = 'OfficeBuilding'
            break
          case 'writing':
            stepMessage = `单元 ${msg.data.unit_index || ''}: 内容生成中...`
            stepIcon = 'EditPen'
            break
          case 'reviewing':
            stepMessage = `单元 ${msg.data.unit_index || ''}: 审阅润色中...`
            stepIcon = 'View'
            break
          case 'assembling':
            stepMessage = `单元 ${msg.data.unit_index || ''}: 内容组装中...`
            stepIcon = 'SetUp'
            break
          case 'completed':
            stepMessage = `单元 ${msg.data.unit_index || ''}: 处理完成`
            stepIcon = 'CircleCheck'
            break
          default:
            stepMessage =
              msg.data.message || `单元 ${msg.data.unit_index || ''}: ${status}`
        }

        const existingStep = steps.find(
          (s) => s.step === `unit_${msg.data.unit_index}_${status}`
        )
        if (!existingStep) {
          steps.push({
            step: `unit_${msg.data.unit_index}_${status}`,
            status:
              status === 'completed'
                ? 'done'
                : status === 'failed'
                  ? 'error'
                  : 'running',
            message: stepMessage,
            icon: stepIcon,
            progress
          })
        }
      }

      if (msg.type === 'scene_progress' && msg.data?.status) {
        const status = msg.data.status
        const unitIdx = msg.data.unit_index || ''
        const sceneIdx = msg.data.scene_index || ''

        if (status === 'writing') {
          steps.push({
            step: `scene_${unitIdx}_${sceneIdx}_writing`,
            status: 'running',
            message: `单元 ${unitIdx} 场景 ${sceneIdx}: 内容生成中...`,
            icon: 'EditPen'
          })
        } else if (status === 'completed' || status === 'done') {
          steps.push({
            step: `scene_${unitIdx}_${sceneIdx}_done`,
            status: 'done',
            message: `单元 ${unitIdx} 场景 ${sceneIdx}: 生成完成`,
            icon: 'CircleCheck'
          })
        } else if (status === 'failed') {
          steps.push({
            step: `scene_${unitIdx}_${sceneIdx}_error`,
            status: 'error',
            message: `单元 ${unitIdx} 场景 ${sceneIdx}: 生成失败`,
            icon: 'CircleClose'
          })
        }
      }

      if (msg.type === 'task_progress' && msg.data) {
        const completed = msg.data.completed_units || 0
        const total = msg.data.total_units || 0
        if (completed > 0) {
          steps.push({
            step: `task_progress_${completed}`,
            status: 'done',
            message: `已完成 ${completed}/${total} 单元`,
            icon: 'DataLine'
          })
        }
      }
    }

    return steps.slice(-5)
  })

  // 选中的场景标题
  const selectedSceneTitle = computed(() => {
    if (!selectedScene.value) return ''
    const unitIdx = selectedUnit.value?.unit_index || ''
    const sceneIdx = selectedScene.value.scene_index
    const sceneTitle = selectedScene.value.scene_title || `场景 ${sceneIdx}`
    return `单元 ${unitIdx} - ${sceneTitle}`
  })

  // 显示的单元列表
  const displayUnits = computed(() => {
    if (writingStore.currentTask && writingStore.units.length > 0) {
      return writingStore.units
    }

    if (
      projectState?.unitSummaries?.value &&
      Object.keys(projectState.unitSummaries.value).length > 0
    ) {
      return Object.entries(projectState.unitSummaries.value)
        .map(([index, summary]) => ({
          unit_index: parseInt(index),
          unit_title:
            typeof summary === 'string'
              ? summary
              : summary?.title || `第${index}${projectState.unitLabel.value}`,
          unit_summary:
            typeof summary === 'string' ? null : summary?.summary || null,
          status: 'pending',
          word_count: 0
        }))
        .sort((a, b) => a.unit_index - b.unit_index)
    }

    return []
  })

  // ==================== 方法 ====================

  // 处理单元展开
  async function handleUnitExpand(unit) {
    if (writingStore.scenes[unit.unit_index]) return

    loadingScenes.value[unit.unit_index] = true
    await writingStore.fetchScenes(writingStore.currentTask.id, unit.unit_index)
    loadingScenes.value[unit.unit_index] = false
  }

  // 获取场景列表
  function getScenes(unitIndex) {
    return writingStore.scenes[unitIndex] || []
  }

  // 处理场景点击
  function handleSceneClick(scene, unit) {
    selectedScene.value = scene
    selectedUnit.value = unit
    sceneDialogVisible.value = true
  }

  // 获取单元状态类型
  function getUnitStatusType(status) {
    const typeMap = {
      pending: 'info',
      processing: 'primary',
      completed: 'success',
      failed: 'danger'
    }
    return typeMap[status] || 'info'
  }

  // 获取单元状态标签
  function getUnitStatusLabel(status) {
    const labelMap = {
      pending: '等待中',
      processing: '处理中',
      completed: '已完成',
      failed: '失败'
    }
    return labelMap[status] || status
  }

  // 获取场景状态类型
  function getSceneStatusType(status) {
    const typeMap = {
      pending: 'info',
      writing: 'primary',
      reviewing: 'warning',
      completed: 'success',
      failed: 'danger'
    }
    return typeMap[status] || 'info'
  }

  // 获取场景状态标签
  function getSceneStatusLabel(status) {
    const labelMap = {
      pending: '等待中',
      writing: '写作中',
      reviewing: '审阅中',
      completed: '已完成',
      failed: '失败'
    }
    return labelMap[status] || status
  }

  // 格式化数字
  function formatNumber(num) {
    if (!num) return '0'
    return num.toLocaleString()
  }

  // 格式化时间
  function formatTime(timestamp) {
    if (!timestamp) return ''
    const date = new Date(timestamp)
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
  }

  // 计算效率
  function calculateEfficiency() {
    const tokens =
      writingStore.stats?._summary?.total_tokens ||
      writingStore.stats?.total_tokens ||
      0
    const task = writingStore.currentTask
    if (!task) return '0'

    const start = task.start_time ? new Date(task.start_time) : null
    const end = task.end_time ? new Date(task.end_time) : null

    let ms = 0
    if (start && end) {
      ms = end - start
    } else if (start && writingStore.isRunning) {
      ms = Date.now() - start
    }

    const durationSec = ms / 1000
    if (durationSec === 0) return '0'
    return (tokens / durationSec).toFixed(1)
  }

  // 获取状态类型
  function getStatusType(status) {
    const typeMap = {
      pending: 'info',
      running: 'primary',
      interrupted: 'warning',
      completed: 'success',
      failed: 'danger'
    }
    return typeMap[status] || 'info'
  }

  // 获取状态标签
  function getStatusLabel(status) {
    const labelMap = {
      pending: '等待中',
      running: '运行中',
      interrupted: '已中断',
      completed: '已完成',
      failed: '失败'
    }
    return labelMap[status] || status
  }

  // 设置消息列表滚动
  function setupMessagesScroll() {
    watch(
      () => writingStore.progressMessages.length,
      () => {
        nextTick(() => {
          if (messagesListRef.value) {
            messagesListRef.value.scrollTop = 0
          }
        })
      }
    )
  }

  // 清理资源
  function cleanup() {
    writingStore.disconnectWebSocket()
  }

  return {
    // 状态
    messagesListRef,
    activeCollapse,
    activeUnits,
    loadingScenes,
    sceneDialogVisible,
    selectedScene,
    selectedUnit,

    // 计算属性
    agentPipeline,
    currentProcessingInfo,
    workflowSteps,
    selectedSceneTitle,
    displayUnits,

    // 方法
    handleUnitExpand,
    getScenes,
    handleSceneClick,
    getUnitStatusType,
    getUnitStatusLabel,
    getSceneStatusType,
    getSceneStatusLabel,
    formatNumber,
    formatTime,
    calculateEfficiency,
    getStatusType,
    getStatusLabel,
    setupMessagesScroll,
    cleanup
  }
}
