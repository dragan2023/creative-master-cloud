"""
配置管理模块
使用 pydantic-settings 管理环境变量和应用配置
"""
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
import os
import json


def get_version_from_file() -> str:
    """
    从项目根目录的 version.json 文件读取版本号
    如果文件不存在或解析失败，返回默认版本号
    """
    default_version = "1.1.0"
    try:
        # 获取项目根目录（backend 的上级目录）
        backend_dir = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        project_root = os.path.dirname(backend_dir)
        version_file = os.path.join(project_root, "version.json")

        if os.path.exists(version_file):
            with open(version_file, "r", encoding="utf-8") as f:
                version_data = json.load(f)
                return version_data.get("current_version", default_version)
    except Exception as e:
        # 读取失败时静默回退到默认值
        pass
    return default_version


class Settings(BaseSettings):
    """应用配置类"""

    # 应用基础配置
    APP_NAME: str = "全能创意大师"
    APP_VERSION: str = get_version_from_file()
    APP_BASE_URL: str = Field(
        default="http://localhost:5173",
        description="应用基础URL，用于OpenRouter等服务的HTTP-Referer头"
    )
    DEBUG: bool = True

    # 服务配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # 数据库配置
    DATABASE_URL: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/creative_master",
        description="PostgreSQL 数据库连接URL"
    )

    # Redis 配置
    REDIS_URL: str = Field(
        default="memory://",
        description="Redis 连接URL，使用 memory:// 禁用 Redis 并使用内存存储"
    )

    # JWT 配置
    SECRET_KEY: str = Field(
        default="your-secret-key-change-in-production",
        description="JWT 密钥"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24小时

    # LLM API Keys (预置)
    DEEPSEEK_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    DASHSCOPE_API_KEY: Optional[str] = None  # 千问
    ARK_API_KEY: Optional[str] = None  # 豆包
    T8STAR_API_KEY: Optional[str] = None  # 贞贞AI工坊

    # 向量数据库配置
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    CHROMA_MODEL_CACHE_DIR: str = "./data/chroma/models"  # ChromaDB 嵌入模型缓存目录

    # 知识图谱配置
    KNOWLEDGE_GRAPH_DIR: str = "./data/knowledge_graphs"  # 知识图谱存储目录

    # 文档预处理配置
    DOC_PREPROCESSOR_ENABLED: bool = True  # 是否启用文档预处理流水线

    # GPU 加速配置
    USE_GPU: bool = True  # 是否启用GPU加速（自动检测）
    GPU_DEVICE_ID: int = 0  # GPU设备ID
    FORCE_GPU: bool = False  # 强制使用GPU，如果GPU不可用则报错而不是降级到CPU（默认False，允许自动降级）

    # 代理配置
    HTTP_PROXY: Optional[str] = None  # HTTP代理地址，如 http://127.0.0.1:7890
    HTTPS_PROXY: Optional[str] = None  # HTTPS代理地址，如 http://127.0.0.1:7890

    # Hugging Face 配置
    # Hugging Face 镜像地址，默认使用国内镜像加速
    HF_ENDPOINT: Optional[str] = "https://hf-mirror.com"

    # 日志配置
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "./logs"

    # 文件上传配置
    MAX_UPLOAD_SIZE: int = Field(
        default=200 * 1024 * 1024,  # 200MB
        description="最大上传文件大小（字节）"
    )
    UPLOAD_DIR: str = Field(
        default="./data/uploads",
        description="文件上传目录"
    )
    MAX_IMAGE_SIZE: int = Field(
        default=50 * 1024 * 1024,  # 50MB
        description="图片最大上传大小（字节）"
    )
    MAX_DOC_SIZE: int = Field(
        default=50 * 1024 * 1024,  # 50MB
        description="文档最大上传大小（字节）"
    )
    ALLOWED_EXTENSIONS: set = {".pdf", ".docx", ".doc", ".txt", ".md"}

    # CORS 配置
    CORS_ORIGINS: str = Field(
        default="*",
        description="允许的跨域源，多个用逗号分隔，* 表示允许所有"
    )

    # 知识库配置
    TEMP_KNOWLEDGE_EXPIRE_HOURS: int = 24  # 临时知识库过期时间

    # 版本管理配置
    MAX_VERSION_HISTORY: int = 5  # 最大保留历史版本数

    # ==================== 批量生成速率控制配置 ====================
    BATCH_REQUEST_INTERVAL: float = Field(
        default=2.0,
        description="批量生成请求间隔时间（秒），用于避免API速率限制"
    )
    BATCH_RETRY_ON_RATE_LIMIT: bool = Field(
        default=True,
        description="遇到429速率限制错误时是否自动重试"
    )
    BATCH_MAX_RETRIES: int = Field(
        default=3,
        description="批量生成遇到速率限制时的最大重试次数"
    )
    BATCH_RETRY_BASE_DELAY: float = Field(
        default=2.0,
        description="重试基础延迟时间（秒），实际延迟 = base_delay * (2 ^ retry_count)"
    )

    # ==================== MCP 多内容提供商配置 ====================
    # MCP 服务总开关
    MCP_ENABLED: bool = Field(
        default=True,
        description="是否启用 MCP 多内容提供商服务"
    )

    # MCP 缓存配置
    MCP_CACHE_ENABLED: bool = Field(
        default=True,
        description="是否启用 MCP 数据缓存"
    )
    MCP_CACHE_TTL: int = Field(
        default=3600,
        description="MCP 缓存过期时间（秒），默认1小时"
    )

    # HotNews MCP 配置（中文社交媒体热点）
    MCP_HOTNEWS_ENABLED: bool = Field(
        default=True,
        description="是否启用 HotNews 中文社交媒体热点服务"
    )
    MCP_HOTNEWS_API_URL: str = Field(
        default="https://api.v3.vc/api/hot",
        description="HotNews API 地址"
    )

    # MCP 提供者列表（逗号分隔）
    MCP_PROVIDERS: str = Field(
        default="search_hotnews",
        description="启用的 MCP 提供者列表，逗号分隔（search_hotnews为基于搜索引擎的热点聚合）"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    def _normalize_path(self, path: str) -> str:
        """规范化路径，移除 ./ 前缀并确保格式正确"""
        # 移除 ./ 或 .\ 前缀
        normalized = path.lstrip("./").lstrip(".\\")
        # 获取 backend 目录的绝对路径
        backend_dir = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        # 拼接并规范化
        full_path = os.path.join(backend_dir, normalized)
        return os.path.normpath(full_path)

    def get_log_dir(self) -> str:
        """获取日志目录的绝对路径"""
        log_dir = self._normalize_path("logs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        return log_dir

    def get_chroma_dir(self) -> str:
        """获取 ChromaDB 持久化目录的绝对路径"""
        chroma_dir = self._normalize_path(self.CHROMA_PERSIST_DIR)
        if not os.path.exists(chroma_dir):
            os.makedirs(chroma_dir, exist_ok=True)
        return chroma_dir

    def get_chroma_model_cache_dir(self) -> str:
        """获取 ChromaDB 模型缓存目录的绝对路径"""
        model_cache_dir = self._normalize_path(self.CHROMA_MODEL_CACHE_DIR)
        if not os.path.exists(model_cache_dir):
            os.makedirs(model_cache_dir, exist_ok=True)
        return model_cache_dir

    def get_knowledge_graph_dir(self) -> str:
        """获取知识图谱存储目录的绝对路径"""
        kg_dir = self._normalize_path(self.KNOWLEDGE_GRAPH_DIR)
        if not os.path.exists(kg_dir):
            os.makedirs(kg_dir, exist_ok=True)
        return kg_dir

    def get_upload_dir(self) -> str:
        """获取文件上传目录的绝对路径"""
        upload_dir = self._normalize_path(self.UPLOAD_DIR)
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir, exist_ok=True)
        return upload_dir

    def get_cors_origins(self) -> list:
        """获取CORS允许的源列表"""
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache()
def get_settings() -> Settings:
    """获取配置单例"""
    return Settings()


# 预置模型配置（2026年最新）
# 模型类型: text(文本模型), image(图像生成模型), video(视频模型)
# vision: 是否支持图片输入（多模态）
# description: 模型能力说明
PRESET_MODELS = {
    # ==================== 通义千问（阿里云百炼）====================
    "qianwen": {
        "name": "通义千问 (阿里云百炼)",
        "provider": "qianwen",
        "notice": "国内服务商，直连即可。支持文本、图像、视频多模态输入。",
        "models": [
            # 文本模型（多模态）
            {"id": "qwen3.5-plus", "name": "Qwen3.5-Plus", "context": "256K",
                "vision": True, "type": "text", "max_output_tokens": 32768,
                "description": "旗舰多模态模型，支持文本/图像/视频输入，擅长语言理解、逻辑推理、代码生成、智能体任务"},
            {"id": "qwen3.5-plus-2026-02-15", "name": "Qwen3.5-Plus (快照)", "context": "256K",
                "vision": True, "type": "text", "max_output_tokens": 32768,
                "description": "Qwen3.5-Plus 快照版本"},
        ],
        "default_model": "qwen3.5-plus",
        "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "doc_url": "https://bailian.console.aliyun.com"
    },
    # 图像生成模型（单独配置）
    "qianwen-image": {
        "name": "通义千问-图像生成 (阿里云百炼)",
        "provider": "qianwen",
        "notice": "图像生成模型，通过文本描述生成图像。支持中英双语渲染。",
        "models": [
            {"id": "z-image-turbo", "name": "Z-Image-Turbo", "context": "-",
                "vision": False, "type": "image",
                "description": "轻量级文生图模型，快速生成高质量图像，分辨率512-2048px"},
            {"id": "qwen-image-edit-max-2026-01-16", "name": "Qwen-Image-Edit-Max", "context": "-",
                "vision": True, "type": "image",
                "description": "图像编辑模型，支持角色一致性、工业设计、几何推理"},
        ],
        "default_model": "z-image-turbo",
        "api_base": "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation",
        "doc_url": "https://bailian.console.aliyun.com"
    },

    # ==================== 火山引擎（豆包）====================
    "doubao": {
        "name": "豆包 (字节跳动/火山引擎)",
        "provider": "doubao",
        "notice": "模型名称需填写接入点ID（Endpoint ID），如：ep-2024xxxx-xxxxx。doubao-seed-2-0-pro支持文本、图像、视频多模态输入。",
        "models": [
            # 文本模型（多模态）
            {"id": "doubao-seed-2-0-pro-260215", "name": "Doubao-Seed-2.0-Pro", "context": "256K",
                "vision": True, "type": "text", "max_output_tokens": 32768,
                "description": "旗舰多模态模型，支持文本/图像/视频输入，擅长复杂推理、工具调用、视频理解"},
            {"id": "deepseek-v3-2-251201", "name": "DeepSeek-V3.2 (火山引擎)", "context": "128K",
                "vision": False, "type": "text", "max_output_tokens": 16384,
                "description": "DeepSeek V3.2版本，支持隐式缓存，擅长推理和工具调用"},
        ],
        "default_model": "doubao-seed-2-0-pro-260215",
        "api_base": "https://ark.cn-beijing.volces.com/api/v3",
        "doc_url": "https://console.volcengine.com/ark"
    },
    # 图像生成模型（豆包Seedream系列）
    "doubao-image": {
        "name": "豆包-图像生成 (火山引擎)",
        "provider": "doubao",
        "notice": "Seedream系列图像生成模型，支持文本生成图像、图像编辑。",
        "models": [
            {"id": "doubao-seedream-5-0-260128", "name": "Seedream-5.0", "context": "-",
                "vision": False, "type": "image",
                "description": "最新图像生成模型，高质量文生图"},
        ],
        "default_model": "doubao-seedream-5-0-260128",
        "api_base": "https://ark.cn-beijing.volces.com/api/v3",
        "doc_url": "https://console.volcengine.com/ark"
    },

    # ==================== 硅基流动 ====================
    "siliconflow": {
        "name": "硅基流动 (SiliconFlow)",
        "provider": "siliconflow",
        "notice": "聚合平台，提供多种开源模型API，模型名称格式：开发者/模型名",
        "models": [
            {"id": "deepseek-ai/DeepSeek-V3.2", "name": "DeepSeek-V3.2", "context": "164K",
                "vision": False, "type": "text", "max_output_tokens": 16384,
                "description": "推理优先模型，支持思考模式下的工具调用，Agent能力增强"},
        ],
        "default_model": "deepseek-ai/DeepSeek-V3.2",
        "api_base": "https://api.siliconflow.cn/v1",
        "doc_url": "https://cloud.siliconflow.cn"
    },

    # ==================== OpenRouter ====================
    "openrouter": {
        "name": "OpenRouter",
        "provider": "openrouter",
        "notice": "国外模型聚合平台，国内直连，支持支付宝充值。模型格式：提供商/模型名",
        "models": [
            # Google Gemini 文本模型
            {"id": "google/gemini-3.1-pro-preview", "name": "Gemini 3.1 Pro", "context": "1M",
                "vision": True, "type": "text", "max_output_tokens": 65536,
                "description": "Google多模态模型，擅长推理和工具调用"},
            # OpenAI 模型
            {"id": "openai/gpt-5.2-pro", "name": "GPT-5.2 Pro", "context": "400K",
                "vision": True, "type": "text", "max_output_tokens": 32768,
                "description": "OpenAI最新旗舰模型，40万token上下文，擅长编码和复杂推理"},
        ],
        "default_model": "google/gemini-3.1-pro-preview",
        "api_base": "https://openrouter.ai/api/v1",
        "doc_url": "https://openrouter.ai"
    },
    # OpenRouter 图像生成模型
    "openrouter-image": {
        "name": "OpenRouter-图像生成",
        "provider": "openrouter",
        "notice": "通过OpenRouter访问的图像生成模型。",
        "models": [
            {"id": "google/gemini-3-pro-image-preview", "name": "Gemini 3 Pro Image", "context": "-",
                "vision": False, "type": "image",
                "description": "Google最新图像生成模型，支持文本生成高质量图像"},
        ],
        "default_model": "google/gemini-3-pro-image-preview",
        "api_base": "https://openrouter.ai/api/v1",
        "doc_url": "https://openrouter.ai"
    },

    # ==================== 贞贞AI工坊（平价API聚合平台）====================
    "t8star": {
        "name": "贞贞AI工坊",
        "provider": "t8star",
        "notice": "平价API聚合平台，支持500+模型。分组需在官网令牌后台配置。",
        "api_base": "https://ai.t8star.cn/v1",
        "doc_url": "https://ai.t8star.cn/about",
        # 分组在贞贞工坊网站后台配置，无需在此选择
        "channels": [],
        "models": [
            # 文本模型
            {"id": "gpt-5.2-pro", "name": "GPT-5.2 Pro", "context": "400K",
                "vision": True, "type": "text", "max_output_tokens": 32768,
                "description": "OpenAI旗舰模型，40万token上下文"},
            {"id": "gpt-5.2-thinking", "name": "GPT-5.2 Thinking", "context": "200K",
                "vision": True, "type": "text", "max_output_tokens": 16384,
                "description": "OpenAI深度思考模型"},
            {"id": "claude-opus-4-5-20251101", "name": "Claude 4.5 Opus", "context": "200K",
                "vision": True, "type": "text", "max_output_tokens": 16384,
                "description": "Anthropic最强推理模型"},
            {"id": "glm-5", "name": "GLM-5", "context": "128K",
                "vision": False, "type": "text", "max_output_tokens": 8192,
                "description": "智谱AI SOTA模型，支持缓存计费"},
        ],
        "default_model": "gpt-5.2-pro"
    },
    # 贞贞AI工坊-图像生成
    "t8star-image": {
        "name": "贞贞AI工坊-图像生成",
        "provider": "t8star",
        "notice": "图像生成模型，支持Nano Banana 2、Gemini等。分组需在官网令牌后台配置。",
        "api_base": "https://ai.t8star.cn/v1",
        "doc_url": "https://ai.t8star.cn/about",
        # 分组在贞贞工坊网站后台配置，无需在此选择
        "channels": [],
        "models": [
            {"id": "gemini-3-pro-image-preview", "name": "Gemini 3 Pro Image", "context": "-",
                "vision": False, "type": "image",
                "description": "Google图像生成，支持高分辨率"},
            {"id": "nano-banana-2", "name": "Nano Banana 2", "context": "-",
                "vision": False, "type": "image",
                "description": "支持2K/4K高清"},
            {"id": "nano-banana-2-2k", "name": "Nano Banana 2 (2K)", "context": "-",
                "vision": False, "type": "image",
                "description": "固定2K分辨率"},
            {"id": "nano-banana-2-4k", "name": "Nano Banana 2 (4K)", "context": "-",
                "vision": False, "type": "image",
                "description": "固定4K分辨率"},
            {"id": "doubao-seedream-4-5", "name": "豆包Seedream 4.5", "context": "-",
                "vision": False, "type": "image",
                "description": "人物一致性好"},
        ],
        "default_model": "gemini-3-pro-image-preview"
    },
    # 贞贞AI工坊-视频生成
    "t8star-video": {
        "name": "贞贞AI工坊-视频生成",
        "provider": "t8star",
        "notice": "视频生成模型，Sora2/Veo3.1等。分组需在官网令牌后台配置。",
        "api_base": "https://ai.t8star.cn/v1",
        "doc_url": "https://ai.t8star.cn/about",
        # 分组在贞贞工坊网站后台配置，无需在此选择
        "channels": [],
        "models": [
            {"id": "sora-2", "name": "Sora 2", "context": "-",
                "vision": False, "type": "video",
                "description": "OpenAI视频生成，支持15秒"},
            {"id": "sora-2-pro", "name": "Sora 2 Pro", "context": "-",
                "vision": False, "type": "video",
                "description": "高清无水印版本"},
            {"id": "veo3.1", "name": "Veo3.1", "context": "-",
                "vision": False, "type": "video",
                "description": "Google视频生成"},
            {"id": "veo3.1-pro", "name": "Veo3.1 Pro", "context": "-",
                "vision": False, "type": "video",
                "description": "Google高质量视频"},
            {"id": "grok-video-3", "name": "Grok Video 3", "context": "-",
                "vision": False, "type": "video",
                "description": "支持中文配音，10秒视频"},
        ],
        "default_model": "sora-2"
    }
}

# ==================== 搜索服务提供商配置（国产化）====================
SEARCH_PROVIDERS = {
    "bocha": {
        "name": "博查AI搜索",
        "api_base": "https://api.bochaai.com/v1",
        "test_endpoint": "/web-search",
        "doc_url": "https://open.bochaai.com",
        "notice": "国内AI搜索服务，专为AI应用优化。无需代理，直连可用。",
        "models": [
            {"id": "bocha-web-search", "name": "博查Web搜索", "type": "search",
                "description": "高质量多模态AI搜索引擎，支持自然语言搜索"}
        ],
        "default_model": "bocha-web-search"
    },
    "baidu": {
        "name": "百度搜索",
        "api_base": "https://qianfan.baidubce.com/v2",
        "test_endpoint": "/ai_search/chat/completions",
        "doc_url": "https://ai.baidu.com/ai-doc/AppBuilder/pmaxd1hvy",
        "notice": "百度官方搜索API，中文搜索质量最高。免费额度：100次/天。",
        "models": [
            {"id": "baidu-ai-search", "name": "百度AI搜索", "type": "search",
                "description": "百度智能搜索，支持网页、图片、视频多模态搜索"}
        ],
        "default_model": "baidu-ai-search"
    }
}
