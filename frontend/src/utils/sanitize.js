/**
 * HTML内容消毒工具
 * 
 * 使用DOMPurify对所有v-html渲染的内容进行XSS防护
 * 统一配置允许的标签和属性，确保安全性和功能性平衡
 * 
 * @module utils/sanitize
 */

import DOMPurify from 'dompurify'

/**
 * 默认允许的HTML标签（用于Markdown渲染内容）
 */
const DEFAULT_ALLOWED_TAGS = [
  'p', 'br', 'strong', 'em', 'u', 's', 'blockquote',
  'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
  'ul', 'ol', 'li',
  'a', 'code', 'pre',
  'table', 'thead', 'tbody', 'tr', 'th', 'td',
  'img', 'hr',
  'details', 'summary',
  'span', 'div'
]

/**
 * 默认允许的HTML属性
 */
const DEFAULT_ALLOWED_ATTR = [
  'href', 'target', 'rel',
  'src', 'alt', 'title', 'width', 'height',
  'class', 'id',
  'open' // for <details>
]

/**
 * 消毒HTML内容，防止XSS攻击
 * 
 * @param {string} html - 原始HTML内容
 * @param {Object} options - 可选配置
 * @param {string[]} options.allowedTags - 允许的HTML标签列表
 * @param {string[]} options.allowedAttrs - 允许的HTML属性列表
 * @param {boolean} options.keepScripts - 是否保留脚本标签（默认false，强烈不建议开启）
 * @returns {string} 消毒后的安全HTML
 * 
 * @example
 * // 基础使用
 * <div v-html="sanitizeHtml(content)"></div>
 * 
 * @example
 * // 自定义配置
 * <div v-html="sanitizeHtml(content, { allowedTags: ['p', 'br'] })"></div>
 */
export function sanitizeHtml(html, options = {}) {
  if (!html) return ''
  
  const {
    allowedTags = DEFAULT_ALLOWED_TAGS,
    allowedAttrs = DEFAULT_ALLOWED_ATTR,
    keepScripts = false
  } = options
  
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: allowedTags,
    ALLOWED_ATTR: allowedAttrs,
    KEEP_CONTENT: true, // 保留被消毒标签的内容
    RETURN_DOM: false, // 返回字符串而非DOM节点
    WHOLE_DOCUMENT: false // 不是完整文档
  })
}

/**
 * 消毒Markdown渲染后的HTML（专门用于marked.js输出）
 * 
 * @param {string} markdownHtml - marked.js渲染后的HTML
 * @returns {string} 消毒后的安全HTML
 */
export function sanitizeMarkdown(markdownHtml) {
  return sanitizeHtml(markdownHtml, {
    allowedTags: [...DEFAULT_ALLOWED_TAGS, 'code', 'pre'],
    allowedAttrs: [...DEFAULT_ALLOWED_ATTR, 'class']
  })
}

/**
 * 消毒差异对比HTML（用于diff高亮显示）
 * 
 * @param {string} diffHtml - 差异HTML内容
 * @returns {string} 消毒后的安全HTML
 */
export function sanitizeDiffHtml(diffHtml) {
  return sanitizeHtml(diffHtml, {
    allowedTags: [...DEFAULT_ALLOWED_TAGS, 'span'],
    allowedAttrs: [...DEFAULT_ALLOWED_ATTR, 'class', 'data-*']
  })
}
