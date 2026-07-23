/**
 * E2E 公共夹具：认证种子 + API mock
 *
 * 所有 /api 请求在浏览器层被拦截并返回可预测的 mock 响应，
 * 保证测试不依赖真实后端、真实模型或任何密钥。
 */

/** 在应用启动前注入 token 与 userInfo，绕过登录守卫 */
export async function seedAuth(page) {
  await page.addInitScript(() => {
    localStorage.setItem('token', 'e2e-fake-token')
    localStorage.setItem('userInfo', JSON.stringify({
      id: 1,
      username: 'e2e-user',
      role: 'user'
    }))
  })
}

/**
 * 拦截后端 API 请求，按路径返回 mock 数据。
 * 仅拦截真实后端前缀 /api/v1/（避免误伤 Vite dev 下 /src/api/*.js 模块脚本）。
 * 未显式匹配的接口统一返回 { code: 0, data: null } 以避免页面报错。
 */
export async function mockApi(page, overrides = {}) {
  await page.route('**/api/v1/**', async (route) => {
    const url = route.request().url()

    for (const [pattern, handler] of Object.entries(overrides)) {
      if (url.includes(pattern)) {
        const body = typeof handler === 'function' ? handler(route) : handler
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(body)
        })
        return
      }
    }

    // 默认空响应
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ code: 0, message: 'ok', data: null })
    })
  })
}

/** 常用的项目列表/详情 mock 数据 */
export const mockProjectDetail = {
  code: 0,
  message: 'ok',
  data: {
    id: 123,
    title: 'E2E 测试项目',
    status: 'draft',
    chapters: [],
    outline: ''
  }
}
