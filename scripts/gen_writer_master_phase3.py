"""生成 writer_master 补充文件"""
import os

BASE = r'F:\python_project\writer_master\backend'


def write_file(rel_path, content):
    full_path = os.path.join(BASE, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content.strip() + '\n')
    print(f'  Created: {rel_path}')


# ==================== core/preset_models.py ====================
write_file('app/core/preset_models.py', '''
"""预置模型配置 - 所有LLM服务商的默认配置"""

PRESET_MODELS = {
    "qianwen": {
        "name": "通义千问",
        "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "default_model": "qwen-max",
        "models": ["qwen-max", "qwen-plus", "qwen-turbo", "qwen-long"],
    },
    "doubao": {
        "name": "豆包",
        "api_base": "https://ark.cn-beijing.volces.com/api/v3",
        "default_model": "doubao-pro-4k",
        "models": ["doubao-pro-4k", "doubao-pro-32k", "doubao-lite-4k"],
    },
    "siliconflow": {
        "name": "硅基流动",
        "api_base": "https://api.siliconflow.cn/v1",
        "default_model": "Qwen/Qwen2.5-72B-Instruct",
        "models": ["Qwen/Qwen2.5-72B-Instruct"],
    },
    "openrouter": {
        "name": "OpenRouter",
        "api_base": "https://openrouter.ai/api/v1",
        "default_model": "openai/gpt-4o",
        "models": ["openai/gpt-4o"],
    },
    "t8star": {
        "name": "贞贞AI工坊",
        "api_base": "https://ai.t8star.cn/v1",
        "default_model": "gpt-4o",
        "models": ["gpt-4o"],
    },
}
''')

# ==================== Update config.py to import PRESET_MODELS ====================
config_path = os.path.join(BASE, 'app/core/config.py')
with open(config_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Add PRESET_MODELS import after existing imports
if 'PRESET_MODELS' not in content:
    content = content.replace(
        'class Settings(BaseSettings):',
        'from app.core.preset_models import PRESET_MODELS\n\n\nclass Settings(BaseSettings):'
    )
    # Add PRESET_MODELS property
    content = content.replace(
        'def get_cors_origins(self) -> list:',
        '@property\n    def PRESET_MODELS(self) -> dict:\n        """预置模型配置"""\n        from app.core.preset_models import PRESET_MODELS as _PM\n        return _PM\n\n    def get_cors_origins(self) -> list:'
    )
    with open(config_path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('  Updated: app/core/config.py (added PRESET_MODELS)')

# ==================== models/api_key.py ====================
write_file('app/models/api_key.py', '''
"""API Key模型"""
from sqlalchemy import Column, String, Integer, ForeignKey, Boolean, Text
from app.models.base import BaseModel


class UserAPIKey(BaseModel):
    """用户API Key表"""
    __tablename__ = "user_api_keys"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, comment="用户ID")
    provider = Column(String(50), nullable=False, comment="服务商名称")
    encrypted_key = Column(Text, nullable=False, comment="加密后的API Key")
    api_base = Column(String(255), nullable=True, comment="API基础地址")
    model_name = Column(String(100), nullable=True, comment="默认模型名称")
    is_default = Column(Boolean, default=False, comment="是否默认")
    is_valid = Column(Boolean, default=True, comment="是否有效")
    channel = Column(String(50), default="default", comment="渠道分组")

    def __repr__(self):
        return f"<UserAPIKey(id={self.id}, provider='{self.provider}')>"
''')

# ==================== models/writing_model_config.py ====================
write_file('app/models/writing_model_config.py', '''
"""写作模型配置"""
from sqlalchemy import Column, String, Integer, ForeignKey, Boolean, JSON, Text
from app.models.base import BaseModel


class WritingModelConfig(BaseModel):
    """写作模型配置表"""
    __tablename__ = "writing_model_configs"

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"),
                     nullable=False, comment="用户ID")
    name = Column(String(100), nullable=False, comment="配置名称")
    provider = Column(String(50), nullable=False, comment="服务商")
    model_id = Column(String(100), nullable=False, comment="模型ID")
    api_base = Column(String(255), nullable=True, comment="API地址")
    api_key_id = Column(Integer, nullable=True, comment="关联的API Key ID")
    temperature = Column(Integer, default=70, comment="温度(0-100)")
    max_tokens = Column(Integer, default=4096, comment="最大Token数")
    is_default = Column(Boolean, default=False, comment="是否默认配置")
    config_data = Column(JSON, nullable=True, comment="完整配置JSON")

    def __repr__(self):
        return f"<WritingModelConfig(id={self.id}, name='{self.name}')>"
''')

# ==================== Update models/__init__.py ====================
write_file('app/models/__init__.py', '''
"""数据库模型统一导出"""
from app.models.user import User
from app.models.project import NovelProject, ProjectType, ProjectStatus
from app.models.chapter import NovelChapter, ChapterStatus
from app.models.api_key import UserAPIKey
from app.models.writing_model_config import WritingModelConfig

__all__ = [
    "User", "NovelProject", "ProjectType", "ProjectStatus",
    "NovelChapter", "ChapterStatus", "UserAPIKey", "WritingModelConfig",
]
''')

# ==================== domain/services/outline_service.py ====================
write_file('app/domain/services/outline_service.py', '''
"""大纲生成服务 - 领域服务"""
from typing import Optional, Dict, Any
from app.core.constants import OutlineConstants, TokenConstants
from app.domain.strategies.strategy_factory import StrategyFactory
from app.core.logger import get_logger

logger = get_logger("outline_service")


class OutlineService:
    """大纲生成领域服务"""

    async def generate_global_outline(
        self, project: Any, llm_provider: Any,
        temperature: float = 0.7
    ) -> str:
        """生成全局大纲"""
        content_type = project.content_type
        strategy = StrategyFactory.get_outline_generator(content_type)
        result = await strategy.generate_global_outline(
            project, llm_provider, temperature
        )
        return result

    async def generate_unit_summaries(
        self, project: Any, global_outline: str, unit_count: int,
        llm_provider: Any, temperature: float = 0.7
    ) -> Dict[str, Any]:
        """生成单元概述"""
        content_type = project.content_type
        strategy = StrategyFactory.get_outline_generator(content_type)
        result = await strategy.generate_unit_summaries(
            project, global_outline, unit_count, llm_provider, temperature
        )
        return result

    async def generate_detailed_outline(
        self, project: Any, unit_num: int, unit_data: Dict[str, Any],
        llm_provider: Any, temperature: float = 0.7
    ) -> Dict[str, Any]:
        """生成详细大纲（章节/集/场景）"""
        content_type = project.content_type
        strategy = StrategyFactory.get_outline_generator(content_type)
        result = await strategy.generate_detailed_outline(
            project, unit_num, unit_data, llm_provider, temperature
        )
        return result
''')

# ==================== domain/services/chapter_service.py ====================
write_file('app/domain/services/chapter_service.py', '''
"""章节生成服务 - 领域服务"""
from typing import Optional, Dict, Any
from app.core.constants import GenerationConstants, TokenConstants
from app.domain.strategies.strategy_factory import StrategyFactory
from app.core.logger import get_logger

logger = get_logger("chapter_service")


class ChapterGenerationService:
    """章节生成领域服务"""

    async def generate_chapter(
        self, project: Any, chapter: Any, knowledge_context: str,
        llm_provider: Any, temperature: float = 0.7,
        max_tokens: Optional[int] = None
    ) -> str:
        """生成章节正文"""
        content_type = project.content_type

        # 构建上下文
        context_strategy = StrategyFactory.get_context_builder(content_type)
        context = await context_strategy.build_chapter_context(
            project, chapter, knowledge_context
        )

        # 构建提示词
        prompt_strategy = StrategyFactory.get_prompt_builder(content_type)
        prompt = prompt_strategy.build_chapter_prompt(
            chapter_number=chapter.chapter_number,
            chapter_title=chapter.chapter_title or "",
            chapter_metadata=chapter.chapter_metadata or {},
            context=context,
            generation_config=project.generation_config or {}
        )

        # 调用LLM
        effective_max_tokens = max_tokens or TokenConstants.CHAPTER_CONTENT_MAX_TOKENS
        response = await llm_provider.generate(
            prompt=prompt,
            temperature=temperature,
            max_tokens=effective_max_tokens
        )

        return response.content
''')

# ==================== domain/services/__init__.py ====================
write_file('app/domain/services/__init__.py', '''
"""领域服务模块"""
from app.domain.services.outline_service import OutlineService
from app.domain.services.chapter_service import ChapterGenerationService

__all__ = ["OutlineService", "ChapterGenerationService"]
''')

# ==================== domain/models/__init__.py ====================
write_file('app/domain/models/__init__.py', '''
"""领域模型模块"""
from app.domain.models.value_objects import (
    ContentType, ProjectStatus, WordsPerChapter, QualityScore
)
from app.domain.models.project import Project, BusinessError

__all__ = [
    "ContentType", "ProjectStatus", "WordsPerChapter", "QualityScore",
    "Project", "BusinessError",
]
''')

# ==================== domain/repositories/__init__.py ====================
write_file('app/domain/repositories/__init__.py', '''
"""仓储接口模块"""
from app.domain.repositories.project_repository import ProjectRepository
from app.domain.repositories.chapter_repository import ChapterRepository

__all__ = ["ProjectRepository", "ChapterRepository"]
''')

# ==================== domain/__init__.py ====================
write_file('app/domain/__init__.py', '')
write_file('app/domain/models/value_objects/__init__.py', '')

# ==================== api/__init__.py ====================
write_file('app/api/__init__.py', '')
write_file('app/api/v1/__init__.py', '')
write_file('app/api/v1/endpoints/__init__.py', '')

# ==================== .env ====================
write_file('.env', '''
APP_NAME=Writer Master
DEBUG=True
HOST=0.0.0.0
PORT=8000
DATABASE_URL=sqlite+aiosqlite:///./data/writer_master.db
SECRET_KEY=dev-secret-key-change-in-production
LOG_LEVEL=INFO
LOG_DIR=./logs
CHROMA_PERSIST_DIR=./data/chroma
UPLOAD_DIR=./data/uploads
KNOWLEDGE_GRAPH_DIR=./data/knowledge_graphs
REDIS_URL=memory://
BATCH_REQUEST_INTERVAL=2.0
BATCH_RETRY_ON_RATE_LIMIT=true
BATCH_MAX_RETRIES=3
BATCH_RETRY_BASE_DELAY=2.0
''')

print("\n=== Phase 3 Complete: Supplementary Files ===")
