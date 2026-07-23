# 🎨 全能创意大师 v5.1

> 基于多模态 AI 的智能创意生成与写作平台，支持小说、剧本、短视频、广告等全品类创意内容的一站式创作。

[![Version](https://img.shields.io/badge/version-5.1-blue)](https://github.com/dragan2023/creative-master)
[![License](https://img.shields.io/badge/license-MIT-green)](LICENSE)

---

## ✨ 核心功能

### 🖊️ 写作工作台
- **全品类写作支持**：小说（章回体）、剧集（单元剧/连续剧）、电影剧本
- **智能大纲生成**：AI 驱动的全局大纲 + 原子化章节概述自动生成
- **逐章直接生成**：基于大纲直接生成正文，上下文自动衔接
- **六维度正文质控**：人物一致性、叙事逻辑、风格统一、时间线、空间逻辑、OOC 防偏
- **双版本内容管理**：支持修订前后版本对比、选择性应用修正
- **全维度一致性追踪**：28-Mixin 人物状态追踪器 + 知识图谱持久化

### 🎬 多模态 AI 资源生成
- **Seedance 2.0 视频提示词**：五维智能合并（人物/场景/道具/氛围/运镜）
- **Suno AI 配乐**：从剧本配乐参考板块动态生成提示词
- **视觉内容同步**：正文修改自动触发 AI 视觉资源更新建议

### 💬 多模型 AI 对话
- 支持 **DeepSeek** / **通义千问** / **豆包** / **OpenAI** / **Google Gemini** 等主流模型
- DeepSeek 思考模式（Reasoning）全链路支持
- SSE 流式输出 + Markdown 实时渲染

### 📚 知识库管理
- 文档上传与智能解析（PDF、Word、TXT、Markdown）
- 基于 ChromaDB 的向量检索
- 知识图谱可视化（G6 图引擎）
- 实体关系网络构建与查询

### 🛡️ 三维质控体系
- **实时质控**：写作过程中 WebSocket 推送质量报告
- **批量质控**：全章/全文质量扫描与自动修正
- **质控仪表盘**：可视化质量得分、问题分布、修正建议

---

## 🚀 快速开始

### 环境要求

| 组件 | 最低版本 |
|:---|:---|
| Python | 3.10+ |
| Node.js | 18+ |
| npm / yarn | 最新稳定版 |

### 一键启动（Windows）

```powershell
.\run-local.ps1
```

或双击运行 `run-local.bat`，脚本将自动：
1. 检测并配置 Python/Node.js 环境
2. 创建虚拟环境并安装依赖
3. 启动后端（端口 8000）和前端（端口 3001）

### 手动安装

#### 1. 后端

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
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
| API 文档（Swagger） | http://localhost:8000/docs |
| API 文档（ReDoc） | http://localhost:8000/redoc |

---

## 🧪 测试

后端测试统一通过入口脚本运行，脚本会固定调用后端虚拟环境解释器
（`backend\venv\Scripts\python.exe`），不会静默回退到系统 Python。
若虚拟环境缺失，脚本会提示先运行 `run-local.ps1` 并以非零退出码结束。

```powershell
# 运行后端与根级测试
scripts\test-backend.ps1

# 仅打印将执行的命令（排查/校验用，不实际运行）
scripts\test-backend.ps1 -PrintCommand

# 追加额外 pytest 参数
scripts\test-backend.ps1 -- -k character_state
```

等价的显式命令：

```powershell
backend\venv\Scripts\python.exe -m pytest backend/tests tests -q -p no:cacheprovider
```

---

## ⚙️ 配置说明

### API Key 配置

在应用内「API Key 管理」页面配置各模型密钥，或通过环境变量设置：

| 模型 | 获取地址 |
|:---|:---|
| DeepSeek | https://platform.deepseek.com |
| 通义千问 | https://bailian.console.aliyun.com |
| 豆包 | https://console.volcengine.com/ark |
| OpenAI | https://platform.openai.com |
| Google Gemini | https://aistudio.google.com |

### 环境变量

在项目根目录或 `backend/` 下创建 `.env` 文件（参考 `.env.example`）：

```env
APP_NAME=全能创意大师
DEBUG=True
DATABASE_URL=sqlite+aiosqlite:///./data/creative_master.db
SECRET_KEY=your-secret-key-here
```

> 云端部署：仓库仅提供脱敏模板 `.env.cloud.example`。请复制为 `.env.cloud`
> 并填写真实密钥（`.env.cloud` 已加入 `.gitignore`，不会被提交）：
>
> ```powershell
> copy .env.cloud.example .env.cloud
> ```

---

## 📁 项目结构

```
├── backend/                     # 后端 (FastAPI)
│   ├── app/
│   │   ├── agents/              # AI Agent 模块
│   │   │   ├── writing/         # 写作 Agent (写手/风格/逻辑编辑/合规)
│   │   │   ├── orchestrator/    # 编排 Agent
│   │   │   └── prompt_manager/  # 提示词模板管理
│   │   ├── api/v1/endpoints/    # REST API 端点
│   │   │   ├── generate/        # 创意生成
│   │   │   ├── novel_writer/    # 写作工作台 + 质控
│   │   │   ├── writing_tasks/   # 写作任务管理
│   │   │   └── knowledge/       # 知识库
│   │   ├── services/            # 业务服务层
│   │   │   ├── outline_generator/  # 大纲生成引擎
│   │   │   ├── writing_engine/     # 写作流水线
│   │   │   ├── quality_control/    # 质量管控
│   │   │   └── ai_resource/        # AI 资源生成
│   │   ├── models/              # ORM 数据模型
│   │   ├── schemas/             # Pydantic 数据模式
│   │   └── tools/               # 工具模块 (知识图谱/RAG/向量存储)
│   ├── alembic/                 # 数据库迁移
│   └── requirements.txt
├── frontend/                    # 前端 (Vue 3)
│   ├── src/
│   │   ├── api/                 # API 调用封装
│   │   ├── components/          # 通用组件
│   │   ├── views/               # 页面
│   │   │   ├── generate/        # 创意生成页
│   │   │   ├── novel-writer/    # 写作工作台
│   │   │   ├── knowledge/       # 知识库管理
│   │   │   └── api-keys/        # API Key 管理
│   │   ├── stores/              # Pinia 状态管理
│   │   └── router/              # 路由配置
│   └── package.json
├── scripts/                     # 运维脚本
├── docker-compose.prod.yml      # 生产环境 Docker 配置
├── docker-compose.cloud.yml     # 云端部署配置
├── run-local.bat                # Windows 本地启动
├── run-local.ps1                # PowerShell 本地启动
└── README.md
```

---

## 🛠️ 技术栈

### 后端

| 技术 | 用途 |
|:---|:---|
| **FastAPI** | 高性能异步 Web 框架 |
| **SQLAlchemy** | ORM + 异步数据库操作 |
| **ChromaDB** | 向量数据库（知识库检索） |
| **SSE / WebSocket** | 实时流式输出 + 双向消息推送 |
| **Alembic** | 数据库版本迁移 |

### 前端

| 技术 | 用途 |
|:---|:---|
| **Vue 3** (Composition API) | 渐进式前端框架 |
| **Element Plus** | UI 组件库 |
| **Pinia** | 状态管理 |
| **ECharts** | 数据可视化（质控仪表盘） |
| **AntV G6** | 知识图谱可视化 |
| **Vite** | 构建工具 |
| **marked + DOMPurify** | Markdown 安全渲染 |

---

## 📝 更新日志

### v5.1 (2026-07-17)

**功能新增**
- 📄 应用文写作模块上线：演讲稿、新闻稿、会议纪要、商业计划书等 21 种专业文档生成
- 📎 参考文档上传解析：支持上传文档作为写作参考，提示词嵌入优先级加权
- 📏 自定义文档长度：纯文本长度输入，生成篇幅精准可控
- 🎨 前端模块排版优化：应用文写作入口调整至原创IP计划与小说大纲之间

### v5.0 (2026-06-15)

**重大更新**
- 🏗️ 写作工作台架构重构：统一整章直接生成模式
- 📊 正文质控六维度升级（人物/叙事/风格/时间线/空间/OOC）
- 📋 双版本内容管理：修订前后对比、选择性应用
- 🔗 全维度一致性状态追踪（28-Mixin 状态机 + 知识图谱双轨持久化）
- 🎵 Seedance 2.0 五维视频提示词智能合并
- 🎼 Suno AI 动态配乐提示词生成
- 🧹 项目工程规范完善：临时文件清理、.gitignore 优化

### v4.2 (2026-05-06)
- 首次公开发布
- AI 智能对话 + 多模型支持
- 文档智能解析 + 知识库管理
- 基础创意生成功能

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

## 📄 许可证

MIT License © 2026

## 🔗 仓库

https://github.com/dragan2023/creative-master
