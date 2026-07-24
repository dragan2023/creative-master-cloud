#!/usr/bin/env node
/**
 * 前端性能预算检查脚本
 *
 * 读取 Vite 生产构建产物，测量 gzip 大小，与预算阈值比较。
 * 超限返回非零退出码，用于 preflight-release.ps1 门禁。
 *
 * 使用方式：
 *   node scripts/check-frontend-budget.mjs
 *   node scripts/check-frontend-budget.mjs --baseline  (仅输出当前值，不校验)
 *
 * 预算阈值定义规则：
 *   - 初始值 = 当前测量值 × 110%，不得凭经验设置不可能达到的阈值
 *   - 每次优化后根据实际测量值更新（收紧，不放宽）
 */

import { readFileSync, readdirSync, existsSync } from 'fs';
import { join, resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { gzipSync } from 'zlib';

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = resolve(__dirname, '..');
const ASSETS_DIR = join(PROJECT_ROOT, 'backend', 'app', 'static', 'assets');
const INDEX_HTML = join(PROJECT_ROOT, 'backend', 'app', 'static', 'index.html');

// ─── 预算阈值（gzip 后大小，单位 kB）────────────────────────────
// 基线测量日期：2026-07-23  |  构建工具：Vite 5.4.21
const BUDGET = {
  // 全局上限
  maxSingleChunkGzipKB: 425,     // 单 chunk 不得超过 425 kB gzip（antv 384→422 预留）

  // 命名 chunk 上限
  'element-plus':  { gzipKB: 389 },   // JS: 当前 354 kB → 110%
  'antv':           { gzipKB: 422 },   // 当前 384 kB → 110%

  // 入口与布局
  mainEntry:        { gzipKB: 52 },    // index-*.js 当前 47 kB → 110%
  mainCSS:          { gzipKB: 3 },     // index-*.css 当前 2.3 kB → 110%（el CSS 已分离）

  // 首屏关键路径（首页 /）
  firstScreenTotal: { gzipKB: 540 },   // index.html + mainEntry + mainCSS + Layout + Home + element-plus
                                        // 当前: 0.5+47+2.3+...+354 ≈ 490 kB → 110%

  // 页面 chunk 上限
  pageChunkMax:     { gzipKB: 50 },    // 单个页面 chunk 上限
};

// ─── 辅助函数 ─────────────────────────────────────────────────
function gzipSizeKB(filePath) {
  const content = readFileSync(filePath);
  return gzipSync(content).length / 1024;
}

function listAssets() {
  if (!existsSync(ASSETS_DIR)) {
    console.error(`Assets directory not found: ${ASSETS_DIR}`);
    console.error('Run "npm run build" in frontend/ first.');
    process.exit(1);
  }
  return readdirSync(ASSETS_DIR).filter(f => /\.(js|css)$/.test(f));
}

// ─── 主逻辑 ───────────────────────────────────────────────────
const isBaseline = process.argv.includes('--baseline');
const assets = listAssets();
const results = [];

let totalFirstScreenGzip = 0;

// 计算 index.html
if (existsSync(INDEX_HTML)) {
  const htmlGzip = gzipSizeKB(INDEX_HTML);
  totalFirstScreenGzip += htmlGzip;
  results.push({ name: 'index.html', gzipKB: htmlGzip, budget: null });
}

for (const asset of assets) {
  const filePath = join(ASSETS_DIR, asset);
  const gzipKB = gzipSizeKB(filePath);
  const rawKB = (readFileSync(filePath).length / 1024);

  // 匹配预算类别
  let budgetEntry = null;
  for (const [key, budget] of Object.entries(BUDGET)) {
    if (key === 'maxSingleChunkGzipKB' || key === 'firstScreenTotal' || key === 'mainEntry' || key === 'mainCSS' || key === 'pageChunkMax') continue;
    if (asset.startsWith(key)) {
      budgetEntry = { key, ...budget };
      break;
    }
  }

  // 识别首屏资源
  const isFirstScreen =
    asset.startsWith('index-') ||
    asset.startsWith('MainLayout-') ||
    asset.startsWith('Index-') ||
    asset.startsWith('element-plus-');

  if (isFirstScreen) {
    totalFirstScreenGzip += gzipKB;
  }

  results.push({
    name: asset,
    rawKB,
    gzipKB,
    budget: budgetEntry ? budgetEntry.gzipKB : null,
    isFirstScreen,
  });
}

// 排序：gzip 降序
results.sort((a, b) => b.gzipKB - a.gzipKB);

// ─── 输出 ─────────────────────────────────────────────────────
console.log('\n📊 Frontend Build Size Budget Report');
console.log('═'.repeat(62));
console.log('Asset                          │  Raw(kB) │ Gzip(kB) │ Budget │ Status');
console.log('─'.repeat(62));

let violations = 0;

for (const r of results) {
  const name = r.name.padEnd(30).slice(0, 30);
  const raw = String(r.rawKB?.toFixed(1) ?? '—').padStart(8);
  const gzip = r.gzipKB.toFixed(1).padStart(8);
  const budget = r.budget ? String(r.budget).padStart(7) : '      —';
  let status = '  OK';

  // 单 chunk 上限
  if (r.gzipKB > BUDGET.maxSingleChunkGzipKB) {
    status = ' FAIL';
    violations++;
  }
  // 命名 chunk 预算
  if (r.budget && r.gzipKB > r.budget) {
    status = ' FAIL';
    violations++;
  }

  console.log(`${name} │ ${raw} │ ${gzip} │ ${budget} │ ${status}`);
}

// 首屏总计
const fsBudget = BUDGET.firstScreenTotal.gzipKB;
const fsStatus = totalFirstScreenGzip > fsBudget ? ' FAIL' : '  OK';
if (totalFirstScreenGzip > fsBudget) violations++;
console.log('─'.repeat(62));
console.log(`${'First-screen total (gzip)'.padEnd(30)} │ ${'—'.padStart(8)} │ ${totalFirstScreenGzip.toFixed(1).padStart(8)} │ ${String(fsBudget).padStart(7)} │ ${fsStatus}`);

// ─── 汇总 ─────────────────────────────────────────────────────
console.log('═'.repeat(62));
if (isBaseline) {
  console.log('📋 Baseline mode — thresholds not enforced.');
  console.log('   Update BUDGET in check-frontend-budget.mjs to 110% of current values.');
  process.exit(0);
}

if (violations === 0) {
  console.log('✅ All budget checks passed.');
  process.exit(0);
} else {
  console.error(`❌ ${violations} budget violation(s) detected.`);
  console.error('   To resolve: optimize bundle size, or update budget with justification.');
  process.exit(1);
}
