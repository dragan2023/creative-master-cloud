"""生成 writer_master 后端 Phase1 核心文件：常量、值对象、配置、数据库模型"""
import os

BASE = r'F:\python_project\writer_master\backend'


def write_file(rel_path, content):
    full_path = os.path.join(BASE, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content.strip() + '\n')
    print(f'  Created: {rel_path}')


# ==================== core/constants.py ====================
write_file('app/core/constants.py', '''
"""全局常量定义 - 替代所有硬编码字面量"""


class GenerationConstants:
    """生成相关常量"""
    MAX_CONTEXT_TOKENS = 4096
    RECENT_CHAPTERS_COUNT = 3
    SUMMARY_MAX_CHARS = 2000
    GLOBAL_OUTLINE_PREVIEW_LIMIT = 3000
    CHAPTER_OUTLINE_PREVIEW_LIMIT = 5000
    BATCH_GENERATION_SIZE = 5
    MAX_RETRY_COUNT = 3
    STREAMING_TIMEOUT_SECONDS = 300
    WORDS_PER_MINUTE = 250


class OutlineConstants:
    """大纲生成相关常量"""
    GLOBAL_OUTLINE_MIN_CHARS = 2000
    UNIT_SUMMARY_MIN_CHARS = 100
    UNIT_SUMMARY_MAX_CHARS = 300
    CHAPTER_OUTLINE_MIN_CHARS = 500
    CHAPTER_OUTLINE_MAX_CHARS = 1000


class TokenConstants:
    """Token相关常量"""
    DEFAULT_MAX_TOKENS = 4096
    OUTLINE_MAX_TOKENS = 8000
    CHAPTER_CONTENT_MAX_TOKENS = 4000
    QUALITY_CHECK_MAX_TOKENS = 2000


class ProjectConstants:
    """项目相关常量"""
    PROJECT_CODE_PREFIX = "WM"
    MAX_TITLE_LENGTH = 200
    MAX_GENRE_LENGTH = 50
    MAX_PLATFORM_LENGTH = 50


class QualityConstants:
    """质控相关常量"""
    MIN_SCORE = 0
    MAX_SCORE = 100
    PASS_THRESHOLD = 60
    EXCELLENT_THRESHOLD = 80
    WEIGHT_CONSISTENCY = 0.4
    WEIGHT_COHERENCE = 0.35
    WEIGHT_STYLE_MATCH = 0.25
''')

# ==================== domain/models/value_objects/content_type.py ====================
write_file('app/domain/models/value_objects/content_type.py', '''
"""内容类型值对象 - 封装类型校验与标签映射"""


class ContentType:
    """内容类型值对象"""
    NOVEL = "novel"
    SERIES_SCRIPT = "series_script"
    MOVIE_SCRIPT = "movie_script"

    _LABELS = {
        "novel": "小说",
        "series_script": "剧集剧本",
        "movie_script": "电影剧本",
    }
    _UNIT_LABELS = {
        "novel": "章",
        "series_script": "集",
        "movie_script": "场",
    }

    def __init__(self, value: str):
        self._validate(value)
        self._value = value

    def _validate(self, value: str):
        valid_types = {self.NOVEL, self.SERIES_SCRIPT, self.MOVIE_SCRIPT}
        if value not in valid_types:
            raise ValueError(f"无效的内容类型: {value}")

    @property
    def value(self) -> str:
        return self._value

    @property
    def label(self) -> str:
        return self._LABELS[self._value]

    @property
    def unit_label(self) -> str:
        return self._UNIT_LABELS[self._value]

    @property
    def is_novel(self) -> bool:
        return self._value == self.NOVEL

    @property
    def is_series_script(self) -> bool:
        return self._value == self.SERIES_SCRIPT

    @property
    def is_movie_script(self) -> bool:
        return self._value == self.MOVIE_SCRIPT

    def __eq__(self, other):
        if isinstance(other, ContentType):
            return self._value == other._value
        return False

    def __hash__(self):
        return hash(self._value)

    def __repr__(self):
        return f"ContentType({self._value!r})"
''')

# ==================== domain/models/value_objects/project_status.py ====================
write_file('app/domain/models/value_objects/project_status.py', '''
"""项目状态值对象"""


class ProjectStatus:
    """项目状态值对象 - 封装状态校验与流转规则"""
    INIT = "init"
    DIRECTORY = "directory"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"

    _LABELS = {
        "init": "初始化",
        "directory": "目录生成中",
        "generating": "正文生成中",
        "completed": "已完成",
        "failed": "失败",
        "paused": "已暂停",
    }

    _VALID_TRANSITIONS = {
        "init": {"directory", "generating", "failed"},
        "directory": {"generating", "failed", "paused"},
        "generating": {"completed", "failed", "paused"},
        "paused": {"generating", "failed"},
        "completed": {"generating"},
        "failed": {"init"},
    }

    def __init__(self, value: str):
        self._validate(value)
        self._value = value

    def _validate(self, value: str):
        valid = {self.INIT, self.DIRECTORY, self.GENERATING,
                 self.COMPLETED, self.FAILED, self.PAUSED}
        if value not in valid:
            raise ValueError(f"无效的项目状态: {value}")

    @property
    def value(self) -> str:
        return self._value

    @property
    def label(self) -> str:
        return self._LABELS[self._value]

    def can_transition_to(self, target: "ProjectStatus") -> bool:
        """检查是否可以流转到目标状态"""
        return target._value in self._VALID_TRANSITIONS.get(self._value, set())

    def __eq__(self, other):
        if isinstance(other, ProjectStatus):
            return self._value == other._value
        return False

    def __hash__(self):
        return hash(self._value)

    def __repr__(self):
        return f"ProjectStatus({self._value!r})"
''')

# ==================== domain/models/value_objects/word_count.py ====================
write_file('app/domain/models/value_objects/word_count.py', '''
"""字数相关值对象"""
from app.domain.models.value_objects.content_type import ContentType
from app.core.constants import GenerationConstants


class WordsPerChapter:
    """每章字数值对象 - 封装校验与计算"""
    MIN_WORDS = 500
    MAX_WORDS = 10000

    _DEFAULTS = {
        ContentType.NOVEL: 3000,
        ContentType.SERIES_SCRIPT: 2500,
        ContentType.MOVIE_SCRIPT: 250,
    }

    def __init__(self, value: int, content_type: ContentType):
        self._validate(value)
        self._value = value
        self._content_type = content_type

    def _validate(self, value: int):
        if not (self.MIN_WORDS <= value <= self.MAX_WORDS):
            raise ValueError(
                f"每章字数必须在{self.MIN_WORDS}-{self.MAX_WORDS}之间"
            )

    @classmethod
    def default_for(cls, content_type: ContentType) -> "WordsPerChapter":
        """根据内容类型获取默认字数"""
        default_value = cls._DEFAULTS.get(content_type.value, 3000)
        return cls(default_value, content_type)

    @property
    def value(self) -> int:
        return self._value

    def estimated_duration_minutes(self) -> float:
        """估算时长（分钟）"""
        return self._value / GenerationConstants.WORDS_PER_MINUTE
''')

# ==================== domain/models/value_objects/quality_score.py ====================
write_file('app/domain/models/value_objects/quality_score.py', '''
"""质控分数值对象"""
from app.core.constants import QualityConstants


class QualityScore:
    """质控分数值对象 - 封装评分逻辑与等级判定"""

    def __init__(self, consistency: int, coherence: int, style_match: int):
        self._validate_dimension(consistency, "内容一致性")
        self._validate_dimension(coherence, "逻辑连贯性")
        self._validate_dimension(style_match, "风格适配性")
        self._consistency = consistency
        self._coherence = coherence
        self._style_match = style_match

    def _validate_dimension(self, value: int, name: str):
        if not (QualityConstants.MIN_SCORE <= value <= QualityConstants.MAX_SCORE):
            raise ValueError(
                f"{name}分数必须在{QualityConstants.MIN_SCORE}-"
                f"{QualityConstants.MAX_SCORE}之间"
            )

    @property
    def consistency(self) -> int:
        return self._consistency

    @property
    def coherence(self) -> int:
        return self._coherence

    @property
    def style_match(self) -> int:
        return self._style_match

    @property
    def overall_score(self) -> float:
        return (
            self._consistency * QualityConstants.WEIGHT_CONSISTENCY
            + self._coherence * QualityConstants.WEIGHT_COHERENCE
            + self._style_match * QualityConstants.WEIGHT_STYLE_MATCH
        )

    @property
    def grade(self) -> str:
        if self.overall_score >= QualityConstants.EXCELLENT_THRESHOLD:
            return "优秀"
        if self.overall_score >= QualityConstants.PASS_THRESHOLD:
            return "合格"
        return "需修正"

    @property
    def is_passed(self) -> bool:
        return self.overall_score >= QualityConstants.PASS_THRESHOLD
''')

# ==================== domain/models/value_objects/__init__.py ====================
write_file('app/domain/models/value_objects/__init__.py', '''
"""值对象统一导出"""
from app.domain.models.value_objects.content_type import ContentType
from app.domain.models.value_objects.project_status import ProjectStatus
from app.domain.models.value_objects.word_count import WordsPerChapter
from app.domain.models.value_objects.quality_score import QualityScore

__all__ = ["ContentType", "ProjectStatus", "WordsPerChapter", "QualityScore"]
''')

# ==================== core/config.py ====================
write_file('app/core/config.py', '''
"""配置管理模块 - 使用 pydantic-settings 管理环境变量"""
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field
from functools import lru_cache
import os


class Settings(BaseSettings):
    """应用配置类"""
    APP_NAME: str = "Writer Master"
    DEBUG: bool = True
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./data/writer_master.db",
        description="数据库连接URL"
    )

    SECRET_KEY: str = Field(
        default="change-this-in-production",
        description="JWT密钥"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    REDIS_URL: str = Field(
        default="memory://",
        description="Redis连接URL"
    )

    CHROMA_PERSIST_DIR: str = "./data/chroma"
    KNOWLEDGE_GRAPH_DIR: str = "./data/knowledge_graphs"

    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "./logs"

    UPLOAD_DIR: str = "./data/uploads"
    MAX_UPLOAD_SIZE: int = 200 * 1024 * 1024
    ALLOWED_EXTENSIONS: set = {".pdf", ".docx", ".doc", ".txt", ".md"}

    CORS_ORIGINS: str = "*"

    BATCH_REQUEST_INTERVAL: float = 2.0
    BATCH_RETRY_ON_RATE_LIMIT: bool = True
    BATCH_MAX_RETRIES: int = 3
    BATCH_RETRY_BASE_DELAY: float = 2.0

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"

    def _normalize_path(self, path: str) -> str:
        if os.path.isabs(path):
            if not os.path.exists(path):
                os.makedirs(path, exist_ok=True)
            return path
        normalized = path.lstrip("./").lstrip(".\\\\")
        backend_dir = os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))
        full_path = os.path.join(backend_dir, normalized)
        return os.path.normpath(full_path)

    def get_upload_dir(self) -> str:
        upload_dir = self._normalize_path(self.UPLOAD_DIR)
        if not os.path.exists(upload_dir):
            os.makedirs(upload_dir, exist_ok=True)
        return upload_dir

    def get_chroma_dir(self) -> str:
        chroma_dir = self._normalize_path(self.CHROMA_PERSIST_DIR)
        if not os.path.exists(chroma_dir):
            os.makedirs(chroma_dir, exist_ok=True)
        return chroma_dir

    def get_cors_origins(self) -> list:
        if self.CORS_ORIGINS == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


@lru_cache()
def get_settings() -> Settings:
    return Settings()
''')

# ==================== core/database.py ====================
write_file('app/core/database.py', '''
"""数据库连接配置"""
from sqlalchemy.ext.asyncio import (
    AsyncSession, create_async_engine, async_sessionmaker
)
from sqlalchemy.orm import declarative_base
from sqlalchemy import MetaData
from typing import AsyncGenerator

from app.core.config import get_settings

settings = get_settings()
is_sqlite = settings.DATABASE_URL.startswith("sqlite")

if is_sqlite:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        connect_args={"check_same_thread": False}
    )
else:
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10
    )

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

Base = declarative_base()

metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s"
    }
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """获取数据库会话的依赖项"""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """初始化数据库"""
    from app.models.project import NovelProject
    from app.models.chapter import NovelChapter
    from app.models.user import User

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    """关闭数据库连接"""
    await engine.dispose()
''')

# ==================== core/logger.py ====================
write_file('app/core/logger.py', '''
"""日志配置模块"""
import sys
from loguru import logger
from app.core.config import get_settings

settings = get_settings()


def get_logger(name: str = __name__):
    """获取日志记录器"""
    _logger = logger.bind(name=name)
    return _logger


# 配置日志输出
logger.remove()
logger.add(
    sys.stderr,
    level=settings.LOG_LEVEL,
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
           "<level>{level: <8}</level> | "
           "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
           "<level>{message}</level>"
)
''')

# ==================== models/base.py ====================
write_file('app/models/base.py', '''
"""数据库模型基类"""
from datetime import datetime, timezone, timedelta
from sqlalchemy import Column, DateTime, Integer
from sqlalchemy.orm import declared_attr
from app.core.database import Base


def get_local_now():
    """获取本地时间（UTC+8）"""
    return datetime.now(timezone(timedelta(hours=8))).replace(tzinfo=None)


class TimestampMixin:
    """时间戳混入类"""

    @declared_attr
    def created_at(cls):
        return Column(DateTime, default=get_local_now, nullable=False)

    @declared_attr
    def updated_at(cls):
        return Column(
            DateTime, default=get_local_now, onupdate=get_local_now, nullable=False
        )


class BaseModel(Base, TimestampMixin):
    """模型基类"""
    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    def to_dict(self, exclude: list = None) -> dict:
        exclude = exclude or []
        result = {}
        for column in self.__table__.columns:
            if column.name not in exclude:
                value = getattr(self, column.name)
                if isinstance(value, datetime):
                    value = value.isoformat()
                result[column.name] = value
        return result
''')

# ==================== models/user.py ====================
write_file('app/models/user.py', '''
"""用户模型 - 独立系统精简版"""
from sqlalchemy import Column, String, Boolean
from app.models.base import BaseModel


class User(BaseModel):
    """用户表"""
    __tablename__ = "users"

    username = Column(String(50), unique=True, nullable=False, comment="用户名")
    email = Column(String(100), unique=True, nullable=True, comment="邮箱")
    hashed_password = Column(String(255), nullable=False, comment="密码哈希")
    is_active = Column(Boolean, default=True, comment="是否激活")
    is_admin = Column(Boolean, default=False, comment="是否管理员")

    def __repr__(self):
        return f"<User(id={self.id}, username='{self.username}')>"
''')

# ==================== models/project.py ====================
write_file('app/models/project.py', '''
"""小说/剧本项目模型"""
from sqlalchemy import (
    Column, String, Integer, ForeignKey, Text, Enum, JSON, Boolean
)
from sqlalchemy.orm import relationship
import enum

from app.models.base import BaseModel


class ProjectType(str, enum.Enum):
    NOVEL = "novel"
    SCRIPT = "script"


class ProjectStatus(str, enum.Enum):
    INIT = "init"
    DIRECTORY = "directory"
    GENERATING = "generating"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"


class NovelProject(BaseModel):
    """小说/剧本项目表"""
    __tablename__ = "novel_projects"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, comment="用户ID")

    title = Column(String(200), nullable=False, comment="项目标题")
    project_type = Column(Enum(ProjectType), nullable=False, comment="项目类型")
    content_type = Column(String(20), nullable=True,
                          comment="内容类型(novel/series_script/movie_script)")
    genre = Column(String(50), nullable=True, comment="类型标签")
    target_platform = Column(String(50), nullable=True, comment="目标平台")

    outline_file_path = Column(String(255), nullable=True, comment="大纲文件路径")
    outline_content = Column(Text, nullable=True, comment="大纲原始内容")

    global_outline_content = Column(Text, nullable=True, comment="全局大纲内容")
    global_outline_status = Column(String(20), default="pending",
                                   comment="全局大纲状态")
    global_outline_file_path = Column(String(255), nullable=True,
                                      comment="全局大纲文件路径")

    unit_summaries = Column(JSON, nullable=True, comment="单元简要概述")
    unit_summaries_status = Column(String(20), default="pending",
                                   comment="单元概述状态")

    episode_outlines = Column(JSON, nullable=True, comment="分集详细大纲")
    chapter_outlines = Column(JSON, nullable=True, comment="章节详细大纲")
    scene_outlines = Column(JSON, nullable=True, comment="场景详细大纲")

    status = Column(Enum(ProjectStatus), default=ProjectStatus.INIT,
                    nullable=False, comment="项目状态")
    total_chapters = Column(Integer, default=0, comment="总章节数")
    completed_chapters = Column(Integer, default=0, comment="已完成章节数")
    current_chapter = Column(Integer, default=0, comment="当前生成章节")

    generation_config = Column(JSON, nullable=True, comment="生成配置")
    knowledge_base_config = Column(JSON, nullable=True, comment="知识库配置")

    novel_config = Column(JSON, nullable=True, comment="小说专属配置")
    series_script_config = Column(JSON, nullable=True, comment="剧集剧本专属配置")
    movie_script_config = Column(JSON, nullable=True, comment="电影剧本专属配置")

    project_code = Column(String(50), unique=True, nullable=True,
                          comment="项目代码")
    vectorstore_path = Column(String(255), nullable=True, comment="向量库路径")
    chapters_dir = Column(String(255), nullable=True, comment="章节文件目录")

    style_document_path = Column(String(255), nullable=True, comment="风格文档路径")
    style_document_name = Column(String(200), nullable=True, comment="风格文档名称")
    style_config = Column(JSON, nullable=True, comment="风格配置")

    project_kb_id = Column(Integer, nullable=True, comment="项目专属知识库ID")
    project_kb_collection = Column(String(100), nullable=True,
                                   comment="知识库集合名称")
    kb_status = Column(String(20), default="pending", comment="知识库状态")
    kb_graphrag_enabled = Column(Boolean, default=True, comment="是否启用GraphRAG")

    user = relationship("User", back_populates="novel_projects")
    chapters = relationship("NovelChapter", back_populates="project",
                            cascade="all, delete-orphan")

    def __repr__(self):
        return f"<NovelProject(id={self.id}, title='{self.title}')>"

    def get_progress_percentage(self) -> float:
        if self.total_chapters == 0:
            return 0.0
        return (self.completed_chapters / self.total_chapters) * 100
''')

# ==================== models/chapter.py ====================
write_file('app/models/chapter.py', '''
"""小说/剧本章节模型"""
from sqlalchemy import (
    Column, String, Integer, ForeignKey, Text, Enum, JSON
)
from sqlalchemy.orm import relationship
import enum

from app.models.base import BaseModel


class ChapterStatus(str, enum.Enum):
    PENDING = "pending"
    DRAFTING = "drafting"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    FAILED = "failed"


class NovelChapter(BaseModel):
    """小说/剧本章节表"""
    __tablename__ = "novel_chapters"

    project_id = Column(Integer, ForeignKey("novel_projects.id",
                        ondelete="CASCADE"), nullable=False, comment="项目ID")

    chapter_number = Column(Integer, nullable=False, comment="章节序号")
    chapter_title = Column(String(200), nullable=True, comment="章节标题")

    episode_number = Column(Integer, nullable=True, comment="集数（剧本专用）")
    scene_number = Column(Integer, nullable=True, comment="场景编号（剧本专用）")

    chapter_metadata = Column(JSON, nullable=True, comment="章节元数据")

    status = Column(Enum(ChapterStatus), default=ChapterStatus.PENDING,
                    nullable=False, comment="章节状态")
    draft_content = Column(Text, nullable=True, comment="草稿内容")
    final_content = Column(Text, nullable=True, comment="最终内容")

    content_file = Column(String(255), nullable=True, comment="章节文件路径")

    word_count = Column(Integer, default=0, comment="字数")
    token_count = Column(Integer, default=0, comment="Token消耗")
    duration_ms = Column(Integer, default=0, comment="生成耗时(毫秒)")

    error_message = Column(Text, nullable=True, comment="错误信息")

    user_edited = Column(Integer, default=0, comment="用户是否编辑过(0/1)")
    edit_history = Column(JSON, nullable=True, comment="编辑历史")

    project = relationship("NovelProject", back_populates="chapters")

    def __repr__(self):
        return f"<NovelChapter(id={self.id}, ch={self.chapter_number})>"

    def get_content_preview(self, max_length: int = 200) -> str:
        content = self.final_content or self.draft_content or ""
        if len(content) <= max_length:
            return content
        return content[:max_length] + "..."
''')

# ==================== models/__init__.py ====================
write_file('app/models/__init__.py', '''
"""数据库模型统一导出"""
from app.models.user import User
from app.models.project import NovelProject, ProjectType, ProjectStatus
from app.models.chapter import NovelChapter, ChapterStatus

__all__ = [
    "User", "NovelProject", "ProjectType", "ProjectStatus",
    "NovelChapter", "ChapterStatus",
]
''')

# ==================== domain/strategies/context_build_strategy.py ====================
write_file('app/domain/strategies/context_build_strategy.py', '''
"""上下文构建策略接口"""
from typing import Protocol, Dict, Any


class ContextBuildStrategy(Protocol):
    """上下文构建策略接口 - 各内容类型必须实现"""

    async def build_chapter_context(
        self, project: Any, chapter: Any, knowledge_context: str
    ) -> Dict[str, Any]:
        """构建章节/场景上下文"""
        ...

    async def build_previous_summary(
        self, project: Any, current_chapter_num: int
    ) -> str:
        """构建前文摘要"""
        ...

    async def build_character_state(
        self, project: Any, current_chapter_num: int
    ) -> str:
        """构建角色状态"""
        ...
''')

# ==================== domain/strategies/prompt_strategy.py ====================
write_file('app/domain/strategies/prompt_strategy.py', '''
"""提示词构建策略接口"""
from typing import Protocol, Dict, Any


class PromptBuildStrategy(Protocol):
    """提示词构建策略接口 - 各内容类型必须实现"""

    def build_chapter_prompt(
        self, chapter_number: int, chapter_title: str,
        chapter_metadata: Dict[str, Any], context: Dict[str, Any],
        generation_config: Dict[str, Any
    ) -> str:
        """构建章节/场景正文生成提示词"""
        ...

    def build_outline_prompt(
        self, outline_content: str, unit_count: int, content_type: str
    ) -> str:
        """构建大纲生成提示词"""
        ...
''')

# ==================== domain/strategies/outline_strategy.py ====================
write_file('app/domain/strategies/outline_strategy.py', '''
"""大纲生成策略接口"""
from typing import Protocol, Dict, Any


class OutlineGenerationStrategy(Protocol):
    """大纲生成策略接口 - 各内容类型必须实现"""

    async def generate_global_outline(
        self, project: Any, llm_provider: Any, temperature: float
    ) -> str:
        """生成全局大纲"""
        ...

    async def generate_unit_summaries(
        self, project: Any, global_outline: str, unit_count: int,
        llm_provider: Any, temperature: float
    ) -> Dict[str, Any]:
        """生成单元概述"""
        ...

    async def generate_detailed_outline(
        self, project: Any, unit_num: int, unit_data: Dict[str, Any],
        llm_provider: Any, temperature: float
    ) -> Dict[str, Any]:
        """生成详细大纲"""
        ...
''')

# ==================== domain/strategies/strategy_factory.py ====================
write_file('app/domain/strategies/strategy_factory.py', '''
"""策略工厂 - 通过注册表模式管理各类型的策略实现"""
from typing import Any


class StrategyFactory:
    """策略工厂注册表"""

    _context_builders: dict = {}
    _prompt_builders: dict = {}
    _outline_generators: dict = {}

    @classmethod
    def register_context_builder(cls, content_type: str, strategy: Any):
        cls._context_builders[content_type] = strategy

    @classmethod
    def register_prompt_builder(cls, content_type: str, strategy: Any):
        cls._prompt_builders[content_type] = strategy

    @classmethod
    def register_outline_generator(cls, content_type: str, strategy: Any):
        cls._outline_generators[content_type] = strategy

    @classmethod
    def get_context_builder(cls, content_type: str) -> Any:
        builder = cls._context_builders.get(content_type)
        if not builder:
            raise ValueError(f"未注册的上下文构建策略: {content_type}")
        return builder

    @classmethod
    def get_prompt_builder(cls, content_type: str) -> Any:
        builder = cls._prompt_builders.get(content_type)
        if not builder:
            raise ValueError(f"未注册的提示词构建策略: {content_type}")
        return builder

    @classmethod
    def get_outline_generator(cls, content_type: str) -> Any:
        generator = cls._outline_generators.get(content_type)
        if not generator:
            raise ValueError(f"未注册的大纲生成策略: {content_type}")
        return generator

    @classmethod
    def get_registered_types(cls) -> list:
        """获取所有已注册的内容类型"""
        return list(set(
            list(cls._context_builders.keys())
            + list(cls._prompt_builders.keys())
            + list(cls._outline_generators.keys())
        ))
''')

# ==================== domain/strategies/__init__.py ====================
write_file('app/domain/strategies/__init__.py', '''
"""策略模块统一导出"""
from app.domain.strategies.strategy_factory import StrategyFactory

__all__ = ["StrategyFactory"]
''')

# ==================== domain/repositories/project_repository.py ====================
write_file('app/domain/repositories/project_repository.py', '''
"""项目仓储接口"""
from typing import Protocol, Optional, List


class ProjectRepository(Protocol):
    """项目仓储接口 - 领域层定义，基础设施层实现"""

    async def find_by_id(self, project_id: int) -> Optional[Any]:
        ...

    async def find_by_user_id(self, user_id: int) -> List[Any]:
        ...

    async def save(self, project: Any) -> Any:
        ...

    async def delete(self, project_id: int) -> bool:
        ...

    async def update_status(self, project_id: int, status: str) -> bool:
        ...
''')

# ==================== domain/repositories/chapter_repository.py ====================
write_file('app/domain/repositories/chapter_repository.py', '''
"""章节仓储接口"""
from typing import Protocol, Optional, List


class ChapterRepository(Protocol):
    """章节仓储接口 - 领域层定义，基础设施层实现"""

    async def find_by_id(self, chapter_id: int) -> Optional[Any]:
        ...

    async def find_by_project_id(self, project_id: int) -> List[Any]:
        ...

    async def find_by_project_and_number(
        self, project_id: int, chapter_number: int
    ) -> Optional[Any]:
        ...

    async def save(self, chapter: Any) -> Any:
        ...

    async def delete(self, chapter_id: int) -> bool:
        ...
''')

# ==================== domain/models/project.py ====================
write_file('app/domain/models/project.py', '''
"""项目领域模型 - 充血模型"""
from app.domain.models.value_objects.content_type import ContentType
from app.domain.models.value_objects.project_status import ProjectStatus
from app.core.constants import ProjectConstants


class Project:
    """项目领域模型 - 业务逻辑封装在实体内部"""

    def __init__(
        self, id: int, title: str, content_type: ContentType,
        status: ProjectStatus, total_chapters: int = 0,
        completed_chapters: int = 0, user_id: int = 0,
        genre: str = "", target_platform: str = "",
    ):
        self._id = id
        self._title = title
        self._content_type = content_type
        self._status = status
        self._total_chapters = total_chapters
        self._completed_chapters = completed_chapters
        self._user_id = user_id
        self._genre = genre
        self._target_platform = target_platform

    @property
    def id(self) -> int:
        return self._id

    @property
    def title(self) -> str:
        return self._title

    @property
    def content_type(self) -> ContentType:
        return self._content_type

    @property
    def status(self) -> ProjectStatus:
        return self._status

    def start_generation(self) -> None:
        """开始生成 - 封装状态变更业务规则"""
        target = ProjectStatus(ProjectStatus.GENERATING)
        if not self._status.can_transition_to(target):
            raise BusinessError(
                error_code="PROJECT_001",
                message=f"项目状态为{self._status.label}，无法开始生成"
            )
        self._status = target

    def complete_chapter(self) -> None:
        """完成一个章节"""
        self._completed_chapters += 1
        if self._completed_chapters >= self._total_chapters:
            self._status = ProjectStatus(ProjectStatus.COMPLETED)

    def get_progress_percentage(self) -> float:
        """获取进度百分比"""
        if self._total_chapters == 0:
            return 0.0
        return (self._completed_chapters / self._total_chapters) * 100


class BusinessError(Exception):
    """业务异常基类"""

    def __init__(self, error_code: str, message: str):
        self.error_code = error_code
        self.message = message
        super().__init__(message)
''')

# ==================== main.py ====================
write_file('app/main.py', '''
"""Writer Master 应用入口"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import init_db, close_db
from app.core.logger import get_logger

logger = get_logger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info("Writer Master 启动中...")
    await init_db()
    logger.info("数据库初始化完成")
    yield
    await close_db()
    logger.info("Writer Master 已关闭")


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok", "app": settings.APP_NAME}


# 注册路由
from app.api.v1.router import api_router
app.include_router(api_router, prefix="/api/v1")
''')

# ==================== api/v1/router.py ====================
write_file('app/api/v1/router.py', '''
"""API路由注册"""
from fastapi import APIRouter

api_router = APIRouter()

# TODO: 注册各业务模块路由
# from app.api.v1.endpoints.projects import router as projects_router
# api_router.include_router(projects_router, prefix="/projects", tags=["项目管理"])
''')

print("\n=== Phase 1 Complete: Backend Core Files Created ===")
