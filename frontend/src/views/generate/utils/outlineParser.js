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
  const chapterPattern = /第(\d+)(?:章|集|场)/g
  let maxChapter = 0
  let match
  while ((match = chapterPattern.exec(outlineContent)) !== null) {
    const chapterNum = parseInt(match[1])
    if (chapterNum > maxChapter) {
      maxChapter = chapterNum
    }
  }
  
  if (maxChapter > 0) {
    console.log(`[ParseOutline] 从大纲中找到最大单元号: ${maxChapter}`)
    return maxChapter
  }
  
  console.log(`[ParseOutline] 未能从大纲中解析到单元数`)
  return null
}

/**
 * 从生成内容中解析单元概述
 * @param {string} content - 生成的单元概述内容
 * @param {string} contentType - 可选的内容类型 (novel/series_outline/movie_outline/...)，用于精确判断单元字符
 * @returns {Object} 键为单元号的单元概述对象
 */
export function parseUnitSummariesFromContent(content, contentType) {
  const result = {}
  if (!content) return result

  // [2026-05-05] 修复：优先使用显式content_type，回退到基于内容推测
  const isMovie = contentType
    ? contentType.includes('movie')
    : (content.includes('场') && !content.includes('集'))
  const isSeries = contentType
    ? contentType.includes('series')
    : (content.includes('集') && !content.includes('场'))
  const unitChar = isMovie ? '场' : (isSeries ? '集' : '章')

  // [2026-05-05] 修复：支持**第N集**：和**第N集：**两种bold格式
  // ### 第N章：、**第N集**：、**第N集：、第N场**：、第N集：（纯文本）
  const pattern = new RegExp(
    `(?:###\\s*|\\*\\*)\\s*第(\\d+)${unitChar}(?:\\*\\*)?[：:]\\s*(.+?)(?:\\n|$)`,
    'g'
  )

  let match
  while ((match = pattern.exec(content)) !== null) {
    const unitNum = parseInt(match[1])
    // [2026-05-05] 修复：去除标题末尾可能残留的**标记
    let title = match[2].trim().replace(/\*\*$/, '').trim()

    // 提取梗概（根据单元类型使用不同的梗概标签）
    const summaryLabel = isMovie ? '本场' : (isSeries ? '本集' : '本章')
    const summaryPattern = new RegExp(
      `\\*\\*${summaryLabel}梗概\\*\\*[：:]\\s*(.+?)(?:\\n\\n|\\n\\*\\*|$)`,
      's'
    )

    const summaryMatch = content.slice(match.index, match.index + 500).match(summaryPattern)
    const summary = summaryMatch ? summaryMatch[1].trim() : ''

    // [2026-05-05] 修复：匹配下一个单元边界，使用动态unitChar
    const nextUnitPattern = new RegExp(
      `(?:###\\s*|\\*\\*)\\s*第${unitNum + 1}${unitChar}`
    )
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
