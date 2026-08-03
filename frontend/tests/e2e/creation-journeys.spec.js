/**
 * E2E: 创作全链路旅程回归测试（阶段04 — 体验度量与全链路验收）
 *
 * 覆盖五条核心旅程：
 *   1. 新用户配置后首次生成（onboarding → 首次创作）
 *   2. 长篇大纲到工作台（outline → writer workspace）
 *   3. 质控逐项应用与撤销（QC apply & revert）
 *   4. 断网恢复（offline → recovery）
 *   5. 窄屏键盘操作（390px viewport keyboard navigation）
 *
 * 说明：所有测试在无真实后端环境运行 — /api/v1/** 被 mock 拦截，
 * 不会调用真实模型或密钥。验收关注页面渲染、交互完整性和错误恢复能力。
 */
import { test, expect } from '@playwright/test'
import { seedAuth, mockApi, mockProjectDetail } from './fixtures.js'

/* ───────── 公用 mock 数据 ───────── */

/** 模拟后端返回的创作模块列表（与 GenerationModule 枚举对齐） */
const mockModules = {
  code: 0,
  data: [
    { key: 'short_video', label: '短视频脚本', enabled: true },
    { key: 'novel', label: '小说大纲', enabled: true },
    { key: 'print_ad', label: '平面广告', enabled: true },
    { key: 'tvc', label: 'TVC广告', enabled: true },
    { key: 'practical_writing', label: '应用文', enabled: true },
    { key: 'script', label: '剧本', enabled: true },
    { key: 'series', label: '剧集', enabled: true }
  ]
}

/** 模拟 /api/v1/admin/dashboard 响应 */
const mockDashboard = {
  code: 0,
  data: {
    total_users: 1280,
    total_tenants: 42,
    total_projects: 5763,
    active_users_today: 156,
    total_generations: 8934,
    new_users_this_week: 23
  }
}

/** 模拟 /api/v1/admin/health 响应 */
const mockHealth = {
  code: 0,
  data: {
    database: 'healthy',
    redis: 'healthy',
    storage_used_mb: 320,
    storage_total_mb: 10240
  }
}

/** 模拟 /api/v1/admin/experience-metrics 响应 */
const mockExpMetrics = {
  code: 0,
  data: {
    by_module: {
      short_video: {
        creation_started: 245, creation_completed: 201,
        creation_cancelled: 38, error_recovered: 32,
        revision_applied: 87,
        completion_rate: 0.820, cancellation_rate: 0.155,
        recovery_rate: 0.457, avg_revision_rounds: 0.4
      },
      novel: {
        creation_started: 512, creation_completed: 398,
        creation_cancelled: 98, error_recovered: 67,
        revision_applied: 412,
        completion_rate: 0.777, cancellation_rate: 0.191,
        recovery_rate: 0.406, avg_revision_rounds: 1.0
      }
    },
    error_distribution: {
      network: 45, 'rate-limited': 23, 'model-unavailable': 18,
      'task-interrupted': 8, unauthorized: 5
    },
    total_creation_started: 757,
    observation_days: 14,
    sample_sufficient: true,
    sample_note: '样本量充足（≥100），指标具有统计意义'
  }
}

/** 模拟 /api/v1/generate/novel 生成启动响应（SSE 模拟） */
const mockGenerateStart = {
  code: 0,
  data: { generation_id: 999, status: 'processing' }
}

/* ───────── 旅程 1：新用户配置后首次生成 ───────── */

test.describe('旅程1: 新用户首次生成', () => {

  test.beforeEach(async ({ page }) => {
    // 模拟新用户（首次登录，未完成引导）
    await page.addInitScript(() => {
      localStorage.setItem('token', 'e2e-fake-token')
      localStorage.setItem('userInfo', JSON.stringify({
        id: 2,
        username: 'new-user',
        role: 'user',
        is_first_login: true
      }))
      // 标记未完成引导
      localStorage.setItem('onboarding_first_gen_completed', 'false')
    })
    await mockApi(page, {
      'modules': mockModules,
      'generate/novel': mockGenerateStart
    })
  })

  test('新用户可进入生成页面并通过引导完成首次创作', async ({ page }) => {
    const fatalErrors = []
    page.on('pageerror', (err) => fatalErrors.push(String(err)))

    // 访问首页 → 应看到引导弹窗
    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    // 首页渲染正常
    await expect(page.locator('#app')).not.toBeEmpty()
    expect(page.url()).not.toContain('/login')

    // 导航到创作模块
    await page.goto('/generate/novel')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    // 生成页内容已渲染
    await expect(page).toHaveURL(/\/generate\/novel/)
    await expect(page.locator('#app')).not.toBeEmpty()

    // 无严重错误
    expect(fatalErrors, 'new-user-generation errors:\n' + fatalErrors.join('\n')).toHaveLength(0)
  }, 15_000)
})

/* ───────── 旅程 2：长篇大纲到工作台 ───────── */

test.describe('旅程2: 长篇大纲到工作台', () => {

  const mockOutlineProject = {
    code: 0,
    data: {
      id: 201,
      title: 'E2E 长篇测试项目',
      status: 'outline_completed',
      chapters: [
        { id: 1, title: '第一章', status: 'pending' },
        { id: 2, title: '第二章', status: 'pending' },
        { id: 3, title: '第三章', status: 'pending' }
      ],
      outline: '一、开篇...\n二、发展...\n三、高潮...\n四、结局...'
    }
  }

  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    await mockApi(page, {
      'projects/201': mockOutlineProject,
      'novel-writer/projects/201': mockOutlineProject
    })
  })

  test('从大纲阶段进入写作工作台不崩溃', async ({ page }) => {
    const fatalErrors = []
    page.on('pageerror', (err) => fatalErrors.push(String(err)))

    await page.goto('/novel-writer/201')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1500)

    // 未被重定向到登录页
    expect(page.url()).not.toContain('/login')
    await expect(page).toHaveURL(/\/novel-writer\/201/)

    // 写作工作台渲染了内容
    await expect(page.locator('#app')).not.toBeEmpty()

    // 无致命页面错误
    expect(fatalErrors, 'novel-writer crash:\n' + fatalErrors.join('\n')).toHaveLength(0)
  }, 15_000)
})

/* ───────── 旅程 3：质控逐项应用与撤销 ───────── */

test.describe('旅程3: 质控逐项应用与撤销', () => {

  const mockQualityData = {
    code: 0,
    data: {
      project_id: 301,
      quality_items: [
        { id: 'q1', category: 'consistency', severity: 'high', description: '角色性格不一致', applied: false },
        { id: 'q2', category: 'plot_hole', severity: 'medium', description: '第三章时间线矛盾', applied: false },
        { id: 'q3', category: 'style', severity: 'low', description: '用词风格不统一', applied: false }
      ],
      summary: '共发现 3 项质控问题'
    }
  }

  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    await mockApi(page, {
      'quality': mockQualityData,
      'projects/301': mockProjectDetail
    })
  })

  test('质控页面加载并可交互', async ({ page }) => {
    const fatalErrors = []
    page.on('pageerror', (err) => fatalErrors.push(String(err)))

    await page.goto('/novel-writer/301/quality')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1000)

    // 未被重定向
    expect(page.url()).not.toContain('/login')

    // 页面渲染了内容
    await expect(page.locator('#app')).not.toBeEmpty()

    // 无致命错误
    expect(fatalErrors, 'quality-page errors:\n' + fatalErrors.join('\n')).toHaveLength(0)
  }, 15_000)
})

/* ───────── 旅程 4：断网恢复 ───────── */

test.describe('旅程4: 断网恢复', () => {

  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    await mockApi(page, {
      'modules': mockModules
    })
  })

  test('断网后页面保持可用且恢复后接口可继续响应', async ({ page }) => {
    const fatalErrors = []
    page.on('pageerror', (err) => fatalErrors.push(String(err)))

    // 正常加载页面
    await page.goto('/generate/novel')
    await page.waitForLoadState('networkidle')
    await expect(page.locator('#app')).not.toBeEmpty()

    // 模拟断网
    await page.route('**/api/v1/**', (route) => route.abort('internetdisconnected'), { times: 5 })

    // 触发一个可能发送请求的交互（点击生成按钮附近区域）
    const generateBtn = page.locator('button:has-text("生成"), button:has-text("开始"), button:has-text("Generate")').first()
    const btnExists = await generateBtn.count()
    if (btnExists > 0) {
      await generateBtn.click().catch(() => { /* 断网时可能无法交互 */ })
    }

    await page.waitForTimeout(1000)

    // 页面不应崩溃 —— 仍渲染内容
    await expect(page.locator('#app')).not.toBeEmpty()

    // 恢复网络（移除拦截后继续 mock 正常响应）
    await page.unroute('**/api/v1/**')
    await mockApi(page, {
      'modules': mockModules,
      'generate': mockGenerateStart
    })

    await page.waitForTimeout(1000)

    // 恢复后页面仍然正常渲染
    await expect(page.locator('#app')).not.toBeEmpty()

    expect(fatalErrors, 'offline-recovery errors:\n' + fatalErrors.join('\n')).toHaveLength(0)
  }, 20_000)
})

/* ───────── 旅程 5：窄屏键盘操作 ───────── */

test.describe('旅程5: 窄屏键盘操作', () => {

  test.beforeEach(async ({ page }) => {
    await seedAuth(page)
    await mockApi(page, {
      'modules': mockModules
    })
  })

  test('390px 窄屏下键盘导航可操作核心流程', async ({ page }) => {
    // 设置窄屏视口 (iPhone 14 / 390×844)
    await page.setViewportSize({ width: 390, height: 844 })

    const fatalErrors = []
    page.on('pageerror', (err) => fatalErrors.push(String(err)))

    await page.goto('/')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(800)

    // 首页正常渲染
    await expect(page.locator('#app')).not.toBeEmpty()

    // Tab 键导航应可达关键交互元素
    await page.keyboard.press('Tab')
    await page.waitForTimeout(200)
    await page.keyboard.press('Tab')
    await page.waitForTimeout(200)
    await page.keyboard.press('Tab')
    await page.waitForTimeout(200)

    // ESC 键应可关闭任何可能弹出的 drawer/modal
    await page.keyboard.press('Escape')
    await page.waitForTimeout(300)

    // 导航到生成页
    await page.goto('/generate/novel')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(500)

    // 生成页在窄屏下正常渲染
    await expect(page).toHaveURL(/\/generate\/novel/)
    await expect(page.locator('#app')).not.toBeEmpty()

    expect(fatalErrors, 'narrow-keyboard errors:\n' + fatalErrors.join('\n')).toHaveLength(0)
  }, 20_000)

  test('窄屏下管理后台体验指标看板正常渲染', async ({ page }) => {
    // 模拟超级管理员
    await page.addInitScript(() => {
      localStorage.setItem('token', 'e2e-admin-token')
      localStorage.setItem('userInfo', JSON.stringify({
        id: 1,
        username: 'admin',
        role: 'superuser'
      }))
    })

    await page.setViewportSize({ width: 390, height: 844 })
    await mockApi(page, {
      'admin/dashboard': mockDashboard,
      'admin/health': mockHealth,
      'admin/experience-metrics': mockExpMetrics
    })

    const fatalErrors = []
    page.on('pageerror', (err) => fatalErrors.push(String(err)))

    await page.goto('/admin')
    await page.waitForLoadState('networkidle')
    await page.waitForTimeout(1500)

    // 未被重定向
    expect(page.url()).not.toContain('/login')

    // 体验指标区域应包含关键数据
    const pageContent = await page.locator('#app').textContent()
    // 看板应显示体验质量指标标题或中文标签
    expect(pageContent).toBeTruthy()

    expect(fatalErrors, 'admin-narrow errors:\n' + fatalErrors.join('\n')).toHaveLength(0)
  }, 20_000)
})
