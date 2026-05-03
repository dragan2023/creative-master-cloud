/**
 * 写作工作台步骤引导组合式函数
 * 
 * 追踪用户操作进度，提供步骤引导
 * 
 * @module useWorkbenchGuide
 */

import { ref, computed } from 'vue'

const STORAGE_PREFIX = 'workbench_guide_'

/**
 * 写作工作台步骤引导
 */
export function useWorkbenchGuide(projectId) {
  // 步骤定义
  const steps = [
    {
      key: 'upload_outline',
      title: '上传大纲',
      description: '上传小说/剧本大纲文件（.txt/.md/.docx）',
      required: true,
      icon: '📄'
    },
    {
      key: 'upload_unit_summaries',
      title: '上传单元概述',
      description: '上传单元概述指导AI生成正文（小说类型必需）',
      required: true,
      icon: '📋'
    },
    {
      key: 'build_knowledge_base',
      title: '构建知识库',
      description: '基于大纲构建项目专属知识库（可选，推荐）',
      required: false,
      icon: '🧠'
    },
    {
      key: 'config_generation',
      title: '配置生成参数',
      description: '设置起始单元、生成数量、并发数等',
      required: true,
      icon: '⚙️'
    },
    {
      key: 'start_generation',
      title: '开始生成',
      description: '启动多Agent协作生成正文',
      required: true,
      icon: '🚀'
    }
  ]
  
  // 当前进度状态
  const completedSteps = ref(new Set())
  const currentStepIndex = ref(0)
  const showGuideDialog = ref(false)
  
  // 从localStorage加载进度
  function loadProgress() {
    try {
      const saved = localStorage.getItem(`${STORAGE_PREFIX}${projectId}`)
      if (saved) {
        const data = JSON.parse(saved)
        completedSteps.value = new Set(data.completed || [])
        currentStepIndex.value = data.currentStep || 0
      }
    } catch (error) {
      console.warn('[WorkbenchGuide] 加载进度失败:', error)
    }
  }
  
  // 保存进度到localStorage
  function saveProgress() {
    try {
      localStorage.setItem(`${STORAGE_PREFIX}${projectId}`, JSON.stringify({
        completed: Array.from(completedSteps.value),
        currentStep: currentStepIndex.value
      }))
    } catch (error) {
      console.warn('[WorkbenchGuide] 保存进度失败:', error)
    }
  }
  
  // 计算当前应该高亮的步骤
  function calculateCurrentStep(hasOutline, hasUnitSummaries, hasKnowledgeBase, hasConfig) {
    let step = 0
    
    if (!hasOutline) {
      step = 0
    } else if (!hasUnitSummaries) {
      step = 1
      markStepComplete('upload_outline')
    } else if (!hasKnowledgeBase && steps[2].required) {
      step = 2
      markStepComplete('upload_unit_summaries')
    } else if (!hasConfig) {
      step = 3
      markStepComplete('build_knowledge_base')
    } else {
      step = 4
      markStepComplete('config_generation')
    }
    
    currentStepIndex.value = step
    saveProgress()
    return step
  }
  
  // 标记步骤完成
  function markStepComplete(stepKey) {
    if (!completedSteps.value.has(stepKey)) {
      completedSteps.value.add(stepKey)
      saveProgress()
    }
  }
  
  // 获取步骤状态
  function getStepStatus(stepIndex) {
    const step = steps[stepIndex]
    if (!step) return 'pending'
    
    if (completedSteps.value.has(step.key)) {
      return 'completed'
    }
    if (stepIndex === currentStepIndex.value) {
      return 'active'
    }
    return 'pending'
  }
  
  // 显示引导对话框
  function showGuide() {
    showGuideDialog.value = true
  }
  
  // 隐藏引导对话框
  function hideGuide() {
    showGuideDialog.value = false
  }
  
  // 跳转到指定步骤
  function goToStep(stepIndex) {
    currentStepIndex.value = stepIndex
  }
  
  // 重置引导进度
  function resetProgress() {
    completedSteps.value.clear()
    currentStepIndex.value = 0
    localStorage.removeItem(`${STORAGE_PREFIX}${projectId}`)
  }
  
  // 计算属性
  const allRequiredComplete = computed(() => {
    return steps
      .filter(s => s.required)
      .every(s => completedSteps.value.has(s.key))
  })
  
  const completionPercentage = computed(() => {
    const completed = completedSteps.value.size
    const total = steps.length
    return Math.round((completed / total) * 100)
  })
  
  return {
    steps,
    completedSteps,
    currentStepIndex,
    showGuideDialog,
    allRequiredComplete,
    completionPercentage,
    
    loadProgress,
    saveProgress,
    calculateCurrentStep,
    markStepComplete,
    getStepStatus,
    showGuide,
    hideGuide,
    goToStep,
    resetProgress
  }
}
