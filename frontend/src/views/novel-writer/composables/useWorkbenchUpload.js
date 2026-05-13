/**
 * useWorkbenchUpload - 上传与知识库管理
 *
 * 从 useWorkbenchTask.js 提取的上传逻辑和知识库管理，
 * 包括大纲上传、单元概述上传、目录生成、知识库构建/删除。
 *
 * @module views/novel-writer/composables/useWorkbenchUpload
 */
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import { novelWriterApi } from '@/api/novel-writer'

/**
 * @param {Object} options
 * @param {import('vue').ComputedRef} options.projectId
 * @param {Function} options.loadProjectData
 * @param {import('vue').Ref} options.taskForm - 用于上传后自动填充 unit_count
 * @param {import('vue').ComputedRef} options.projectTotalUnits - 项目总单元数
 */
export function useWorkbenchUpload(options) {
  const { projectId, loadProjectData, taskForm, projectTotalUnits } = options

  // ==================== 知识库状态 ====================
  const kbStatus = ref({ status: 'pending' })
  const buildingKb = ref(false)

  async function loadKbStatus() {
    try {
      const res = await novelWriterApi.getKnowledgeBaseStatus(projectId.value)
      if (res.success) {
        kbStatus.value = res.data
      }
    } catch (error) {
      console.warn('加载知识库状态失败:', error)
    }
  }

  // ==================== 上传相关状态 ====================
  const showOutlineUploadDialog = ref(false)
  const uploadingOutline = ref(false)
  const showUnitSummariesUploadDialog = ref(false)
  const unitSummariesUploadMode = ref('file')
  const unitSummariesInput = ref('')
  const globalOutlineInput = ref('')
  const uploadingUnitSummaries = ref(false)
  const generatingDirectory = ref(false)

  // ==================== 大纲与目录 ====================

  async function handleUploadOutline(content) {
    if (!content?.trim()) {
      ElMessage.warning('请输入大纲内容')
      return
    }

    uploadingOutline.value = true
    try {
      const res = await novelWriterApi.updateProject(projectId.value, {
        outline_content: content,
      })

      if (res.success) {
        ElMessage.success('大纲上传成功')
        showOutlineUploadDialog.value = false
        if (loadProjectData) await loadProjectData()
      } else {
        ElMessage.error(res.message || '上传失败')
      }
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '上传失败')
    } finally {
      uploadingOutline.value = false
    }
  }

  async function handleGenerateDirectory() {
    generatingDirectory.value = true
    try {
      const res = await novelWriterApi.generateDirectory(projectId.value, {
        total_chapters: projectTotalUnits?.value || 10,
        chapter_naming_style: '数字编号',
        generate_names: true,
      })
      if (res.success) {
        ElMessage.success('目录生成成功')
        if (loadProjectData) await loadProjectData()
      } else {
        ElMessage.error(res.message || '目录生成失败')
      }
    } catch (error) {
      ElMessage.error('目录生成失败')
    } finally {
      generatingDirectory.value = false
    }
  }

  // ==================== 知识库 ====================

  async function handleDeleteKnowledgeBase() {
    try {
      const res = await novelWriterApi.deleteKnowledgeBase(projectId.value)
      if (res.success) {
        ElMessage.success('知识库已删除')
        kbStatus.value = { status: 'not_built', progress: null }
      }
    } catch (error) {
      ElMessage.error('删除知识库失败')
    }
  }

  async function handleBuildKnowledgeBase() {
    buildingKb.value = true
    try {
      const res = await novelWriterApi.buildKnowledgeBase(projectId.value)
      if (res.success) {
        ElMessage.success('知识库构建任务已启动')
        kbStatus.value = { status: 'building', progress: 0 }
        startKbPolling()
      } else {
        ElMessage.error(res.message || '构建失败')
      }
    } catch (error) {
      ElMessage.error('知识库构建失败')
    } finally {
      buildingKb.value = false
    }
  }

  let kbPollingTimer = null
  function startKbPolling() {
    if (kbPollingTimer) clearInterval(kbPollingTimer)
    kbPollingTimer = setInterval(async () => {
      try {
        const res = await novelWriterApi.getKnowledgeBaseStatus(projectId.value)
        if (res.success) {
          kbStatus.value = res.data
          if (res.data.status !== 'building') {
            clearInterval(kbPollingTimer)
            kbPollingTimer = null
            if (res.data.status === 'ready') {
              ElMessage.success('知识库构建完成')
            } else if (res.data.status === 'failed') {
              ElMessage.error('知识库构建失败')
            }
          }
        }
      } catch (error) {
        console.warn('轮询知识库状态失败:', error)
      }
    }, 2000)
  }

  // ==================== 单元概述上传 ====================

  function handleCancelUnitSummariesUpload() {
    showUnitSummariesUploadDialog.value = false
  }

  async function handleUploadUnitSummariesFile(options) {
    const file = options?.file
    if (!file) {
      ElMessage.warning('请选择要上传的文件')
      return
    }

    const validExtensions = ['.txt', '.md', '.doc', '.docx']
    const fileExt = file.name.substring(file.name.lastIndexOf('.')).toLowerCase()
    if (!validExtensions.includes(fileExt)) {
      ElMessage.error(`不支持的文件格式: ${fileExt}，支持 .txt, .md, .doc, .docx`)
      return
    }

    uploadingUnitSummaries.value = true
    try {
      const formData = new FormData()
      formData.append('file', file)

      const res = await novelWriterApi.uploadUnitSummariesFile(
        projectId.value,
        formData,
      )
      if (res.success) {
        const unitCount = res.data?.unit_count || 0
        ElMessage.success(res.data?.message || '单元概述上传成功')
        showUnitSummariesUploadDialog.value = false
        unitSummariesInput.value = ''
        globalOutlineInput.value = ''
        if (unitCount > 0 && !taskForm.value.unit_count) {
          taskForm.value.unit_count = unitCount
        }
        if (loadProjectData) await loadProjectData()
      } else {
        ElMessage.error(res.data?.message || '上传失败')
      }
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '上传失败')
    } finally {
      uploadingUnitSummaries.value = false
    }
  }

  async function handleUploadUnitSummariesContent(contentData) {
    if (!contentData || !contentData.parsedData) {
      ElMessage.warning('请输入单元概述内容')
      return
    }

    const unitSummaries = contentData.parsedData

    if (typeof unitSummaries !== 'object' || Array.isArray(unitSummaries)) {
      ElMessage.error('单元概述格式错误，应为对象格式')
      return
    }

    uploadingUnitSummaries.value = true
    try {
      const data = { unit_summaries: unitSummaries }
      if (globalOutlineInput.value.trim()) {
        data.global_outline = globalOutlineInput.value.trim()
      }

      const res = await novelWriterApi.uploadUnitSummaries(
        projectId.value,
        data,
      )
      if (res.success) {
        const unitCount = res.data?.unit_count || 0
        ElMessage.success(res.data?.message || '单元概述上传成功')
        showUnitSummariesUploadDialog.value = false
        unitSummariesInput.value = ''
        globalOutlineInput.value = ''
        if (unitCount > 0 && !taskForm.value.unit_count) {
          taskForm.value.unit_count = unitCount
        }
        if (loadProjectData) await loadProjectData()
      } else {
        ElMessage.error(res.data?.message || '上传失败')
      }
    } catch (error) {
      ElMessage.error(error.response?.data?.detail || '上传失败')
    } finally {
      uploadingUnitSummaries.value = false
    }
  }

  return {
    // 知识库
    kbStatus,
    buildingKb,
    loadKbStatus,
    handleBuildKnowledgeBase,
    handleDeleteKnowledgeBase,

    // 上传状态
    showOutlineUploadDialog,
    uploadingOutline,
    showUnitSummariesUploadDialog,
    unitSummariesUploadMode,
    unitSummariesInput,
    globalOutlineInput,
    uploadingUnitSummaries,
    generatingDirectory,

    // 上传方法
    handleUploadOutline,
    handleGenerateDirectory,
    handleCancelUnitSummariesUpload,
    handleUploadUnitSummariesFile,
    handleUploadUnitSummariesContent,
  }
}
