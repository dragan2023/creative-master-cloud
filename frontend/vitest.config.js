import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import path from 'path'

// 单元测试配置（与 vite.config.js 分离，避免影响生产构建）
// 仅覆盖 tests/unit 下的单元测试；端到端测试由 playwright.config.js 管理
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src')
    }
  },
  define: {
    // vite.config.js 通过 define 注入版本号，测试环境提供占位值防止引用报错
    __APP_VERSION__: JSON.stringify('0.0.0-test')
  },
  test: {
    environment: 'jsdom',
    globals: true,
    include: ['tests/unit/**/*.spec.js'],
    exclude: ['tests/e2e/**', 'node_modules/**', 'dist/**'],
    clearMocks: true,
    restoreMocks: true
  }
})
