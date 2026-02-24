"""
配置管理模块
使用 pydantic-settings 管理环境变量和应用配置
"""
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
import os


class Settings(BaseSettings):
    """应用配置类"""

    # 应用基础配置
    APP_NAME: str = "全能创意大师"
    APP_VERSION: str = "1.0.0"
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
        default="redis://localhost:6379/0",
        description="Redis 连接URL"
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

    # 向量数据库配置
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    CHROMA_MODEL_CACHE_DIR: str = "./data/chroma/models"  # ChromaDB 嵌入模型缓存目录

    # 知识图谱配置
    KNOWLEDGE_GRAPH_DIR: str = "./data/knowledge_graphs"  # 知识图谱存储目录

    # 文档预处理配置 (GraphRAG增强)
    DOC_PREPROCESSOR_ENABLED: bool = True  # 是否启用文档预处理流水线
    MARKER_ENABLED: bool = True  # 是否启用 Marker 文档转换
    SEMANTIC_CHUNK_ENABLED: bool = True  # 是否启用语义切片
    SEMANTIC_CHUNK_SIZE: int = 1024  # 语义切片最大token数
    SEMANTIC_THRESHOLD: float = 0.7  # 语义相似度阈值 (0-1，越低分组越大)
    SUMMARIZATION_ENABLED: bool = False  # 是否启用摘要压缩（降低Token消耗）
    MARKER_MODEL_DIR: str = "./data/marker_models"  # Marker 模型存储目录

    # GPU 加速配置
    USE_GPU: bool = True  # 是否启用GPU加速（自动检测）
    GPU_DEVICE_ID: int = 0  # GPU设备ID
    FORCE_GPU: bool = True  # 强制使用GPU，如果GPU不可用则报错而不是降级到CPU

    # 代理配置
    HTTP_PROXY: Optional[str] = None  # HTTP代理地址，如 http://127.0.0.1:7890
    HTTPS_PROXY: Optional[str] = None  # HTTPS代理地址，如 http://127.0.0.1:7890

    # Hugging Face 配置
    # Hugging Face 镜像地址，如 https://hf-mirror.com
    HF_ENDPOINT: Optional[str] = None

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
    ALLOWED_EXTENSIONS: set = {".pdf", ".docx", ".doc", ".txt"}

    # CORS 配置
    CORS_ORIGINS: str = Field(
        default="*",
        description="允许的跨域源，多个用逗号分隔，* 表示允许所有"
    )

    # 知识库配置
    TEMP_KNOWLEDGE_EXPIRE_HOURS: int = 24  # 临时知识库过期时间

    # 版本管理配置
    MAX_VERSION_HISTORY: int = 5  # 最大保留历史版本数

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

    def get_log_dir(self) -> str:
        """获取日志目录的绝对路径"""
        # 获取 backend 目录的绝对路径
        backend_dir = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        log_dir = os.path.join(backend_dir, "logs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        return log_dir

    def get_chroma_dir(self) -> str:
        """获取 ChromaDB 持久化目录的绝对路径"""
        backend_dir = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        chroma_dir = os.path.join(backend_dir, self.CHROMA_PERSIST_DIR)
        if not os.path.exists(chroma_dir):
            os.makedirs(chroma_dir, exist_ok=True)
        return chroma_dir

    def get_chroma_model_cache_dir(self) -> str:
        """获取 ChromaDB 模型缓存目录的绝对路径"""
        backend_dir = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        model_cache_dir = os.path.join(
            backend_dir, self.CHROMA_MODEL_CACHE_DIR)
        if not os.path.exists(model_cache_dir):
            os.makedirs(model_cache_dir, exist_ok=True)
        return model_cache_dir

    def get_knowledge_graph_dir(self) -> str:
        """获取知识图谱存储目录的绝对路径"""
        backend_dir = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        kg_dir = os.path.join(backend_dir, self.KNOWLEDGE_GRAPH_DIR)
        if not os.path.exists(kg_dir):
            os.makedirs(kg_dir, exist_ok=True)
        return kg_dir

    def get_marker_model_dir(self) -> str:
        """获取 Marker 模型存储目录的绝对路径"""
        backend_dir = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        model_dir = os.path.join(backend_dir, self.MARKER_MODEL_DIR)
        if not os.path.exists(model_dir):
            os.makedirs(model_dir, exist_ok=True)
        return model_dir

    def get_upload_dir(self) -> str:
        """获取文件上传目录的绝对路径"""
        backend_dir = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        upload_dir = os.path.join(backend_dir, self.UPLOAD_DIR)
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


# 预置模型配置（2025-2026年最新）
# vision: 是否支持图片输入（多模态）
# description: 模型能力说明
PRESET_MODELS = {
    "deepseek": {
        "name": "DeepSeek",
        "provider": "deepseek",
        "notice": "国内服务商，直连即可",
        "models": [
            {"id": "deepseek-chat", "name": "DeepSeek-V3.2", "context": "128K",
                "vision": False, "description": "通用对话模型，擅长创意写作、代码生成、逻辑推理"},
            {"id": "deepseek-reasoner", "name": "DeepSeek-R1", "context": "128K",
                "vision": False, "description": "深度推理模型，擅长数学计算、复杂逻辑分析"}
        ],
        "default_model": "deepseek-chat",
        "api_base": "https://api.deepseek.com/v1",
        "doc_url": "https://platform.deepseek.com"
    },
    "doubao": {
        "name": "豆包 (字节跳动/火山引擎)",
        "provider": "doubao",
        "notice": "模型名称需填写接入点ID（Endpoint ID），如：ep-2024xxxx-xxxxx。请在火山引擎控制台创建推理接入点后获取。",
        "models": [
            {"id": "ep-xxxx-xxxx", "name": "Endpoint ID示例", "context": "256K",
                "vision": True, "description": "请在火山引擎控制台创建接入点，使用接入点ID作为模型名称"}
        ],
        "default_model": "ep-xxxx-xxxx",
        "api_base": "https://ark.cn-beijing.volces.com/api/v3",
        "doc_url": "https://console.volcengine.com/ark"
    },
    "qianwen": {
        "name": "通义千问 (阿里云)",
        "provider": "qianwen",
        "notice": "国内服务商，直连即可",
        "models": [
            {"id": "qwen-max", "name": "Qwen-Max", "context": "256K",
                "vision": True, "description": "旗舰多模态模型，综合能力最强"},
            {"id": "qwen-plus", "name": "Qwen-Plus", "context": "1M",
                "vision": True, "description": "多模态模型，超长上下文"},
            {"id": "qwen-turbo", "name": "Qwen-Turbo", "context": "1M",
                "vision": True, "description": "快速多模态模型，响应快"},
            {"id": "qwen-coder-plus", "name": "Qwen-Coder-Plus", "context": "1M",
                "vision": False, "description": "代码专用模型"},
            {"id": "qwen-vl-max", "name": "Qwen-VL-Max", "context": "32K",
                "vision": True, "description": "视觉理解专用模型，擅长OCR、图表分析"}
        ],
        "default_model": "qwen-plus",
        "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "doc_url": "https://bailian.console.aliyun.com"
    },
    "zhipu": {
        "name": "智谱AI (GLM)",
        "provider": "zhipu",
        "notice": "国内服务商，直连即可",
        "models": [
            {"id": "glm-4-plus", "name": "GLM-4-Plus", "context": "128K",
                "vision": False, "description": "旗舰对话模型，擅长中文创作、知识问答"},
            {"id": "glm-4-flash", "name": "GLM-4-Flash", "context": "128K",
                "vision": False, "description": "快速模型，性价比高"},
            {"id": "glm-4-air", "name": "GLM-4-Air", "context": "128K",
                "vision": False, "description": "均衡模型"},
            {"id": "glm-z1-air", "name": "GLM-Z1-Air", "context": "128K",
                "vision": False, "description": "推理增强模型"},
            {"id": "glm-4v-plus", "name": "GLM-4V-Plus", "context": "128K",
                "vision": True, "description": "多模态模型，支持图片理解"}
        ],
        "default_model": "glm-4-flash",
        "api_base": "https://open.bigmodel.cn/api/paas/v4",
        "doc_url": "https://open.bigmodel.cn"
    },
    "moonshot": {
        "name": "月之暗面 (Kimi)",
        "provider": "moonshot",
        "notice": "国内服务商，直连即可",
        "models": [
            {"id": "kimi-latest", "name": "Kimi Latest", "context": "128K",
                "vision": True, "description": "最新多模态模型，综合能力最强"},
            {"id": "moonshot-v1-8k", "name": "Moonshot V1 8K", "context": "8K",
                "vision": False, "description": "标准模型"},
            {"id": "moonshot-v1-32k", "name": "Moonshot V1 32K", "context": "32K",
                "vision": False, "description": "中长上下文模型"},
            {"id": "moonshot-v1-128k", "name": "Moonshot V1 128K", "context": "128K",
                "vision": False, "description": "长上下文模型"}
        ],
        "default_model": "kimi-latest",
        "api_base": "https://api.moonshot.cn/v1",
        "doc_url": "https://platform.moonshot.cn"
    },
    "baichuan": {
        "name": "百川智能",
        "provider": "baichuan",
        "notice": "国内服务商，直连即可",
        "models": [
            {"id": "Baichuan4", "name": "Baichuan4", "context": "128K",
                "vision": True, "description": "旗舰多模态模型"},
            {"id": "Baichuan4-Turbo", "name": "Baichuan4 Turbo", "context": "128K",
                "vision": True, "description": "快速多模态模型"},
            {"id": "Baichuan3-Turbo", "name": "Baichuan3 Turbo", "context": "128K",
                "vision": False, "description": "对话模型"}
        ],
        "default_model": "Baichuan4-Turbo",
        "api_base": "https://api.baichuan-ai.com/v1",
        "doc_url": "https://platform.baichuan-ai.com"
    },
    "minimax": {
        "name": "MiniMax",
        "provider": "minimax",
        "notice": "部分API需要group_id参数，请参考官方文档",
        "models": [
            {"id": "MiniMax-Text-01", "name": "MiniMax-Text-01", "context": "4M",
                "vision": False, "description": "超长上下文模型（400万token）"},
            {"id": "abab6.5s-chat", "name": "abab6.5s", "context": "245K",
                "vision": False, "description": "快速模型"},
            {"id": "abab6.5g-chat", "name": "abab6.5g", "context": "245K",
                "vision": True, "description": "多模态模型"}
        ],
        "default_model": "abab6.5s-chat",
        "api_base": "https://api.minimax.chat/v1",
        "doc_url": "https://platform.minimax.io"
    },
    "yi": {
        "name": "零一万物 (Yi)",
        "provider": "yi",
        "notice": "国内服务商，直连即可",
        "models": [
            {"id": "yi-large", "name": "Yi Large", "context": "32K",
                "vision": False, "description": "旗舰对话模型"},
            {"id": "yi-large-turbo", "name": "Yi Large Turbo", "context": "16K",
                "vision": False, "description": "快速模型"},
            {"id": "yi-medium", "name": "Yi Medium", "context": "16K",
                "vision": False, "description": "均衡模型"},
            {"id": "yi-vl-plus", "name": "Yi-VL-Plus", "context": "16K",
                "vision": True, "description": "多模态模型"}
        ],
        "default_model": "yi-large",
        "api_base": "https://api.lingyiwanwu.com/v1",
        "doc_url": "https://platform.lingyiwanwu.com"
    },
    "siliconflow": {
        "name": "硅基流动 (SiliconFlow)",
        "provider": "siliconflow",
        "notice": "聚合平台，提供多种开源模型API，模型名称格式：开发者/模型名",
        "models": [
            {"id": "deepseek-ai/DeepSeek-V3", "name": "DeepSeek-V3",
                "context": "64K", "vision": False, "description": "开源旗舰模型"},
            {"id": "Qwen/Qwen2.5-72B-Instruct", "name": "Qwen2.5-72B",
                "context": "32K", "vision": False, "description": "开源大模型"},
            {"id": "Qwen/Qwen2-VL-72B-Instruct", "name": "Qwen2-VL-72B", "context": "32K",
                "vision": True, "description": "开源多模态模型"},
            {"id": "meta-llama/Llama-3.3-70B-Instruct", "name": "Llama-3.3-70B",
                "context": "8K", "vision": False, "description": "Meta开源模型"}
        ],
        "default_model": "deepseek-ai/DeepSeek-V3",
        "api_base": "https://api.siliconflow.cn/v1",
        "doc_url": "https://cloud.siliconflow.cn"
    },
    "modelscope": {
        "name": "魔搭 (ModelScope)",
        "provider": "modelscope",
        "notice": "阿里云模型社区，提供多种模型API",
        "models": [
            {"id": "qwen-plus", "name": "Qwen-Plus", "context": "128K",
                "vision": True, "description": "多模态模型"},
            {"id": "qwen-turbo", "name": "Qwen-Turbo", "context": "8K",
                "vision": False, "description": "快速模型"},
            {"id": "qwen-max", "name": "Qwen-Max", "context": "32K",
                "vision": True, "description": "旗舰多模态模型"},
            {"id": "deepseek-v3", "name": "DeepSeek-V3", "context": "64K",
                "vision": False, "description": "开源旗舰模型"}
        ],
        "default_model": "qwen-plus",
        "api_base": "https://api-inference.modelscope.cn/v1",
        "doc_url": "https://modelscope.cn"
    },
    "openai": {
        "name": "OpenAI",
        "provider": "openai",
        "notice": "国外服务商，需要代理访问",
        "models": [
            {"id": "gpt-4o", "name": "GPT-4o", "context": "128K",
                "vision": True, "description": "旗舰多模态模型，综合能力最强"},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "context": "128K",
                "vision": True, "description": "轻量多模态模型，性价比高"},
            {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "context": "128K",
                "vision": True, "description": "多模态模型"},
            {"id": "o1-preview", "name": "o1 Preview", "context": "128K",
                "vision": False, "description": "推理增强模型"},
            {"id": "o1-mini", "name": "o1 Mini", "context": "128K",
                "vision": False, "description": "轻量推理模型"}
        ],
        "default_model": "gpt-4o-mini",
        "api_base": "https://api.openai.com/v1",
        "doc_url": "https://platform.openai.com"
    },
    "google": {
        "name": "Google Gemini",
        "provider": "google",
        "notice": "国外服务商，需要代理访问。使用Google AI Studio API Key",
        "models": [
            {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "context": "1M",
                "vision": True, "description": "最新多模态模型，响应快"},
            {"id": "gemini-2.0-flash-lite", "name": "Gemini 2.0 Flash-Lite",
                "context": "1M", "vision": True, "description": "轻量多模态模型"},
            {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro", "context": "2M",
                "vision": True, "description": "超长上下文多模态模型（200万token）"},
            {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash", "context": "1M",
                "vision": True, "description": "快速多模态模型"}
        ],
        "default_model": "gemini-2.0-flash",
        "api_base": None,
        "doc_url": "https://aistudio.google.com"
    },
    "openrouter": {
        "name": "OpenRouter",
        "provider": "openrouter",
        "notice": "国外模型聚合平台，国内直连，支持支付宝充值。模型格式：提供商/模型名",
        "models": [
            # OpenAI 模型
            {"id": "openai/gpt-4o", "name": "GPT-4o", "context": "128K",
                "vision": True, "description": "OpenAI旗舰多模态模型"},
            {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini", "context": "128K",
                "vision": True, "description": "轻量多模态模型，性价比高"},
            {"id": "openai/o1-preview", "name": "o1 Preview", "context": "128K",
                "vision": False, "description": "推理增强模型"},
            {"id": "openai/o1-mini", "name": "o1 Mini", "context": "128K",
                "vision": False, "description": "轻量推理模型"},
            # Google 模型
            {"id": "google/gemini-2.0-flash-001", "name": "Gemini 2.0 Flash", "context": "1M",
                "vision": True, "description": "Google最新多模态模型"},
            {"id": "google/gemini-1.5-pro", "name": "Gemini 1.5 Pro", "context": "2M",
                "vision": True, "description": "超长上下文模型"},
            {"id": "google/gemini-1.5-flash", "name": "Gemini 1.5 Flash", "context": "1M",
                "vision": True, "description": "快速多模态模型"},
            # Anthropic 模型
            {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet", "context": "200K",
                "vision": True, "description": "Anthropic最强模型"},
            {"id": "anthropic/claude-3.5-haiku", "name": "Claude 3.5 Haiku", "context": "200K",
                "vision": True, "description": "快速轻量模型"},
            {"id": "anthropic/claude-3-opus", "name": "Claude 3 Opus", "context": "200K",
                "vision": True, "description": "旗舰模型"},
            # xAI 模型
            {"id": "x-ai/grok-beta", "name": "Grok Beta", "context": "128K",
                "vision": False, "description": "xAI旗舰模型"},
            {"id": "x-ai/grok-2-1212", "name": "Grok 2", "context": "128K",
                "vision": False, "description": "xAI最新模型"},
            # Meta 模型
            {"id": "meta-llama/llama-3.3-70b-instruct", "name": "Llama 3.3 70B", "context": "8K",
                "vision": False, "description": "Meta开源旗舰模型"},
            {"id": "meta-llama/llama-3.2-90b-vision-instruct", "name": "Llama 3.2 90B Vision", "context": "128K",
                "vision": True, "description": "Meta多模态模型"},
            # DeepSeek 模型
            {"id": "deepseek/deepseek-chat", "name": "DeepSeek Chat", "context": "64K",
                "vision": False, "description": "DeepSeek对话模型"},
            {"id": "deepseek/deepseek-r1", "name": "DeepSeek R1", "context": "64K",
                "vision": False, "description": "DeepSeek推理模型"}
        ],
        "default_model": "openai/gpt-4o-mini",
        "api_base": "https://openrouter.ai/api/v1",
        "doc_url": "https://openrouter.ai"
    }
}
