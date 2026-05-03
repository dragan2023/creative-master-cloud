/**
 * 导入逻辑 composable
 * 管理大纲导入、单元概述导入和文件上传处理
 */
import { ElMessage } from 'element-plus'
import { parseUnitSummariesFromContent } from '../utils/outlineParser'

export function useImportLogic(deps) {
  const {
    type,
    globalOutlineContent,
    generatedContent,
    unitSummaries,
    outlineStage,
    showResult,
    showImportDialog,
    importType,
    importContent,
    importingOutline,
    importOutlineProgress,
    showImportUnitSummariesDialog,
    importingUnitSummaries,
    importUnitSummariesProgress,
    importedUnitSummaries,
    importedOutline,
    qcApplied,
    qcReportData,
    issuesFixed
  } = deps

  // ==================== 大纲导入 ====================

  function openImportDialog() {
    importType.value = 'global'
    importContent.value = ''
    importingOutline.value = false
    importOutlineProgress.value = 0
    showImportDialog.value = true
  }

  function confirmImport() {
    if (!importContent.value.trim()) {
      ElMessage.warning('请上传要导入的大纲文件')
      return
    }

    // v2.3新增：标记为导入大纲
    importedOutline.value = true
    qcApplied.value = false
    qcReportData.value = null
    issuesFixed.value = 0

    if (importType.value === 'global') {
      globalOutlineContent.value = importContent.value.trim()
      generatedContent.value = importContent.value.trim()
      outlineStage.value = 2
      showResult.value = true
      ElMessage.success('全局大纲已导入，您可以编辑后继续生成单元概述')
    } else {
      try {
        const parsed = parseUnitSummariesFromContent(importContent.value)
        if (Object.keys(parsed).length > 0) {
          unitSummaries.value = parsed
          // v2.4: 兼容加粗标记的章节标题
          const globalOutlineMatch = importContent.value.match(/^([\s\S]*?)(?=###\s*\*{0,2}\s*第\d+(?:章|集)\s*\*{0,2}[：:])/)
          if (globalOutlineMatch) {
            globalOutlineContent.value = globalOutlineMatch[1].trim()
          } else {
            globalOutlineContent.value = importContent.value.split('###')[0].trim()
          }
          generatedContent.value = importContent.value
          outlineStage.value = 4
          showResult.value = true
          ElMessage.success('完整大纲已导入，您可以编辑后下载')
        } else {
          globalOutlineContent.value = importContent.value.trim()
          generatedContent.value = importContent.value.trim()
          outlineStage.value = 2
          showResult.value = true
          ElMessage.warning('无法解析单元概述，已作为全局大纲导入')
        }
      } catch (error) {
        console.error('解析导入内容失败:', error)
        globalOutlineContent.value = importContent.value.trim()
        generatedContent.value = importContent.value.trim()
        outlineStage.value = 2
        showResult.value = true
        ElMessage.warning('导入内容已作为全局大纲处理')
      }
    }

    showImportDialog.value = false
  }

  // 导入文件上传前验证
  function beforeOutlineImportUpload(file) {
    const isLt100M = file.size / 1024 / 1024 < 100
    if (!isLt100M) {
      ElMessage.error('文件大小不能超过 100MB!')
      return false
    }

    const allowedTypes = ['.md', '.txt', '.docx', '.doc']
    const fileName = file.name.toLowerCase()
    const isValidType = allowedTypes.some(ext => fileName.endsWith(ext))

    if (!isValidType) {
      ElMessage.error('只支持 .md、.txt、.docx、.doc 格式的文件!')
      return false
    }

    importingOutline.value = true
    importOutlineProgress.value = 0
    return true
  }

  // 导入文件上传成功
  function handleOutlineImportUploadSuccess(response, file) {
    importingOutline.value = false
    importOutlineProgress.value = 100

    try {
      if (response.code === 200 && response.data) {
        const content = response.data.content || response.data.outline_content || ''

        if (!content.trim()) {
          ElMessage.warning('上传的文件内容为空')
          return
        }

        importContent.value = content

        // 自动确认导入
        confirmImport()

        ElMessage.success('文件上传成功')
      } else {
        ElMessage.error(response.message || '文件上传失败')
      }
    } catch (error) {
      console.error('处理上传响应失败:', error)
      ElMessage.error('文件上传失败')
    }
  }

  // 导入文件上传失败
  function handleOutlineImportUploadError(error, file) {
    importingOutline.value = false
    importOutlineProgress.value = 0
    console.error('文件上传失败:', error)
    ElMessage.error('文件上传失败，请重试')
  }

  // 导入文件上传进度
  function handleOutlineImportProgress(event, file) {
    importOutlineProgress.value = Math.round(event.percent)
  }

  // ==================== 单元概述导入 ====================

  function openImportUnitSummariesDialog() {
    importingUnitSummaries.value = false
    importUnitSummariesProgress.value = 0
    showImportUnitSummariesDialog.value = true
  }

  // 上传前验证
  function beforeUnitSummariesImportUpload(file) {
    const isLt100M = file.size / 1024 / 1024 < 100
    if (!isLt100M) {
      ElMessage.error('文件大小不能超过 100MB!')
      return false
    }

    const allowedTypes = ['.md', '.txt', '.docx', '.doc']
    const fileName = file.name.toLowerCase()
    const isValidType = allowedTypes.some(ext => fileName.endsWith(ext))

    if (!isValidType) {
      ElMessage.error('只支持 .md、.txt、.docx、.doc 格式的文件!')
      return false
    }

    importingUnitSummaries.value = true
    importUnitSummariesProgress.value = 0
    return true
  }

  // 上传成功处理
  function handleUnitSummariesImportUploadSuccess(response, file) {
    importingUnitSummaries.value = false
    importUnitSummariesProgress.value = 100

    try {
      if (response.code === 200 && response.data) {
        const content = response.data.content || ''

        if (!content.trim()) {
          ElMessage.warning('上传的文件内容为空')
          return
        }

        const parsed = parseUnitSummariesFromContent(content)

        console.log('[单元概述导入调试] 原始内容长度:', content.length)
        console.log('[单元概述导入调试] 解析到的单元数:', Object.keys(parsed).length)
        console.log('[单元概述导入调试] 解析到的单元key:', Object.keys(parsed))

        if (Object.keys(parsed).length > 0) {
          unitSummaries.value = parsed

          // 从导入内容中提取全局大纲
          // v2.4: 兼容加粗标记的章节标题
          const globalOutlineMatch = content.match(/^([\s\S]*?)(?=###\s*\*{0,2}\s*第\d+(?:章|集)\s*\*{0,2}[：:]|###\s*\*{0,2}\s*第\d+集\s*\*{0,2}[：:]|\*\*第\d+集\*\*[：:])/)
          if (globalOutlineMatch && globalOutlineMatch[1].trim()) {
            globalOutlineContent.value = globalOutlineMatch[1].trim()
            console.log('[单元概述导入] 已提取全局大纲，长度:', globalOutlineContent.value.length)
          } else {
            const firstPart = content.split(/###\s*第\d+章[:：]|###\s*第\d+集[:：]|\*\*第\d+集\*\*[:：]/)[0]
            if (firstPart && firstPart.trim().length > 50) {
              globalOutlineContent.value = firstPart.trim()
              console.log('[单元概述导入] 从文件前部分提取全局大纲，长度:', globalOutlineContent.value.length)
            } else {
              globalOutlineContent.value = ''
              console.warn('[单元概述导入] 未找到全局大纲内容，质控检测可能不准确')
            }
          }

          generatedContent.value = content
          outlineStage.value = 4
          showResult.value = true
          importedUnitSummaries.value = true

          console.log('[单元概述导入调试] outlineStage已设置为:', outlineStage.value)
          console.log('[单元概述导入调试] generatedContent长度:', generatedContent.value.length)
          console.log('[单元概述导入调试] unitSummaries数量:', Object.keys(unitSummaries.value).length)

          // 重置质控状态
          qcApplied.value = false
          qcReportData.value = null
          issuesFixed.value = 0

          const outlineInfo = globalOutlineContent.value
            ? `（已提取全局大纲 ${globalOutlineContent.value.length} 字）`
            : '（⚠️ 未检测到全局大纲，建议先导入全局大纲以保证质控准确性）'

          ElMessage.success(`单元概述导入成功，共解析 ${Object.keys(parsed).length} 章 ${outlineInfo}`)

          showImportUnitSummariesDialog.value = false
        } else {
          ElMessage.error('无法解析单元概述内容，请检查文件格式')
        }
      } else {
        ElMessage.error(response.message || '文件上传失败')
      }
    } catch (error) {
      console.error('处理上传响应失败:', error)
      ElMessage.error('文件上传失败')
    }
  }

  // 上传失败处理
  function handleUnitSummariesImportUploadError(error, file) {
    importingUnitSummaries.value = false
    importUnitSummariesProgress.value = 0
    console.error('文件上传失败:', error)
    ElMessage.error('文件上传失败，请重试')
  }

  // 上传进度
  function handleUnitSummariesImportProgress(event, file) {
    importUnitSummariesProgress.value = Math.round(event.percent)
  }

  return {
    openImportDialog,
    confirmImport,
    beforeOutlineImportUpload,
    handleOutlineImportUploadSuccess,
    handleOutlineImportUploadError,
    handleOutlineImportProgress,
    openImportUnitSummariesDialog,
    beforeUnitSummariesImportUpload,
    handleUnitSummariesImportUploadSuccess,
    handleUnitSummariesImportUploadError,
    handleUnitSummariesImportProgress
  }
}
