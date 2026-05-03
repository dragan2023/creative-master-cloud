/**
 * ResultViewer 单元状态与编辑逻辑组合式函数
 *
 * 封装单元概述计数、续生成判断、时长格式化、Markdown渲染等逻辑。
 */
import { computed, ref } from 'vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

export function useResultViewerUnits(props) {
  // ==================== 单元计数 ====================

  const existingUnitCount = computed(() => {
    return props.unitSummaries ? Object.keys(props.unitSummaries).length : 0
  })

  const canResumeUnitSummaries = computed(() => {
    const existing = existingUnitCount.value
    const expected = props.expectedUnitCount
    return existing > 0 && expected > 0 && existing < expected
  })

  const showResumeFromBackend = computed(() => {
    return props.backendResumeInfo?.can_resume === true
  })

  const remainingUnitCount = computed(() => {
    if (props.backendResumeInfo?.remaining_count !== undefined) {
      return props.backendResumeInfo.remaining_count
    }
    const existing = existingUnitCount.value
    const expected = props.expectedUnitCount
    return Math.max(0, expected - existing)
  })

  // ==================== 时长格式化 ====================

  function formatDuration(ms) {
    if (!ms || ms < 0) return ''
    const seconds = Math.floor(ms / 1000)
    const minutes = Math.floor(seconds / 60)
    const remainingSeconds = seconds % 60
    if (minutes > 0) {
      return `${minutes}分${remainingSeconds}秒`
    }
    return `${remainingSeconds}秒`
  }

  // ==================== Markdown 渲染 ====================

  const renderedGlobalOutline = computed(() => {
    if (!props.globalOutlineContent) return ''
    return DOMPurify.sanitize(marked(props.globalOutlineContent))
  })

  const renderedContent = computed(() => {
    if (!props.generatedContent) return ''
    return DOMPurify.sanitize(marked(props.generatedContent))
  })

  const renderedRevisionContent = computed(() => {
    if (!props.revisionContent) return ''
    return DOMPurify.sanitize(marked(props.revisionContent))
  })

  // ==================== 修订输入本地状态 ====================

  const localRevisionInput = ref('')

  // ==================== 文件上传 ====================

  const uploadedFiles = ref([])
  const fileInputRef = ref(null)

  function handleFileSelect(event) {
    const files = Array.from(event.target.files)
    uploadedFiles.value.push(...files)
  }

  function removeFile(index) {
    uploadedFiles.value.splice(index, 1)
  }

  return {
    existingUnitCount,
    canResumeUnitSummaries,
    showResumeFromBackend,
    remainingUnitCount,
    formatDuration,
    renderedGlobalOutline,
    renderedContent,
    renderedRevisionContent,
    localRevisionInput,
    uploadedFiles,
    fileInputRef,
    handleFileSelect,
    removeFile
  }
}
