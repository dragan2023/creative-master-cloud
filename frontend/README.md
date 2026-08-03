# 全能创意大师 - 前端

基于 **Vue 3 + Vite + Element Plus** 的创作平台前端，配套后端见项目根目录 [README](../README.md)。

## 技术栈

- Vue 3（Composition API）+ Vite 5
- Element Plus + @element-plus/icons-vue
- Pinia 状态管理 + Vue Router
- ECharts（质控仪表盘）+ AntV G6（知识图谱）
- marked + DOMPurify（Markdown 安全渲染）
- Vitest（单元测试）+ Playwright（E2E 测试）

## 常用命令

```bash
npm install              # 安装依赖
npm run dev              # 开发服务器（默认 http://localhost:3001）
npm run build            # 生产构建（输出到 backend/app/static）
npm run preview          # 预览构建产物
npm run test:unit        # Vitest 单元测试
npm run test:e2e         # Playwright 端到端测试
npm run check:quality    # 单元测试 + 生产构建
```

## 环境变量

复制 `.env.example` 为 `.env.local` 并按需修改：

| 变量 | 说明 |
|:---|:---|
| `VITE_API_BASE_URL` | API 基础地址（生产环境必填；开发环境留空走 Vite 代理） |
| `VITE_BACKEND_URL` | 后端地址（仅开发代理使用，默认 `http://localhost:8002`） |
| `VITE_FRONTEND_PORT` | 前端端口（默认 `3001`） |

## 目录结构

```text
src/
├── api/          # API 调用封装
├── components/   # 通用组件
├── composables/  # 组合式函数
├── config/       # 模块与功能配置
├── domain/       # 领域模型
├── layouts/      # 布局
├── router/       # 路由
├── stores/       # Pinia 状态
├── styles/       # 全局样式
├── utils/        # 工具函数
└── views/        # 页面
```

## 测试

```bash
npm run test:unit    # 单元测试
npm run test:e2e     # 端到端测试
```
