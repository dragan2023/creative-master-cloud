# 全能创意大师

一款基于 AI 的智能创意生成平台，支持短视频脚本、剧本大纲、小说大纲、平面广告、TVC 广告等多种创意内容生成。

## 功能特性

- **多模态 AI 对话** - 支持多种主流 AI 模型（DeepSeek、通义千问、豆包、OpenAI、Google Gemini 等）
- **智能创意生成** - 短视频脚本、剧本大纲、小说大纲、平面广告、TVC 广告
- **知识库管理** - 上传文档构建知识库，增强 AI 生成能力
- **文档智能解析** - 支持 PDF、Word、TXT 等多种格式
- **知识图谱** - 可视化知识关系网络

## 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- npm 或 yarn

### 一键启动（Windows）

双击运行 `start.bat`，脚本将自动：

1. 检测并安装 Python 环境
2. 检测并安装 Node.js 环境
3. 创建虚拟环境并安装依赖
4. 启动后端和前端服务

### 手动安装

#### 后端

```bash
cd backend
python -m venv venv
venv\Scripts\activate  # Windows
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

#### 前端

```bash
cd frontend
npm install
npm run dev
```

### 访问地址

- 前端界面：http://localhost:5173
- API 文档：http://localhost:8000/docs

## 配置说明

### API Key 配置

在应用的「API Key 管理」页面添加你的 AI 模型 API 密钥：

- **DeepSeek** - https://platform.deepseek.com
- **通义千问** - https://bailian.console.aliyun.com
- **豆包** - https://console.volcengine.com/ark
- **OpenAI** - https://platform.openai.com
- **Google Gemini** - https://aistudio.google.com

### 环境变量

在 `backend/.env` 文件中配置：

```env
APP_NAME=全能创意大师
DEBUG=True
DATABASE_URL=sqlite+aiosqlite:///./data/creative_master.db
SECRET_KEY=your-secret-key
```

## 项目结构

```
├── backend/                # 后端代码
│   ├── app/
│   │   ├── agents/        # AI代理模块
│   │   ├── api/           # API接口
│   │   ├── core/          # 核心配置
│   │   ├── models/        # 数据模型
│   │   ├── schemas/       # 数据结构
│   │   ├── tools/         # 工具模块
│   │   └── main.py        # 入口文件
│   └── requirements.txt
├── frontend/               # 前端代码
│   ├── src/
│   │   ├── api/           # API调用
│   │   ├── components/    # 组件
│   │   ├── views/         # 页面
│   │   └── main.js
│   └── package.json
├── start.bat              # Windows启动脚本
└── docker-compose.yml     # Docker配置
```

## 技术栈

### 后端

- FastAPI - 高性能 Python Web 框架
- SQLAlchemy - ORM
- ChromaDB - 向量数据库
- LangChain - AI 应用框架

### 前端

- Vue 3 - 渐进式 JavaScript 框架
- Element Plus - UI 组件库
- Vite - 构建工具

## 更新日志

### v3.1.16

- 首次发布
- AI 智能对话功能
- 文档智能解析
- 知识库管理
- 多模型支持

## 许可证

MIT License

## 仓库地址

https://github.com/dragan2023/creative-master

## 贡献

欢迎提交 Issue 和 Pull Request！
