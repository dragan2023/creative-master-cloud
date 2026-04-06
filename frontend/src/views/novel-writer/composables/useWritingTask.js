/**
 * 写作任务管理 Composable
 * 
 * 处理任务创建、中断、续传、删除等任务管理逻辑
 */
import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useWritingTaskStore } from '@/stores/writingTask'
import { writingTaskApi } from '@/api/writing-task'

/**
 * Agent角色配置
 */
export const AGENT_ROLE_LABELS = {
  orchestrator: '总线Agent',
  structural: '结构师Agent',
  writer: '写手Agent',
  logic_editor: '逻辑编辑Agent',
  style_editor: '风格润色Agent',
  compliance: '合规审查Agent',
  knowledge: '知识顾问Agent',
  assembler: '合成Agent'
}

/**
 * Agent配置列表
 */
export const agentConfigs = [
  {
    role: 'orchestrator',
    label: '总线Agent',
    icon: 'Connection',
    configurable: true,
    description:
      '任务调度和流程编排的核心Agent，负责控制其他Agent的协作顺序、管理并发写手数量、处理中断续传等。',
    configTips: {
      modelType: '推荐选择推理能力强的模型，需要稳定的决策输出',
      temperature: '建议 0.2-0.4，决策类任务需要低温度保持稳定性',
      extra: '此Agent是整个系统的调度中心，模型稳定性优先于创意性'
    }
  },
  {
    role: 'structural',
    label: '结构师Agent',
    icon: 'OfficeBuilding',
    configurable: true,
    description:
      '负责将写作大纲拆解为具体的场景列表，规划每个场景的叙事结构、人物出场、情节走向和目标字数。',
    configTips: {
      modelType: '推荐选择长文本理解和结构化输出能力强的模型',
      temperature: '建议 0.5-0.7，需要平衡结构严谨性和创意空间',
      extra: '结构师的输出质量直接影响后续所有写手的创作质量'
    }
  },
  {
    role: 'writer',
    label: '写手Agent',
    icon: 'EditPen',
    configurable: true,
    description:
      '核心内容创作Agent，根据场景大纲生成高质量的文学文本，是系统中调用频率最高的Agent。',
    configTips: {
      modelType: '推荐选择中文创作能力最强的模型，这是最核心的创作环节',
      temperature: '建议 0.7-0.9，高温度能增强文学创意性和表达多样性',
      extra: '建议使用最强的创作模型，写手Agent的质量决定了最终作品的质量'
    }
  },
  {
    role: 'logic_editor',
    label: '逻辑编辑Agent',
    icon: 'View',
    configurable: true,
    description:
      '负责审查内容的逻辑连贯性，包括情节逻辑、角色行为与人设一致性、时间线合理性、场景描述矛盾等。',
    configTips: {
      modelType: '推荐选择推理能力强的模型，如 thinking/reasoning 系列',
      temperature: '建议 0.1-0.3，逻辑分析需要极低温度保证严谨性',
      extra: '推理类模型（如带thinking标签的模型）在逻辑检查任务上表现更优'
    }
  },
  {
    role: 'style_editor',
    label: '风格润色Agent',
    icon: 'MagicStick',
    configurable: true,
    description:
      '负责优化文学风格、修辞手法、叙述节奏和语言质量，提升文本的文学性和可读性。',
    configTips: {
      modelType: '推荐选择中文理解和文学表达能力强的模型',
      temperature: '建议 0.5-0.7，需要平衡文风润色效果和保持原意',
      extra: '风格润色需要对中文文学有良好理解，建议选择中文优化过的模型'
    }
  },
  {
    role: 'compliance',
    label: '合规审查Agent',
    icon: 'Warning',
    configurable: true,
    description:
      '采用Trie树本地检测+LLM辅助判断的双层架构，检测敏感内容，确保生成内容符合发布规范。',
    configTips: {
      modelType: '推荐选择安全审查能力强、判断准确的模型',
      temperature: '建议 0.0-0.2，合规判断需要最高一致性，不容许随机性',
      extra: '合规审查的准确性直接关系到内容安全，建议选择经过安全训练的模型'
    }
  },
  {
    role: 'knowledge',
    label: '知识顾问Agent',
    icon: 'Reading',
    configurable: true,
    description:
      '负责检索项目知识库和上下文信息，为其他Agent提供背景参考资料，确保创作内容与项目设定一致。',
    configTips: {
      modelType: '推荐选择检索增强和准确回答能力强的模型',
      temperature: '建议 0.2-0.4，知识检索需要准确性优先',
      extra: '知识顾问的准确性影响其他Agent的创作一致性'
    }
  },
  {
    role: 'assembler',
    label: '合成Agent',
    icon: 'SetUp',
    configurable: false,
    description:
      '负责将同一单元下所有场景的最终内容合并为完整文本，纯规则合并，无需配置LLM模型。',
    configTips: null
  }
]

/**
 * 写作任务 Composable
 * @param {Object} props - 组件 props
 * @param {Function} emit - emit 函数
 * @param {Object} projectState - 项目状态 composable 返回的对象
 */
export function useWritingTask(props, emit, projectState) {
  const writingStore = useWritingTaskStore()

  // ==================== 响应式状态 ====================
  const interrupting = ref(false)
  const testingAgent = ref({})
  const showAgentConfigDialog = ref(false)
  const quickApplyConfigId = ref(null)

  // 继续生成对话框
  const showContinueDialog = ref(false)
  const continueUnitCount = ref(1)

  // Provider和模型配置相关
  const availableProviders = ref([])
  const loadingProviders = ref(false)
  const modelConfigs = ref([])
  const loadingConfigs = ref(false)

  // 任务表单
  const taskForm = ref({
    start_from: 1,
    unit_count: null,
    words_per_chapter: 3000,
    concurrency: 3,
    generation_mode: 'auto',
    agent_models: {
      orchestrator: '',
      structural: '',
      writer: '',
      logic_editor: '',
      style_editor: '',
      compliance: '',
      knowledge: ''
    },
    agent_temps: {
      orchestrator: 0.3,
      structural: 0.6,
      writer: 0.8,
      logic_editor: 0.2,
      style_editor: 0.6,
      compliance: 0.1,
      knowledge: 0.3
    },
    agent_providers: {
      orchestrator: '',
      structural: '',
      writer: '',
      logic_editor: '',
      style_editor: '',
      compliance: '',
      knowledge: ''
    },
    agent_api_bases: {
      orchestrator: '',
      structural: '',
      writer: '',
      logic_editor: '',
      style_editor: '',
      compliance: '',
      knowledge: ''
    },
    agent_api_keys: {
      orchestrator: '',
      structural: '',
      writer: '',
      logic_editor: '',
      style_editor: '',
      compliance: '',
      knowledge: ''
    },
    agent_config_ids: {
      orchestrator: null,
      structural: null,
      writer: null,
      logic_editor: null,
      style_editor: null,
      compliance: null,
      knowledge: null
    },
    ai_elimination_enabled: true,
    ai_elimination_threshold: 50
  })

  // ==================== 计算属性 ====================

  // 可配置的Agent列表
  const configurableAgents = computed(() => {
    return agentConfigs.filter((agent) => agent.configurable !== false)
  })

  // 格式化耗时
  const formattedDuration = computed(() => {
    const task = writingStore.currentTask
    if (!task) return '00:00:00'

    const start = task.start_time ? new Date(task.start_time) : null
    const end = task.end_time ? new Date(task.end_time) : null

    let ms = 0
    if (start && end) {
      ms = end - start
    } else if (start && writingStore.isRunning) {
      ms = Date.now() - start
    }

    if (ms === 0) return '00:00:00'

    const seconds = Math.floor(ms / 1000)
    const minutes = Math.floor(seconds / 60)
    const hours = Math.floor(minutes / 60)

    return `${hours.toString().padStart(2, '0')}:${(minutes % 60).toString().padStart(2, '0')}:${(seconds % 60).toString().padStart(2, '0')}`
  })

  // 是否有已生成的内容
  const hasGeneratedContent = computed(() => {
    if (writingStore.units && writingStore.units.length > 0) {
      return writingStore.units.some(
        (u) => u.status === 'completed' && u.word_count > 0
      )
    }
    return false
  })

  // 是否可以继续生成
  const canContinueGenerate = computed(() => {
    if (!writingStore.currentTask || !writingStore.isCompleted) return false

    const completedUnits = writingStore.currentTask.completed_units || 0
    const totalUnits =
      props.projectTotalUnits ||
      Object.keys(props.unitSummaries || {}).length ||
      props.chapters?.length ||
      0

    return totalUnits > completedUnits
  })

  // ==================== 方法 ====================

  // 测试Agent连接
  async function handleTestConnection(agentRole) {
    const modelId = taskForm.value.agent_models[agentRole]
    const provider = taskForm.value.agent_providers[agentRole]

    if (!modelId || !provider) {
      ElMessage.warning('请先填写模型ID和供应商')
      return
    }

    testingAgent.value[agentRole] = true
    try {
      const config = {
        model_id: modelId,
        provider: provider,
        api_base: taskForm.value.agent_api_bases[agentRole] || undefined,
        api_key: taskForm.value.agent_api_keys[agentRole] || undefined
      }
      const res = await writingStore.testConnection(config)
      if (res?.success) {
        ElMessage.success('连接成功！')
      } else {
        ElMessage.error(res?.message || '连接失败')
      }
    } catch (error) {
      ElMessage.error('测试连接失败: ' + (error.message || '未知错误'))
    } finally {
      testingAgent.value[agentRole] = false
    }
  }

  // 处理生成模式变更
  function handleModeChange(mode) {
    console.log('[WritingWorkbench] 生成模式变更:', mode)
    taskForm.value.generation_mode = mode
  }

  // 创建任务
  async function handleCreateTask() {
    const configurableAgentsList = agentConfigs.filter((a) => a.configurable)
    const unconfigured = configurableAgentsList.filter((a) => {
      const configId = taskForm.value.agent_config_ids[a.role]
      if (configId && configId !== 'custom') return false
      if (configId === 'custom') {
        return (
          !taskForm.value.agent_models[a.role] ||
          !taskForm.value.agent_providers[a.role]
        )
      }
      return true
    })
    if (unconfigured.length > 0) {
      ElMessage.warning(
        `请先配置以下Agent的模型: ${unconfigured.map((a) => a.label).join('、')}`
      )
      return
    }

    // 验证并获取正确的项目总单元数
    let actualTotalUnits = props.projectTotalUnits

    if (!actualTotalUnits || actualTotalUnits <= 0) {
      if (props.unitSummaries && Object.keys(props.unitSummaries).length > 0) {
        actualTotalUnits = Object.keys(props.unitSummaries).length
      } else if (props.chapters && props.chapters.length > 0) {
        actualTotalUnits = props.chapters.length
      } else if (
        projectState?.projectData?.value?.unit_summaries &&
        Object.keys(projectState.projectData.value.unit_summaries).length > 0
      ) {
        actualTotalUnits = Object.keys(
          projectState.projectData.value.unit_summaries
        ).length
      } else if (
        projectState?.projectData?.value?.total_chapters &&
        projectState.projectData.value.total_chapters > 0
      ) {
        actualTotalUnits = projectState.projectData.value.total_chapters
      }
    }

    if (!actualTotalUnits || actualTotalUnits <= 0) {
      ElMessage.warning(
        '无法确定项目的总章节数，请先在项目设置中配置总章节数，或上传目录/大纲后重新识别'
      )
      return
    }

    const startFrom = taskForm.value.start_from || 1
    if (startFrom > actualTotalUnits) {
      ElMessage.warning(
        `起始单元 ${startFrom} 超出范围（总单元数: ${actualTotalUnits}）`
      )
      return
    }

    let effectiveUnitCount = taskForm.value.unit_count
    const availableUnits = actualTotalUnits - startFrom + 1

    if (!effectiveUnitCount || effectiveUnitCount > availableUnits) {
      effectiveUnitCount = availableUnits
    }

    console.log(
      `[创建任务] 实际总单元数: ${actualTotalUnits}, 起始: ${startFrom}, 生成数量: ${effectiveUnitCount}`
    )

    // 构建Agent配置
    const agentsConfig = {}

    for (const agent of configurableAgentsList) {
      const configId = taskForm.value.agent_config_ids[agent.role]

      if (configId && configId !== 'custom') {
        agentsConfig[agent.role] = {
          config_id: configId,
          temperature: taskForm.value.agent_temps[agent.role] ?? 0.7
        }
      } else {
        agentsConfig[agent.role] = {
          model: taskForm.value.agent_models[agent.role] || '',
          provider: taskForm.value.agent_providers[agent.role] || '',
          temperature: taskForm.value.agent_temps[agent.role] ?? 0.7,
          api_base: taskForm.value.agent_api_bases[agent.role] || undefined,
          api_key: taskForm.value.agent_api_keys[agent.role] || undefined
        }
      }
    }

    const task = await writingStore.createTask(projectState.projectId.value, {
      start_from: startFrom,
      unit_count: effectiveUnitCount || null,
      config: {
        words_per_chapter: taskForm.value.words_per_chapter,
        concurrency: taskForm.value.concurrency,
        generation_mode: taskForm.value.generation_mode,
        agents: agentsConfig,
        agent_api_bases: taskForm.value.agent_api_bases,
        agent_api_keys: taskForm.value.agent_api_keys
      }
    })
    if (task) {
      taskForm.value.start_from = 1
      taskForm.value.unit_count = null
    }
  }

  // 中断任务
  async function handleInterrupt() {
    try {
      interrupting.value = true
      await writingStore.interruptTask(writingStore.currentTask.id)
    } finally {
      interrupting.value = false
    }
  }

  // 续传任务
  async function handleResume() {
    await writingStore.resumeTask(writingStore.currentTask.id)
  }

  // 继续生成任务
  async function handleContinue() {
    if (!continueUnitCount.value || continueUnitCount.value < 1) {
      ElMessage.warning('请输入有效的生成数量')
      return
    }

    try {
      showContinueDialog.value = false
      await writingStore.continueTask(
        writingStore.currentTask.id,
        continueUnitCount.value
      )
      ElMessage.success(`已开始继续生成 ${continueUnitCount.value} 个单元`)
    } catch (error) {
      console.error('继续生成失败:', error)
      ElMessage.error('继续生成失败: ' + (error.message || '未知错误'))
    }
  }

  // 删除任务
  async function handleDelete() {
    try {
      await ElMessageBox.confirm(
        '确定要删除此任务吗？删除后将清除所有进度数据。',
        '确认删除',
        { type: 'warning' }
      )
      await writingStore.deleteTask(writingStore.currentTask.id)
    } catch (error) {
      if (error !== 'cancel') {
        console.error('删除任务失败:', error)
      }
    }
  }

  // 导出任务内容
  async function handleExport() {
    try {
      const taskId = writingStore.currentTask?.id
      if (!taskId) return

      const response = await writingTaskApi.exportTask(taskId, 'txt')
      const blob = new Blob([response.data || response], {
        type: 'text/plain;charset=utf-8'
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `writing_task_${taskId}.txt`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)

      ElMessage.success('下载成功')
    } catch (error) {
      console.error('导出失败:', error)
      ElMessage.error('导出失败: ' + (error.message || '未知错误'))
    }
  }

  // 导出单个单元内容
  async function handleExportUnit(unitIndex, displayUnits, unitLabel) {
    try {
      const taskId = writingStore.currentTask?.id
      if (!taskId) {
        ElMessage.warning('没有正在进行的任务')
        return
      }

      const response = await writingTaskApi.exportUnit(taskId, unitIndex, 'txt')
      const blob = new Blob([response.data || response], {
        type: 'text/plain;charset=utf-8'
      })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url

      const unit = displayUnits.find((u) => u.unit_index === unitIndex)
      const unitTitle = unit?.unit_title || `第${unitIndex}${unitLabel}`
      a.download = `${unitTitle}.txt`

      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)

      ElMessage.success('下载成功')
    } catch (error) {
      console.error('导出单元失败:', error)
      ElMessage.error('导出失败: ' + (error.message || '未知错误'))
    }
  }

  // 加载可用Provider列表
  async function loadProviders() {
    loadingProviders.value = true
    try {
      const res = await writingTaskApi.getAvailableProviders()
      availableProviders.value =
        res.data?.data?.providers || res.data?.providers || []
    } catch (error) {
      console.error('加载Provider列表失败:', error)
      availableProviders.value = [
        {
          name: 'qianwen',
          display_name: '通义千问 (阿里云百炼)',
          api_base: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
          is_preset: true,
          models: []
        },
        {
          name: 'doubao',
          display_name: '豆包 (字节跳动/火山引擎)',
          api_base: 'https://ark.cn-beijing.volces.com/api/v3',
          is_preset: true,
          models: []
        },
        {
          name: 'siliconflow',
          display_name: '硅基流动 (SiliconFlow)',
          api_base: 'https://api.siliconflow.cn/v1',
          is_preset: true,
          models: []
        },
        {
          name: 'openrouter',
          display_name: 'OpenRouter',
          api_base: 'https://openrouter.ai/api/v1',
          is_preset: true,
          models: []
        },
        {
          name: 't8star',
          display_name: '贞贞AI工坊',
          api_base: 'https://ai.t8star.cn/v1',
          is_preset: true,
          models: []
        },
        {
          name: 'custom',
          display_name: '自定义服务商',
          api_base: '',
          is_preset: false,
          models: []
        }
      ]
    } finally {
      loadingProviders.value = false
    }
  }

  // 加载预配置模型列表
  async function loadModelConfigs() {
    loadingConfigs.value = true
    try {
      const res = await writingTaskApi.getModelConfigs()
      modelConfigs.value = res.data?.data || res.data || []
    } catch (error) {
      console.error('加载模型配置失败:', error)
      modelConfigs.value = []
    } finally {
      loadingConfigs.value = false
    }
  }

  // 模型配置选择变更
  function onModelConfigChange(role, configId) {
    if (configId === 'custom') {
      return
    }
    const config = modelConfigs.value.find((c) => c.id === configId)
    if (config) {
      taskForm.value.agent_providers[role] = config.provider
      taskForm.value.agent_models[role] = config.model_id
      taskForm.value.agent_api_bases[role] = config.api_base || ''
      taskForm.value.agent_api_keys[role] = ''
    }
  }

  // 一键应用同一模型到所有Agent
  function applyToAllAgents(configId) {
    const configurableRoles = agentConfigs
      .filter((a) => a.configurable)
      .map((a) => a.role)
    for (const role of configurableRoles) {
      taskForm.value.agent_config_ids[role] = configId
      onModelConfigChange(role, configId)
    }
    ElMessage.success('已应用到所有Agent')
  }

  // 快速应用模型配置
  function handleQuickApply() {
    if (!quickApplyConfigId.value) return
    applyToAllAgents(quickApplyConfigId.value)
  }

  // Provider变更时，自动填充api_base
  function onProviderChange(role, providerName) {
    const provider = availableProviders.value.find(
      (p) => p.name === providerName
    )
    if (provider && provider.api_base) {
      taskForm.value.agent_api_bases[role] = provider.api_base
    } else {
      taskForm.value.agent_api_bases[role] = ''
    }
    taskForm.value.agent_models[role] = ''
  }

  // 获取指定provider的模型列表
  function getProviderModels(role) {
    const providerName = taskForm.value.agent_providers[role]
    const provider = availableProviders.value.find(
      (p) => p.name === providerName
    )
    return provider?.models || []
  }

  // 获取Agent图标
  function getAgentIcon(role) {
    const iconMap = {
      orchestrator: 'Connection',
      structural: 'OfficeBuilding',
      writer: 'EditPen',
      logic_editor: 'View',
      style_editor: 'MagicStick',
      compliance: 'Warning',
      knowledge: 'Reading',
      assembler: 'SetUp'
    }
    return iconMap[role] || 'Setting'
  }

  // 获取Agent标签
  function getAgentLabel(role) {
    if (AGENT_ROLE_LABELS[role]) {
      return AGENT_ROLE_LABELS[role].replace('Agent', '')
    }
    const agent = agentConfigs.find((a) => a.role === role)
    return agent?.label || role
  }

  // 获取Agent标签类型
  function getAgentTagType(agentName) {
    const typeMap = {
      结构师: 'primary',
      写手: 'success',
      逻辑编辑: 'warning',
      风格润色: '',
      合规审查: 'danger',
      合成: 'info'
    }
    return typeMap[agentName] || 'info'
  }

  // 获取消息标签类型
  function getMessageTagType(msg) {
    const agentRole = msg.data?.agent_role
    if (!agentRole) return 'info'

    const typeMap = {
      structural: 'primary',
      writer: 'success',
      logic_editor: 'warning',
      style_editor: '',
      compliance: 'danger',
      assembler: 'info'
    }
    return typeMap[agentRole] || 'info'
  }

  // 初始化加载
  async function initialize() {
    await loadModelConfigs()
    await loadProviders()
    await writingStore.fetchCurrentTask(projectState.projectId.value)
  }

  return {
    // 状态
    interrupting,
    testingAgent,
    showAgentConfigDialog,
    quickApplyConfigId,
    showContinueDialog,
    continueUnitCount,
    availableProviders,
    loadingProviders,
    modelConfigs,
    loadingConfigs,
    taskForm,

    // 计算属性
    configurableAgents,
    formattedDuration,
    hasGeneratedContent,
    canContinueGenerate,

    // 方法
    handleTestConnection,
    handleModeChange,
    handleCreateTask,
    handleInterrupt,
    handleResume,
    handleContinue,
    handleDelete,
    handleExport,
    handleExportUnit,
    loadProviders,
    loadModelConfigs,
    onModelConfigChange,
    applyToAllAgents,
    handleQuickApply,
    onProviderChange,
    getProviderModels,
    getAgentIcon,
    getAgentLabel,
    getAgentTagType,
    getMessageTagType,
    initialize
  }
}
