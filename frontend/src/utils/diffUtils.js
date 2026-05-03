/**
 * 文本差异对比工具函数
 * 
 * 提供两段文本的差异计算和高亮 HTML 生成功能。
 * 小文本使用 LCS（最长公共子序列）算法精确对比，
 * 大文本使用哈希集合快速匹配。
 * 
 * @module utils/diffUtils
 */

/**
 * HTML 转义
 * @param {string} text - 原始文本
 * @returns {string} 转义后的 HTML 安全文本
 */
export function escapeHtml(text) {
  if (!text) return ''
  return text
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;')
    .replace(/ /g, '&nbsp;')  // 保留空格
}

/**
 * 找出两个数组的最长公共子序列（LCS）
 * 使用动态规划算法，时间复杂度 O(m*n)
 * @param {Array} arr1 - 第一个数组
 * @param {Array} arr2 - 第二个数组
 * @returns {Array} 最长公共子序列
 */
export function findLCS(arr1, arr2) {
  const m = arr1.length, n = arr2.length
  const dp = Array(m + 1).fill(null).map(() => Array(n + 1).fill(0))
  
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (arr1[i - 1] === arr2[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1])
      }
    }
  }
  
  // 回溯找出 LCS
  const lcs = []
  let i = m, j = n
  while (i > 0 && j > 0) {
    if (arr1[i - 1] === arr2[j - 1]) {
      lcs.unshift(arr1[i - 1])
      i--
      j--
    } else if (dp[i - 1][j] > dp[i][j - 1]) {
      i--
    } else {
      j--
    }
  }
  
  return lcs
}

/**
 * 使用LCS算法计算差异（适用于小文本，≤100段）
 * @param {string[]} oldParagraphs - 旧段落数组
 * @param {string[]} newParagraphs - 新段落数组
 * @returns {string} 带差异标记的 HTML
 */
export function computeDiffWithLCS(oldParagraphs, newParagraphs) {
  const lcs = findLCS(oldParagraphs, newParagraphs)
  
  let html = ''
  let oldIdx = 0, newIdx = 0, lcsIdx = 0
  
  while (oldIdx < oldParagraphs.length || newIdx < newParagraphs.length) {
    if (lcsIdx < lcs.length && oldIdx < oldParagraphs.length && 
        oldParagraphs[oldIdx] === lcs[lcsIdx] && 
        newIdx < newParagraphs.length && newParagraphs[newIdx] === lcs[lcsIdx]) {
      // 相同段落
      html += `<div class="diff-paragraph unchanged">${escapeHtml(oldParagraphs[oldIdx])}</div>`
      oldIdx++
      newIdx++
      lcsIdx++
    } else if (newIdx < newParagraphs.length &&
               (lcsIdx >= lcs.length || newParagraphs[newIdx] !== lcs[lcsIdx])) {
      // 新增或修改的段落
      if (oldIdx < oldParagraphs.length &&
          (lcsIdx >= lcs.length || oldParagraphs[oldIdx] !== lcs[lcsIdx])) {
        // 修改：旧段落被删除，新段落是新增
        html += `<div class="diff-paragraph removed">${escapeHtml(oldParagraphs[oldIdx])}</div>`
        html += `<div class="diff-paragraph added">${escapeHtml(newParagraphs[newIdx])}</div>`
        oldIdx++
        newIdx++
      } else {
        // 纯新增
        html += `<div class="diff-paragraph added">${escapeHtml(newParagraphs[newIdx])}</div>`
        newIdx++
      }
    } else if (oldIdx < oldParagraphs.length &&
               (lcsIdx >= lcs.length || oldParagraphs[oldIdx] !== lcs[lcsIdx])) {
      // 纯删除
      html += `<div class="diff-paragraph removed">${escapeHtml(oldParagraphs[oldIdx])}</div>`
      oldIdx++
    }
  }
  
  return html
}

/**
 * 简单差异对比（适用于大文本，>100段）
 * 使用哈希集合快速匹配
 * @param {string[]} oldParagraphs - 旧段落数组
 * @param {string[]} newParagraphs - 新段落数组
 * @returns {string} 带差异标记的 HTML
 */
export function computeDiffSimple(oldParagraphs, newParagraphs) {
  // 构建新段落集合
  const newSet = new Set(newParagraphs)
  const oldSet = new Set(oldParagraphs)
  
  let html = ''
  
  // 先处理旧段落
  for (const para of oldParagraphs) {
    if (newSet.has(para)) {
      // 相同段落
      html += `<div class="diff-paragraph unchanged">${escapeHtml(para)}</div>`
    } else {
      // 被删除的段落
      html += `<div class="diff-paragraph removed">${escapeHtml(para)}</div>`
    }
  }
  
  // 找出新增的段落
  for (const para of newParagraphs) {
    if (!oldSet.has(para)) {
      html += `<div class="diff-paragraph added">${escapeHtml(para)}</div>`
    }
  }
  
  return html
}

/**
 * 计算两段文本的差异，生成带高亮的 HTML
 * 使用优化的行级对比算法：
 * - 段落数 ≤ 100：使用 LCS 算法精确对比
 * - 段落数 > 100：使用哈希集合快速匹配
 * 
 * @param {string} oldText - 原始文本
 * @param {string} newText - 新文本
 * @returns {string} 带差异标记的 HTML
 */
export function computeDiffHtml(oldText, newText) {
  if (!oldText && !newText) return ''
  if (!oldText) return `<div class="diff-paragraph added">${escapeHtml(newText)}</div>`
  if (!newText) return `<div class="diff-paragraph removed">${escapeHtml(oldText)}</div>`
  
  // 按段落分割
  const oldParagraphs = oldText.split(/\n+/).filter(p => p.trim())
  const newParagraphs = newText.split(/\n+/).filter(p => p.trim())
  
  // 对于小文本使用LCS，大文本使用简单对比
  if (oldParagraphs.length <= 100 && newParagraphs.length <= 100) {
    return computeDiffWithLCS(oldParagraphs, newParagraphs)
  } else {
    return computeDiffSimple(oldParagraphs, newParagraphs)
  }
}
