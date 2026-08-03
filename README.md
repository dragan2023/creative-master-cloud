# 🎨 全能创意大师（Creative Master）

> 基于**多智能体（Multi-Agent）与多模态 AI** 的一站式创意生成与写作平台，覆盖小说、剧集、电影剧本、短视频、广告、应用文与原创 IP 等全品类创作场景。

[![Version](https://img.shields.io/badge/version-5.1-blue)](https://github.com/dragan2023/creative-master-cloud)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Node](https://img.shields.io/badge/Node.js-18%2B-339933?logo=node.js&logoColor=white)](https://nodejs.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Vue 3](https://img.shields.io/badge/Vue%203-4FC08D?logo=vuedotjs&logoColor=white)](https://vuejs.org/)

---

## 📖 项目简介

全能创意大师是一个前后端分离的 AI 创作平台：

- **后端**：FastAPI + SQLAlchemy（异步）+ ChromaDB 向量库，提供 REST API、SSE 流式输出与 WebSocket 实时推送。
- **前端**：Vue 3 + Vite + Element Plus，提供完整的创作工作台、质控仪表盘与知识库可视化。
- **创作能力**：由写作工作台、多智能体流水线、六维质量控制和知识图谱共同驱动，支持「大纲 → 正文 → 质控 → 修订 → 导出」的完整创作闭环。
- **部署形态**：支持 Windows 本地一键启动（非容器化）、Docker Compose 生产部署与云端容器化部署。

---

## ✨ 核心功能

### 🧩 八大创意模块

| 模块 | 说明 |
|:---|:---|
| 小说 | 章回体小说，支持全局大纲 + 原子化单元概述 + 逐章正文生成 |
| 剧集 | 单元剧 / 连续剧大纲与剧本 |
| 电影剧本 | 完整电影剧本大纲与分场内容 |
| 短视频脚本 | 面向抖音、快手等平台，支持参考资料与热门元素 |
| TVC 广告脚本 | 电视广告、商业视频脚本 |
| 平面广告 | Logo、海报、宣传单、包装等创意文案 |
| 应用文写作 | 演讲稿、新闻稿、会议纪要、商业计划书等 21 种专业文档 |
| 原创 IP 计划 | 一键构建完整角色 IP 档案 |

### 🖊️ 多智能体写作工作台

- **智能体流水线**：撰写（Writer）、风格编辑（Style Editor）、逻辑编辑（Logic Editor）、合规审核（Compliance）、知识助手（Knowledge）等多个智能体协作完成创作。
- **六维正文质控**：人物一致性、叙事逻辑、风格统一、时间线、空间逻辑、OOC 防偏；支持实时质控、批量质控与可视化质控仪表盘。
- **双版本内容管理**：修订前后版本对比、Diff 高亮、选择性应用修正。
- **角色状态追踪**：28-Mixin 人物状态追踪器，贯穿全文的一致性状态管理。
- **知识图谱增强**：GraphRAG 实体关系网络，写作过程中自动检索上下文。
- **项目知识库**：章节/场景大纲、风格文档、世界观设定统一沉淀与检索。
- **导出**：支持 TXT / Markdown / DOCX 格式导出。

### 💬 多模型 AI 支持

- 支持 **DeepSeek**（含 Reasoning 思考模式）、**通义千问**、**豆包**、**OpenAI**、**Google Gemini** 等主流模型及 OpenAI 兼容接口。
- SSE 流式输出 + Markdown 实时渲染，生成过程全程可见。
- 模型配置支持界面化管理（每任务、每写作单元可独立配置模型）。

### 🎬 多模态 AI 资源

- **Seedance 2.0 视频提示词**：人物 / 场景 / 道具 / 氛围 / 运镜五维智能合并。
- **Suno AI 配乐提示词**：从剧本配乐参考板块动态生成。
- **视觉内容同步**：正文修改自动触发 AI 视觉资源更新建议。

### 📚 知识库管理

- 文档上传与智能解析：PDF、Word、TXT、Markdown、Excel。
- 基于 ChromaDB 的向量检索与语义分块。
- 知识图谱可视化（AntV G6），实体关系网络构建与查询。
- 联网搜索（支持自定义搜索 API Key）。

### 🛡️ 平台能力

- 用户认证（JWT）与多租户隔离。
- API Key 管理、后台管理（用户 / 日志 / 租户 / 系统配置）。
- 操作审计、系统监控（CPU / 内存 / 磁盘）、健康检查。
- 写作任务中心：任务断点恢复、实时进度推送（WebSocket）、成本透明展示。
- 自动更新检查与版本管理。
- MCP 端点，支持外部 AI 工具接入。

---

## 🧰 技术栈

### 后端

| 技术 | 用途 |
|:---|:---|
| FastAPI + Uvicorn | 异步 Web 框架 |
| SQLAlchemy 2.0（异步）+ Alembic | ORM 与数据库迁移 |
| SQLite / PostgreSQL | 数据库（开发 / 生产） |
| ChromaDB + sentence-transformers | 向量存储与语义检索 |
| Redis | 可选缓存 / 消息 |
| LangChain + OpenAI SDK | LLM 调用链路 |
| SSE / WebSocket | 流式输出与实时推送 |
| python-jose / PyJWT + passlib | 认证与安全 |

### 前端

| 技术 | 用途 |
|:---|:---|
| Vue 3（Composition API）+ Vite | 前端框架与构建工具 |
| Element Plus | UI 组件库 |
| Pinia | 状态管理 |
| Vue Router | 路由 |
| ECharts | 质控仪表盘数据可视化 |
| AntV G6 | 知识图谱可视化 |
| marked + DOMPurify | Markdown 安全渲染 |
| Vitest + Playwright | 单元测试与 E2E 测试 |

---

## 🚀 快速开始

### 环境要求

| 组件 | 最低版本 | 推荐版本 |
|:---|:---|:---|
| Python | 3.10 | 3.11 / 3.12 |
| Node.js | 18 | 20 LTS |
| npm | 随 Node.js 安装 | 最新稳定版 |

### 一键启动（Windows）

双击运行 `run-local.bat`，或在 PowerShell 中执行：

```powershell
.\run-local.ps1
```

脚本会自动完成：

1. 检测 Python / Node.js 环境。
2. 创建后端虚拟环境并安装 Python 依赖（清华 PyPI 镜像加速）。
3. 安装前端 npm 依赖（npmmirror 镜像加速）。
4. 启动后端服务与前端开发服务器（热更新）。

常用命令：

```powershell
.\run-local.ps1 install   # 仅安装依赖
.\run-local.ps1 start     # 启动开发环境（默认）
.\run-local.ps1 stop      # 停止服务
.\run-local.ps1 status    # 查看服务状态
.\run-local.ps1 help      # 查看帮助
```

### 手动安装

#### 1. 后端

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt -c constraints.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8002 --reload
```

#### 2. 前端

```bash
cd frontend
npm install
npm run dev
```

### 访问地址

| 服务 | 地址 |
|:---|:---|
| 前端界面 | http://localhost:3001 |
| 后端 API | http://localhost:8002（`run-local.ps1` 启动为 7000） |
| Swagger API 文档 | http://localhost:8002/docs |
| ReDoc API 文档 | http://localhost:8002/redoc |

> 说明：本地开发时前端通过 Vite 代理 `/api` 请求后端，无需额外配置跨域；如需异地访问，请配置 `VITE_API_BASE_URL` 指向后端完整地址。

---

## ⚙️ 配置说明

### API Key 配置

可在应用内「API Key 管理」页面配置各模型密钥，也可通过环境变量提供：

| 环境变量 | 模型 | 获取地址 |
|:---|:---|:---|
| `DEEPSEEK_API_KEY` | DeepSeek | https://platform.deepseek.com |
| `DASHSCOPE_API_KEY` | 通义千问 | https://bailian.console.aliyun.com |
| `ARK_API_KEY` | 豆包 | https://console.volcengine.com/ark |
| `OPENAI_API_KEY` | OpenAI | https://platform.openai.com |
| `GOOGLE_API_KEY` | Google Gemini | https://aistudio.google.com |

### 环境变量

复制根目录模板创建本地配置（模板中均为占位值）：

```powershell
copy .env.example .env
```

常用变量：

| 变量 | 说明 | 默认值 |
|:---|:---|:---|
| `DATABASE_URL` | 数据库连接串 | SQLite（开发）/ PostgreSQL（生产） |
| `SECRET_KEY` | JWT 密钥，生产环境必须修改 | 占位值 |
| `REDIS_URL` | Redis 地址（可选） | `redis://localhost:6379/0` |
| `CHROMA_PERSIST_DIR` | 向量库持久化目录 | `./data/chroma` |
| `CORS_ORIGINS` | 允许的跨域来源，`*` 表示全部 | `*` |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` / `ADMIN_EMAIL` | 首次启动自动创建超级管理员 | 注释状态 |

### 云部署配置

```powershell
copy .env.cloud.example .env.cloud
```

`env.cloud` 面向容器化生产环境（PostgreSQL、Redis、HuggingFace / PyPI / npm 镜像等），填写后即可用于云端部署。

### 🔒 安全约定

- `.env`、`.env.cloud` 等真实密钥文件已被 `.gitignore` 排除，**严禁**将任何真实密钥、口令、令牌提交到仓库。
- 仓库仅保留脱敏模板 `.env.example` 与 `.env.cloud.example`。
- `docs/` 下的开发文档（计划、报告、日志、验收证据等）不纳入版本控制。

---

## 🧪 测试

### 后端测试

```powershell
# 运行后端与根级测试（固定使用 backend\venv 解释器）
scripts\test-backend.ps1

# 追加额外 pytest 参数
scripts\test-backend.ps1 -- -k character_state
```

等价命令：

```powershell
backend\venv\Scripts\python.exe -m pytest backend/tests tests -q -p no:cacheprovider
```

### 前端测试

```bash
cd frontend
npm run test:unit       # Vitest 单元测试
npm run test:e2e        # Playwright 端到端测试
npm run check:quality   # 单元测试 + 生产构建
```

---

## 🐳 Docker 部署

### 生产环境

```bash
# 使用 docker-compose.prod.yml 启动（Nginx 对外端口 80）
docker compose -f docker-compose.prod.yml up -d --build
```

部署完成后访问 `http://localhost`，相关辅助脚本位于 `scripts/`（如 `deploy.sh`、`preflight-release.ps1`、`build-and-push.bat`）。

### 云端部署

```bash
docker compose -f docker-compose.cloud.yml up -d --build
```

云端版本包含 PostgreSQL、Redis、多租户支持与 SSL 配置脚本（`nginx/ssl-setup.sh`）。

> 注意：部署前必须通过 `.env.cloud` 配置真实的 `SECRET_KEY`、数据库口令与管理员口令。

---

## 📁 项目结构

```text
全能创意大师（开发版）
├── backend/                  # FastAPI 后端
│   ├── app/
│   │   ├── agents/           # AI 智能体（写作多智能体 / 编排器 / 提示词管理）
│   │   ├── api/v1/           # REST API（generate / novel_writer / writing_tasks / knowledge / admin ...）
│   │   ├── services/         # 业务服务层（写作引擎 / 质控 / 知识库 / AI 资源）
│   │   ├── models/           # SQLAlchemy 数据模型
│   │   ├── schemas/          # Pydantic 数据模型
│   │   ├── core/             # 配置 / 数据库 / 安全 / 日志 / 可观测性
│   │   └── tools/            # 工具模块（知识图谱 RAG / 样式库 / 网页检索）
│   ├── alembic/              # 数据库迁移
│   └── requirements.txt
├── frontend/                 # Vue 3 + Vite 前端
│   ├── src/
│   │   ├── api/              # API 调用封装
│   │   ├── components/       # 通用组件
│   │   ├── composables/      # 组合式函数
│   │   ├── stores/           # Pinia 状态管理
│   │   ├── views/            # 页面（generate / novel-writer / knowledge / admin ...）
│   │   └── router/           # 路由配置
│   └── package.json
├── scripts/                  # 运维 / 部署 / 测试 / 版本管理脚本
├── nginx/                    # Nginx 配置与 SSL 脚本
├── docs/                     # 本地开发文档（不纳入版本控制）
├── docker-compose.prod.yml   # 生产环境 Docker 编排
├── docker-compose.cloud.yml  # 云端部署编排
├── run-local.bat / .ps1      # Windows 本地一键启动脚本
├── .env.example              # 环境变量模板
├── CHANGELOG.md              # 更新日志
└── README.md
```

---

## 📚 相关文档

- [更新日志](CHANGELOG.md)
- [前端说明](frontend/README.md)
- Swagger API 文档：`/docs`（运行时访问）
- ReDoc API 文档：`/redoc`（运行时访问）

---

## 🤝 贡献

欢迎提交 Issue 与 Pull Request！请先阅读：

- [贡献指南](CONTRIBUTING.md)：开发环境、代码规范、提交信息与 PR 流程
- [行为准则](CODE_OF_CONDUCT.md)：社区行为规范
- [安全政策](SECURITY.md)：安全漏洞的私密报告方式

提交前请确保后端与前端测试通过，且不包含任何密钥与敏感信息。

---

## 📄 许可证

本项目基于 [MIT License](LICENSE) 开源，© 2026 全能创意大师开发团队。

---

## 🔗 仓库地址

https://github.com/dragan2023/creative-master-cloud
