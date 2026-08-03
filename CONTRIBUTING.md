# 贡献指南

感谢你对「全能创意大师」的关注与支持！无论是提交 Issue、修复 Bug、完善文档，还是实现新功能，都欢迎参与。

## 开发环境

- Python 3.10+（推荐 3.11 / 3.12）
- Node.js 18+（推荐 20 LTS）
- npm（随 Node.js 安装）

### Windows 一键启动

```powershell
.\run-local.ps1 install   # 安装全部依赖
.\run-local.ps1 start     # 启动前后端（热更新）
```

### 手动安装

```bash
# 后端
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt -c constraints.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload

# 前端（另开终端）
cd frontend
npm install
npm run dev
```

## 代码规范

### 后端

- Python 3.10+，遵循 [PEP 8](https://peps.python.org/pep-0008/)。
- FastAPI 异步风格：优先 `async def`，数据库操作使用 SQLAlchemy 异步会话。
- 数据校验统一使用 Pydantic Schema（`backend/app/schemas/`）。
- 业务逻辑放在 `services/`，不要在 API 端点中堆积实现。

### 前端

- Vue 3 Composition API（`<script setup>`）。
- 状态管理使用 Pinia（`frontend/src/stores/`）。
- 可复用逻辑优先抽取为 composables（`frontend/src/composables/`）。
- 组件、页面分别放在 `components/` 与 `views/`。

### 提交信息

遵循 [Conventional Commits](https://www.conventionalcommits.org/zh-hans/)：

```text
feat: 新增 xxx 功能
fix: 修复 xxx 问题
refactor: 重构 xxx
docs: 更新文档
test: 补充测试
chore: 构建/工具链调整
```

## 分支与提交流程

1. Fork 本仓库并创建特性分支：`feat/xxx` 或 `fix/xxx`。
2. 提交前运行测试并确保通过：

   ```powershell
   # 后端
   scripts\test-backend.ps1

   # 前端
   cd frontend
   npm run test:unit
   npm run build
   ```

3. 提交并推送到你的 Fork，然后向 `main` 分支发起 Pull Request。
4. PR 中请填写模板内容，说明变更动机、范围与测试情况；CI 通过后等待评审。

## 安全约定

- **严禁**将任何密钥、口令、令牌、`.env` 文件提交到仓库（已通过 `.gitignore` 排除）。
- 涉及认证、密钥管理、权限控制等安全相关变更，请在 PR 描述中显式说明。
- 发现安全漏洞请勿提交公开 Issue，按 [SECURITY.md](SECURITY.md) 私密报告。

## 行为准则

请阅读并遵守 [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)。
