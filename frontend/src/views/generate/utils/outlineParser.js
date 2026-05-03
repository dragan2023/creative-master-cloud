/**
 * 大纲/内容解析工具函数
 * 从大纲文本中解析章节数、从生成内容中解析单元概述
 */

/**
 * 从全局大纲中解析章节数
 * @param {string} outlineContent - 大纲内容
 * @returns {number|null} 解析到的章节数，未找到则返回 null
 */
export function parseChapterCountFromOutline(outlineContent) {
  if (!outlineContent) return null
  
  // 尝试多种模式匹配章节数
  const patterns = [
    /共(\d+)章/,           // "共100章"
    /总计(\d+)章/,         // "总计100章"
    /(\d+)章.*全书/,       // "100章全书"
    /全书.*?(\d+)章/,      // "全书共100章"
    /第1章.*?第(\d+)章/,   // "第1章...第100章"（最后的章节号）
    /章节总数[：:]\s*(\d+)/, // "章节总数：100"
    /总章节数[：:]\s*(\d+)/, // "总章节数：100"
  ]
  
  for (const pattern of patterns) {
    const match = outlineContent.match(pattern)
    if (match) {
      const count = parseInt(match[1])
      if (count > 0 && count <= 1000) {  // 合理范围检查
        console.log(`[ParseOutline] 从大纲中解析到章节数: ${count} (模式: ${pattern.source})`)
        return count
      }
    }
  }
  
  // 如果没有找到明确标识，尝试找最大的章节号
  const chapterPattern = /第(\d+)章/g
  let maxChapter = 0
  let match
  while ((match = chapterPattern.exec(outlineContent)) !== null) {
    const chapterNum = parseInt(match[1])
    if (chapterNum > maxChapter) {
      maxChapter = chapterNum
    }
  }
  
  if (maxChapter > 0) {
    console.log(`[ParseOutline] 从大纲中找到最大章节号: ${maxChapter}`)
    return maxChapter
  }
  
  console.log(`[ParseOutline] 未能从大纲中解析到章节数`)
  return null
}

/**
 * 从生成内容中解析单元概述
 * @param {string} content - 生成的单元概述内容
 * @returns {Object} 键为单元号的单元概述对象
 */
export function parseUnitSummariesFromContent(content) {
  const result = {}
  const isMovie = content.includes('场') && !content.includes('集')
  
  // v2.4: 支持加粗标记的章节标题，兼容 ### **第X章：** 和 ### 第X章：
  const pattern = isMovie 
    ? /\*\*第(\d+)场[：:]\s*(.+?)(?:\n|$)/g
    : /###\s*\*{0,2}\s*第(\d+)(?:章|集)\s*\*{0,2}[：:]\s*(.+?)(?:\n|$)/g
  
  let match
  while ((match = pattern.exec(content)) !== null) {
    const unitNum = parseInt(match[1])
    const title = match[2].trim()
    
    // 提取梗概
    const summaryPattern = isMovie
      ? new RegExp(`\\*\\*本场梗概\\*\\*[：:]\\s*(.+?)(?:\\n\\n|\\n\\*\\*|$)`, 's')
      : new RegExp(`\\*\\*本(?:章|集)梗概\\*\\*[：:]\\s*(.+?)(?:\\n\\n|\\n\\*\\*|$)`, 's')
    
    const summaryMatch = content.slice(match.index, match.index + 500).match(summaryPattern)
    const summary = summaryMatch ? summaryMatch[1].trim() : ''
    
    // v2.1: 提取完整单元内容（从当前单元到下一单元之间）
    const nextUnitPattern = isMovie
      ? new RegExp(`\\*\\*第${unitNum + 1}场`)
      : new RegExp(`###\\s*第${unitNum + 1}(?:章|集)`)
    const nextMatch = content.slice(match.index).search(nextUnitPattern)
    const fullContent = nextMatch > 0 
      ? content.slice(match.index, match.index + nextMatch).trim()
      : content.slice(match.index).trim()
    
    result[unitNum.toString()] = {
      unit_id: `unit-${unitNum}-${Date.now().toString(36)}`,
      unit_number: unitNum,
      title: title,
      summary: summary,
      full_content: fullContent,
      status: 'completed'
    }
  }
  
  return result
}
