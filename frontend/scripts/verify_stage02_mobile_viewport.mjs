/**
 * 阶段02验收：/novel-writer 390px 视口布局与键盘焦点顺序
 *
 * 验证项：
 * 1. 390x844 下页面无横向溢出（scrollWidth <= innerWidth）
 * 2. 筛选区四组控件（搜索/类型/状态/排序）均在视口内，纵向排列
 * 3. Tab 焦点顺序覆盖：搜索输入 → 类型 → 状态 → 排序字段 → 升降序按钮（相对顺序与视觉一致）
 * 4. 排序按钮具有 aria-pressed 状态
 *
 * 用法（需前端 dev 服务器已运行）：
 *   node scripts/verify_stage02_mobile_viewport.mjs
 * 环境变量：
 *   QA_TOKEN     登录 token（必填）
 *   QA_USERINFO  userInfo JSON（必填）
 *   QA_BASE_URL  默认 http://localhost:3001
 */
import { chromium } from 'playwright'

const BASE_URL = process.env.QA_BASE_URL || 'http://localhost:3001'
const TOKEN = process.env.QA_TOKEN
const USERINFO = process.env.QA_USERINFO

if (!TOKEN || !USERINFO) {
  console.error('[FAIL] 缺少 QA_TOKEN / QA_USERINFO 环境变量')
  process.exit(2)
}

const VIEWPORT = { width: 390, height: 844 }
const SCREENSHOT_PATH =
  'e:/python_project/全能创意大师（开发版）/docs/全能创意大师验收缺口与可信回归专项修复计划/验收证据/02_项目列表390视口_20260718.png'

/** 断言辅助：失败即累计错误 */
const failures = []
function check(name, condition, detail = '') {
  if (condition) {
    console.log(`[PASS] ${name}${detail ? ' | ' + detail : ''}`)
  } else {
    failures.push(name)
    console.error(`[FAIL] ${name}${detail ? ' | ' + detail : ''}`)
  }
}

const browser = await chromium.launch()
const context = await browser.newContext({ viewport: VIEWPORT })
const page = await context.newPage()

// 注入登录态后进入项目列表页
await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' })
await page.evaluate(([token, userInfo]) => {
  localStorage.setItem('token', token)
  localStorage.setItem('userInfo', userInfo)
}, [TOKEN, USERINFO])
await page.goto(`${BASE_URL}/novel-writer`, { waitUntil: 'networkidle' })
await page.waitForSelector('.filter-bar', { timeout: 15000 })

// 1. 无横向溢出
const overflow = await page.evaluate(() => ({
  scrollWidth: document.documentElement.scrollWidth,
  innerWidth: window.innerWidth,
  bodyScrollWidth: document.body.scrollWidth
}))
check(
  '390px 页面无横向溢出',
  overflow.scrollWidth <= overflow.innerWidth && overflow.bodyScrollWidth <= overflow.innerWidth,
  JSON.stringify(overflow)
)

// 2. 筛选控件均在视口内且纵向排列
const layout = await page.evaluate(() => {
  const items = [...document.querySelectorAll('.filter-bar .filter-item')]
  return items.map(item => {
    const rect = item.getBoundingClientRect()
    return { left: rect.left, right: rect.right, top: rect.top, width: rect.width }
  })
})
check('筛选区包含 4 组控件', layout.length === 4, `实际 ${layout.length} 组`)
check(
  '筛选控件右缘均不超出 390px',
  layout.every(rect => rect.right <= 390.5),
  JSON.stringify(layout.map(r => Math.round(r.right)))
)
const verticallyStacked = layout.every(
  (rect, index) => index === 0 || rect.top >= layout[index - 1].top
)
check('筛选控件纵向排列（top 递增）', verticallyStacked)

// 3. Tab 焦点顺序：筛选区内部相对顺序 = 搜索 → 类型 → 状态 → 排序字段 → 升降序按钮
await page.evaluate(() => document.body.focus())
const focusSequence = []
for (let i = 0; i < 30; i++) {
  await page.keyboard.press('Tab')
  const descriptor = await page.evaluate(() => {
    const el = document.activeElement
    if (!el) return null
    return {
      id: el.id || null,
      className: typeof el.className === 'string' ? el.className : '',
      aria: el.getAttribute('aria-label') || null,
      text: (el.textContent || '').trim().slice(0, 12)
    }
  })
  focusSequence.push(descriptor)
}

function focusIndex(predicate) {
  return focusSequence.findIndex(d => d && predicate(d))
}
const searchIdx = focusIndex(d => d.id === 'project-search-input')
const typeIdx = focusIndex(d => d.id === 'project-type-select' || d.aria === '按内容类型筛选')
const statusIdx = focusIndex(d => d.id === 'project-status-select' || d.aria === '按项目状态筛选')
const sortSelectIdx = focusIndex(d => d.id === 'project-sort-select' || d.aria === '排序字段')
const sortBtnIdx = focusIndex(d => (d.className || '').includes('sort-order-btn') || (d.aria || '').includes('点击切换'))

check('Tab 可达搜索输入框', searchIdx >= 0, `index=${searchIdx}`)
check('Tab 可达类型选择', typeIdx >= 0, `index=${typeIdx}`)
check('Tab 可达状态选择', statusIdx >= 0, `index=${statusIdx}`)
check('Tab 可达排序字段选择', sortSelectIdx >= 0, `index=${sortSelectIdx}`)
check('Tab 可达升降序按钮', sortBtnIdx >= 0, `index=${sortBtnIdx}`)
check(
  '筛选区焦点顺序与视觉顺序一致',
  searchIdx < typeIdx && typeIdx < statusIdx && statusIdx < sortSelectIdx && sortSelectIdx < sortBtnIdx,
  JSON.stringify({ searchIdx, typeIdx, statusIdx, sortSelectIdx, sortBtnIdx })
)

// 4. 排序按钮可访问状态
const ariaPressed = await page.getAttribute('.sort-order-btn', 'aria-pressed')
check('排序按钮携带 aria-pressed 状态', ariaPressed === 'true' || ariaPressed === 'false', `aria-pressed=${ariaPressed}`)

await page.screenshot({ path: SCREENSHOT_PATH, fullPage: true })
console.log(`[INFO] 截图已保存: ${SCREENSHOT_PATH}`)

await browser.close()

if (failures.length > 0) {
  console.error(`[RESULT] 失败 ${failures.length} 项: ${failures.join('; ')}`)
  process.exit(1)
}
console.log('[RESULT] 390px 视口验收全部通过')
