/**
 * 前端产物体积预算检查（阶段04 首屏性能优化）
 *
 * 读取 backend/app/static/assets 下的构建产物，检查关键 chunk 是否超出预算。
 * 超限时输出实际字节与上限，并以非零退出码结束（阻断 verify 流程）。
 *
 * 用法：node scripts/check_frontend_budget.mjs
 * （package.json 中通过 "check:budget": "node ../scripts/check_frontend_budget.mjs" 调用）
 */
import fs from 'fs'
import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const assetsDir = path.resolve(__dirname, '../backend/app/static/assets')

const budgets = [
  { pattern: /^index-.*\.js$/, maxBytes: 120 * 1024 },
  { pattern: /^index-.*\.css$/, maxBytes: 380 * 1024 },
  { pattern: /^element-plus-.*\.js$/, maxBytes: 900 * 1024 }
]

if (!fs.existsSync(assetsDir)) {
  console.error(`[budget] 产物目录不存在: ${assetsDir}，请先执行 npm run build`)
  process.exitCode = 1
} else {
  const assetFiles = fs.readdirSync(assetsDir)
  let violationCount = 0

  for (const budget of budgets) {
    const matchedFiles = assetFiles.filter((name) => budget.pattern.test(name))
    if (matchedFiles.length === 0) {
      console.log(`[budget] 未匹配到 ${budget.pattern}（可能已拆分或未生成），跳过`)
      continue
    }
    for (const fileName of matchedFiles) {
      const actualBytes = fs.statSync(path.join(assetsDir, fileName)).size
      const withinBudget = actualBytes <= budget.maxBytes
      const statusLabel = withinBudget ? 'OK ' : '超限'
      console.log(
        `[budget] ${statusLabel} ${fileName}: ${actualBytes} bytes（上限 ${budget.maxBytes} bytes）`
      )
      if (!withinBudget) violationCount += 1
    }
  }

  if (violationCount > 0) {
    console.error(`[budget] 共 ${violationCount} 个产物超出预算，请优化分包或按需导入，不得直接放宽上限`)
    process.exitCode = 1
  } else {
    console.log('[budget] 全部产物在预算之内')
  }
}
