"""
配置管理模块
使用 pydantic-settings 管理环境变量和应用配置

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
import os
import json
import logging

from app.core.config_presets import PRESET_MODELS, SEARCH_PROVIDERS


def get_version_from_file() -> str:
    """
    从项目根目录的 version.json 文件读取版本号
    如果文件不存在或解析失败，返回默认版本号

    查找顺序:
    1. /app/version.json (Docker 容器路径)
    2. 项目根目录/version.json (本地开发路径)
    """
    default_version = "3.1.0"

    # 可能的 version.json 文件路径
    possible_paths = []

    # Docker 容器中的路径
    possible_paths.append("/app/version.json")

    # 本地开发环境：项目根目录/version.json
    try:
        backend_dir = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        project_root = os.path.dirname(backend_dir)
        possible_paths.append(os.path.join(project_root, "version.json"))
    except Exception:
        logging.debug("无法计算项目根目录，跳过 version.json 路径")

    # 按顺序尝试读取
    for version_file in possible_paths:
        try:
            if os.path.exists(version_file):
                with open(version_file, "r", encoding="utf-8") as f:
                    version_data = json.load(f)
                    version = version_data.get("current_version")
                    if version:
                        return version
        except Exception:
            continue

    return default_version


class Settings(BaseSettings):
    """应用配置类"""

    # 应用基础配置
    APP_NAME: str = "全能创意大师"
    APP_VERSION: str = Field(
        default_factory=get_version_from_file,
        description="应用版本号，从 version.json 动态读取"
    )
    APP_BASE_URL: str = Field(
        default="http://localhost:3001",
        description="应用基础URL，用于OpenRouter等服务的HTTP-Referer头"
    )
    DEBUG: bool = True

    # 服务配置
    HOST: str = "0.0.0.0"
    PORT: int = 8002

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
        default="",
        description="JWT 密钥，生产环境必须通过环境变量 SECRET_KEY 设置，启动时将校验"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24小时

    # LLM API Keys (预置)
    DEEPSEEK_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    DASHSCOPE_API_KEY: Optional[str] = None  # 千问（阿里云百炼）
    ARK_API_KEY: Optional[str] = None  # 豆包（火山引擎）
    T8STAR_API_KEY: Optional[str] = None  # 贞贞AI工坊
    SILICONFLOW_API_KEY: Optional[str] = None  # 硅基流动
    OPENROUTER_API_KEY: Optional[str] = None  # OpenRouter

    # 向量数据库配置
    CHROMA_PERSIST_DIR: str = "./data/chroma"
    CHROMA_MODEL_CACHE_DIR: str = "./data/chroma/models"  # ChromaDB 嵌入模型缓存目录

    # 知识图谱配置
    KNOWLEDGE_GRAPH_DIR: str = "./data/knowledge_graphs"  # 知识图谱存储目录

    # 加密配置
    ENCRYPTION_SALT: str = Field(
        default="creative_master_salt_v1",
        description="API Key 加密盐值，用于派生 Fernet 加密密钥，变更会导致已加密数据无法解密"
    )

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

    # DeepSeek 思考模式配置
    DEEPSEEK_ENABLE_THINKING: bool = Field(
        default=False,
        description="是否启用DeepSeek思考模式（Thinking Mode），启用后自动禁用temperature/top_p等参数"
    )
    DEEPSEEK_REASONING_EFFORT: str = Field(
        default="high",
        description="DeepSeek思考强度：high（高强度）或 max（最高强度，耗时更长）"
    )
    DEEPSEEK_THINKING_SAVE_DIR: str = Field(
        default="./data/thinking_logs",
        description="DeepSeek思考过程保存目录"
    )

    # 文件上传配置
    MAX_UPLOAD_SIZE: int = Field(
        default=500 * 1024 * 1024,  # 500MB（为大文本大纲上传提供足够空间）
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
        default=100 * 1024 * 1024,  # 100MB
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

    # ==================== 创意生成常量 ====================
    CREATIVE_ID_MIN: int = Field(
        default=100000,
        description="创意ID最小值（用于随机生成创意ID）"
    )
    CREATIVE_ID_MAX: int = Field(
        default=999999,
        description="创意ID最大值（用于随机生成创意ID）"
    )
    MAX_LLM_OUTPUT_TOKENS: int = Field(
        default=64000,
        description="LLM最大输出token安全上限，用于防止模型输出过长"
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
        extra = "ignore"  # 忽略 .env 中未定义的字段

    def _normalize_path(self, path: str) -> str:
        """规范化路径，移除 ./ 前缀并确保格式正确"""
        # 如果已经是绝对路径，直接返回
        if os.path.isabs(path):
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
            return path

        # 移除 ./ 或 .\\ 前缀
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


# PRESE_MODELS 和 SEARCH_PROVIDERS 已提取到 config_presets.py
