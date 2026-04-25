/**
 * Diff应用工具 - 将LLM输出的差异指令应用到完整内容
 * 前端版本，对应后端 backend/app/utils/diff_applier.py
 */

/**
 * 应用差异指令到内容
 * @param {string} content - 当前完整内容
 * @param {Object} diffInstructions - LLM输出的差异指令JSON
 * @returns {string} 修改后的完整内容
 */
export function applyDiffInstructions(content, diffInstructions) {
  const modifications = diffInstructions?.modifications || []

  if (!modifications.length) {
    console.warn('[diffApplier] No modifications found in diff instructions')
    return content
  }

  // 按location排序,从后往前应用(避免位置偏移)
  const sorted = [...modifications].sort((a, b) =>
    (b.location || '').localeCompare(a.location || '')
  )

  let modifiedContent = content
  let appliedCount = 0
  let failedCount = 0

  for (const mod of sorted) {
    const modType = mod.type
    const originalText = mod.original_text || ''
    const newText = mod.new_text || ''
    const location = mod.location || ''

    try {
      if (modType === 'replace') {
        if (originalText && modifiedContent.includes(originalText)) {
          modifiedContent = modifiedContent.replace(originalText, newText)
          appliedCount++
        } else {
          modifiedContent = fuzzyReplace(modifiedContent, location, originalText, newText)
          appliedCount++
        }
      } else if (modType === 'insert') {
        modifiedContent = insertAtLocation(modifiedContent, location, newText)
        appliedCount++
      } else if (modType === 'delete') {
        if (originalText && modifiedContent.includes(originalText)) {
          modifiedContent = modifiedContent.replace(originalText, '')
          appliedCount++
        } else {
          console.warn(`[diffApplier] Failed to delete text at ${location}: text not found`)
          failedCount++
        }
      } else {
        console.warn(`[diffApplier] Unknown modification type: ${modType}`)
        failedCount++
      }
    } catch (e) {
      console.error(`[diffApplier] Error applying modification at ${location}:`, e)
      failedCount++
    }
  }

  console.log(`[diffApplier] Diff applied: ${appliedCount} succeeded, ${failedCount} failed`)
  return modifiedContent
}

/**
 * 模糊匹配替换
 */
function fuzzyReplace(content, location, original, newText) {
  // 尝试从location提取段落号
  const paragraphMatch = location.match(/第(\d+)段/)
  if (paragraphMatch) {
    const paragraphNum = parseInt(paragraphMatch[1])
    const paragraphs = content.split('\n\n')
    if (paragraphNum > 0 && paragraphNum <= paragraphs.length) {
      const targetPara = paragraphs[paragraphNum - 1]
      if (targetPara.includes(original)) {
        paragraphs[paragraphNum - 1] = targetPara.replace(original, newText)
        return paragraphs.join('\n\n')
      }
    }
  }

  // 尝试从location提取行号
  const lineMatch = location.match(/第(\d+)行/)
  if (lineMatch) {
    const lineNum = parseInt(lineMatch[1])
    const lines = content.split('\n')
    if (lineNum > 0 && lineNum <= lines.length) {
      const targetLine = lines[lineNum - 1]
      if (targetLine.includes(original)) {
        lines[lineNum - 1] = targetLine.replace(original, newText)
        return lines.join('\n')
      }
    }
  }

  // 降级策略: 如果原文较短,尝试全局模糊匹配
  if (original.length < 50 && content.includes(original)) {
    return content.replace(original, newText)
  }

  console.error(`[diffApplier] Fuzzy replace failed for location: ${location}`)
  return content
}

/**
 * 在指定位置插入文本
 */
function insertAtLocation(content, location, newText) {
  const paragraphMatch = location.match(/第(\d+)段/)
  if (paragraphMatch) {
    const paragraphNum = parseInt(paragraphMatch[1])
    const paragraphs = content.split('\n\n')
    const insertAfter = location.includes('后')
    const idx = insertAfter ? paragraphNum : paragraphNum - 1
    if (idx >= 0 && idx <= paragraphs.length) {
      paragraphs.splice(idx, 0, newText)
      return paragraphs.join('\n\n')
    }
  }

  const lineMatch = location.match(/第(\d+)行/)
  if (lineMatch) {
    const lineNum = parseInt(lineMatch[1])
    const lines = content.split('\n')
    const insertAfter = location.includes('后')
    const idx = insertAfter ? lineNum : lineNum - 1
    if (idx >= 0 && idx <= lines.length) {
      lines.splice(idx, 0, newText)
      return lines.join('\n')
    }
  }

  // 降级策略: 追加到末尾
  console.warn(`[diffApplier] Insert at location failed: ${location}, appending to end`)
  return content + '\n\n' + newText
}

/**
 * 验证差异指令格式
 * @param {Object} diffInstructions - LLM输出的差异指令JSON
 * @returns {boolean} 是否有效
 */
export function validateDiffInstructions(diffInstructions) {
  if (!diffInstructions || typeof diffInstructions !== 'object') {
    return false
  }
  if (!Array.isArray(diffInstructions.modifications)) {
    return false
  }
  for (const mod of diffInstructions.modifications) {
    if (!mod || typeof mod !== 'object') return false
    if (!mod.type || !['replace', 'insert', 'delete'].includes(mod.type)) return false
    if (!mod.location) return false
  }
  return true
}
