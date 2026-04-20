/**
 * 工作流逻辑 composable
 * 管理工作流程步骤、事件处理和结果操作
 */
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'

// 工作流程步骤图标映射
export const stepIcons = {
  model: 'Cpu',
  prompt: 'Document',
  search: 'Search',
  knowledge: 'FolderOpened',
  preset_kb: 'Collection',
  webpage: 'Link',
  generate: 'ChatDotRound',
  evaluate: 'DataAnalysis',
  reflect: 'Refresh',
  verify: 'CircleCheck',
  correct: 'Edit',
  consistency: 'CircleCheckFilled',
  autofix: 'Tools',
  // 续生成相关
  resume_detection: 'RefreshRight',
  merge_content: 'Connection',
  // 质量管控相关
  qc_layer1: 'Search',
  qc_layer2: 'Link',
  qc_layer3: 'DataBoard',
  quality_control: 'DataAnalysis',
  boundary_check: 'Connection',
  global_check: 'Monitor'
}

export function useWorkflow(type, form, generatedContent, currentGenerationId) {
  // 工作流程状态
  const workflowSteps = ref([])
  const currentStep = ref('')
  const workflowComplete = ref(false)
  
  // 质量管控报告
  const qualityReport = ref(null)

  // 生成耗时
  const generationDuration = ref(null)
  
  // 截断检测状态(新增)
  const truncationInfo = ref(null)
  const isContinuing = ref(false)

  // 处理工作流程事件
  const handleWorkflowEvent = (event) => {
    console.log('[Workflow] 收到事件:', event)
    if (event.type === 'start') {
      workflowSteps.value = []
    } else if (event.type === 'step') {
      const existingIndex = workflowSteps.value.findIndex(s => s.step === event.step)
      const stepData = {
        step: event.step,
        status: event.status,
        message: event.message,
        icon: event.icon || stepIcons[event.step] || 'Loading'
      }
      
      if (existingIndex >= 0) {
        const existingStep = workflowSteps.value[existingIndex]
        if (existingStep.status === 'done' && event.status === 'running') {
          console.log('[Workflow] 步骤已完成，忽略 running 事件:', event.step)
        } else {
          workflowSteps.value[existingIndex] = stepData
        }
      } else {
        workflowSteps.value.push(stepData)
      }
      
      if (event.status === 'running') {
        currentStep.value = event.step
      }
    } else if (event.type === 'complete') {
      workflowComplete.value = true
    } else if (event.type === 'error') {
      workflowSteps.value.push({
        step: 'error',
        status: 'error',
        message: event.message,
        icon: 'Warning'
      })
    } else if (event.type === 'quality_report') {
      qualityReport.value = event.report
      console.log('[Workflow] 收到质量管控报告:', event.report)
    } else if (event.type === 'truncation_detected') {
      // 新增:截断检测事件
      truncationInfo.value = event.truncation_info
      console.log('[Workflow] 检测到截断:', event.truncation_info)
      ElMessage.warning(event.message || '检测到内容截断')
    } else if (event.type === 'continuation_start') {
      // 新增:接续生成开始
      isContinuing.value = true
      workflowSteps.value.push({
        step: 'continuation',
        status: 'running',
        message: event.message || '正在接续生成...',
        icon: 'RefreshRight'
      })
    } else if (event.type === 'continuation_complete') {
      // 新增:接续生成完成
      isContinuing.value = false
      workflowSteps.value.push({
        step: 'continuation',
        status: 'done',
        message: event.message || '接续生成完成',
        icon: 'CircleCheck'
      })
      ElMessage.success(event.message || '接续生成完成')
    }
    // 注意：resume_detection 事件的格式为 {type: "step", step: "resume_detection", ...}
    // 它会由上方 event.type === 'step' 分支统一处理，无需单独处理
  }

  // 格式化耗时显示
  const formatDuration = (ms) => {
    if (!ms || ms < 0) return ''
    
    const seconds = Math.floor(ms / 1000)
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = seconds % 60
    
    if (minutes > 0) {
      return `${minutes}分${remainingSeconds}秒`
    } else {
      return `${remainingSeconds}秒`
    }
  }

  // 复制结果
  const copyResult = async () => {
    try {
      await navigator.clipboard.writeText(generatedContent.value)
      ElMessage.success('已复制到剪贴板')
      trackAction('copy')
    } catch (error) {
      ElMessage.error('复制失败')
    }
  }

  // 下载结果
  const downloadResult = () => {
    const blob = new Blob([generatedContent.value], { type: 'text/markdown' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `${form.value.title || '创意内容'}.md`
    a.click()
    URL.revokeObjectURL(url)
    trackAction('download')
  }

  // 追踪用户行为
  const trackAction = async (actionType) => {
    try {
      const { actionApi } = await import('@/api')
      await actionApi.track({
        generation_id: currentGenerationId.value,
        module: type.value,
        action: actionType,
        content_snippet: generatedContent.value?.substring(0, 100)
      })
    } catch (error) {
      console.error('追踪行为失败:', error)
    }
  }

  return {
    // 状态
    workflowSteps,
    currentStep,
    workflowComplete,
    generationDuration,
    qualityReport,
    truncationInfo,  // 新增
    isContinuing,    // 新增
    
    // 方法
    handleWorkflowEvent,
    formatDuration,
    copyResult,
    downloadResult,
    trackAction
  }
}
