"""生成 writer_master 后端 Phase2: 基础设施层 + API层 + Schemas"""
import os

BASE = r'F:\python_project\writer_master\backend'


def write_file(rel_path, content):
    full_path = os.path.join(BASE, rel_path)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(content.strip() + '\n')
    print(f'  Created: {rel_path}')


# ==================== core/exceptions.py ====================
write_file('app/core/exceptions.py', '''
"""统一异常定义模块"""
import uuid
from typing import Optional, Dict, Any
from enum import Enum
from fastapi import HTTPException


class ErrorCode(str, Enum):
    """错误代码枚举"""
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    AUTH_TOKEN_INVALID = "AUTH_TOKEN_INVALID"
    AUTH_UNAUTHORIZED = "AUTH_UNAUTHORIZED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RESOURCE_ALREADY_EXISTS = "RESOURCE_ALREADY_EXISTS"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    GENERATION_FAILED = "GENERATION_FAILED"
    LLM_SERVICE_ERROR = "LLM_SERVICE_ERROR"
    KNOWLEDGE_BASE_ERROR = "KNOWLEDGE_BASE_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"


class AppException(Exception):
    """应用基础异常"""
    def __init__(
        self,
        error_code: ErrorCode,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None
    ):
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.trace_id = trace_id or str(uuid.uuid4())
        super().__init__(self.message)


class AuthenticationException(AppException):
    """认证异常(401)"""
    def __init__(self, error_code: ErrorCode = ErrorCode.AUTH_UNAUTHORIZED,
                 message: str = "认证失败", **kwargs):
        super().__init__(error_code=error_code, message=message,
                         status_code=401, **kwargs)


class ResourceNotFoundException(AppException):
    """资源未找到(404)"""
    def __init__(self, message: str = "资源不存在", **kwargs):
        super().__init__(error_code=ErrorCode.RESOURCE_NOT_FOUND,
                         message=message, status_code=404, **kwargs)


class ValidationException(AppException):
    """验证异常(400)"""
    def __init__(self, message: str = "参数验证失败", **kwargs):
        super().__init__(error_code=ErrorCode.VALIDATION_ERROR,
                         message=message, status_code=400, **kwargs)


class GenerationException(AppException):
    """生成异常(500)"""
    def __init__(self, message: str = "生成失败", **kwargs):
        super().__init__(error_code=ErrorCode.GENERATION_FAILED,
                         message=message, status_code=500, **kwargs)


class LLMServiceException(AppException):
    """LLM服务异常(502)"""
    def __init__(self, message: str = "LLM服务异常", **kwargs):
        super().__init__(error_code=ErrorCode.LLM_SERVICE_ERROR,
                         message=message, status_code=502, **kwargs)


def app_exception_handler(exc: AppException) -> dict:
    """统一异常响应格式"""
    return {
        "success": False,
        "code": exc.status_code,
        "message": exc.message,
        "error_code": exc.error_code.value,
        "trace_id": exc.trace_id,
        "details": exc.details
    }
''')

# ==================== core/security.py ====================
write_file('app/core/security.py', '''
"""安全模块 - 密码加密、JWT Token、API Key加密"""
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from passlib.context import CryptContext
import secrets
import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    """生成密码哈希"""
    return pwd_context.hash(password)


def create_access_token(
    subject: str | int,
    expires_delta: Optional[timedelta] = None,
    extra_data: Optional[dict] = None
) -> str:
    """创建JWT Token"""
    settings = get_settings()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )
    to_encode = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.utcnow()
    }
    if extra_data:
        to_encode.update(extra_data)
    return jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )


def decode_access_token(token: str) -> Optional[dict]:
    """解码并验证JWT Token"""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        return payload
    except JWTError:
        return None


def generate_api_key() -> str:
    """生成随机API Key"""
    return secrets.token_urlsafe(32)


class APIKeyEncryption:
    """API Key加密类 - 使用Fernet对称加密"""

    def __init__(self):
        self._fernet: Optional[Fernet] = None

    def _get_fernet(self) -> Fernet:
        if self._fernet is None:
            settings = get_settings()
            salt = settings.SECRET_KEY.encode()[:16]
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=480000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(
                settings.SECRET_KEY.encode()
            ))
            self._fernet = Fernet(key)
        return self._fernet

    def encrypt(self, plain_text: str) -> str:
        """加密"""
        return self._get_fernet().encrypt(plain_text.encode()).decode()

    def decrypt(self, cipher_text: str) -> str:
        """解密"""
        return self._get_fernet().decrypt(cipher_text.encode()).decode()


api_key_encryption = APIKeyEncryption()


def mask_api_key(api_key: str) -> str:
    """掩码显示API Key"""
    if not api_key or len(api_key) < 8:
        return "****"
    return api_key[:4] + "****" + api_key[-4:]
''')

# ==================== core/__init__.py ====================
write_file('app/core/__init__.py', '''
"""核心模块"""
''')

# ==================== infrastructure/ai/llm_manager.py ====================
write_file('app/infrastructure/ai/llm_manager.py', '''
"""LLM管理器 - 统一管理LLM提供者的创建和调用"""
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.config import get_settings
from app.core.constants import TokenConstants
from app.core.logger import get_logger
from app.core.security import api_key_encryption
from app.infrastructure.ai.base_provider import (
    BaseLLMProvider, LLMResponse
)
from app.infrastructure.ai.openai_provider import OpenAIProvider
from app.infrastructure.ai.qianwen_provider import QianwenProvider
from app.infrastructure.ai.doubao_provider import DoubaoProvider

logger = get_logger("llm_manager")
settings = get_settings()


class LLMManager:
    """LLM管理器"""

    PROVIDER_CLASSES: Dict[str, type] = {
        "qianwen": QianwenProvider,
        "doubao": DoubaoProvider,
        "siliconflow": OpenAIProvider,
        "openrouter": OpenAIProvider,
        "t8star": OpenAIProvider,
    }

    def __init__(self):
        self._instances: Dict[str, BaseLLMProvider] = {}

    def create_provider(
        self,
        provider_name: str,
        api_key: str,
        model_name: Optional[str] = None,
        api_base: Optional[str] = None
    ) -> BaseLLMProvider:
        """创建LLM提供者实例"""
        provider_name = provider_name.lower()

        if provider_name not in self.PROVIDER_CLASSES:
            raise ValueError(f"不支持的LLM提供者: {provider_name}")

        preset = settings.PRESET_MODELS.get(provider_name, {})

        if not model_name:
            model_name = preset.get("default_model", "")
        if not api_base:
            api_base = preset.get("api_base")

        provider_class = self.PROVIDER_CLASSES[provider_name]
        return provider_class(
            api_key=api_key,
            model_name=model_name,
            api_base=api_base
        )

    async def get_provider_from_db(
        self,
        db: AsyncSession,
        user_id: int,
        provider_name: Optional[str] = None
    ) -> BaseLLMProvider:
        """从数据库获取用户的LLM配置"""
        from app.models.api_key import UserAPIKey

        query = select(UserAPIKey).where(UserAPIKey.user_id == user_id)
        if provider_name:
            query = query.where(UserAPIKey.provider == provider_name)
        else:
            query = query.where(UserAPIKey.is_default == True)

        query = query.limit(1)
        result = await db.execute(query)
        api_key_record = result.scalar_one_or_none()

        if not api_key_record:
            raise ValueError("未找到API Key配置")

        decrypted_key = api_key_encryption.decrypt(
            api_key_record.encrypted_key
        )
        return self.create_provider(
            provider_name=api_key_record.provider,
            api_key=decrypted_key,
            model_name=None,
            api_base=api_key_record.api_base
        )


_llm_manager: Optional[LLMManager] = None


def get_llm_manager() -> LLMManager:
    """获取LLM管理器单例"""
    global _llm_manager
    if _llm_manager is None:
        _llm_manager = LLMManager()
    return _llm_manager
''')

# ==================== infrastructure/ai/base_provider.py ====================
write_file('app/infrastructure/ai/base_provider.py', '''
"""LLM提供者基类"""
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional, Dict, Any, List
from pydantic import BaseModel
from app.core.constants import TokenConstants


class LLMResponse(BaseModel):
    """LLM响应模型"""
    content: str
    model: str
    provider: str
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None


class BaseLLMProvider(ABC):
    """LLM提供者基类 - 定义统一调用接口"""

    supports_vision: bool = False
    DEFAULT_MAX_OUTPUT_TOKENS = TokenConstants.DEFAULT_MAX_TOKENS

    def __init__(
        self,
        api_key: str,
        model_name: str,
        api_base: Optional[str] = None,
        **kwargs
    ):
        self.api_key = api_key
        self.model_name = model_name
        self.api_base = api_base
        self.kwargs = kwargs

    def get_max_output_tokens(self) -> int:
        return self.DEFAULT_MAX_OUTPUT_TOKENS

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """生成文本"""
        ...

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """流式生成文本"""
        ...

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """多轮对话"""
        last_user_msg = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_msg = msg
                break

        if not last_user_msg:
            raise ValueError("消息列表中没有用户消息")

        content = last_user_msg.get("content", "")
        if isinstance(content, list):
            prompt = ""
            for item in content:
                if item.get("type") == "text":
                    prompt += item.get("text", "")
        else:
            prompt = str(content)

        system_prompt = None
        for msg in messages:
            if msg.get("role") == "system":
                system_prompt = msg.get("content", "")
                break

        return await self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
''')

# ==================== infrastructure/ai/openai_provider.py ====================
write_file('app/infrastructure/ai/openai_provider.py', '''
"""OpenAI兼容API提供者 - 支持所有OpenAI兼容的API"""
from typing import AsyncGenerator, Optional
from openai import AsyncOpenAI

from app.infrastructure.ai.base_provider import BaseLLMProvider, LLMResponse
from app.core.logger import get_logger

logger = get_logger("openai_provider")


class OpenAIProvider(BaseLLMProvider):
    """OpenAI兼容API提供者"""

    def __init__(self, api_key: str, model_name: str,
                 api_base: Optional[str] = None, **kwargs):
        super().__init__(api_key, model_name, api_base, **kwargs)
        self._client = AsyncOpenAI(
            api_key=api_key,
            base_url=api_base
        )

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        max_tokens = max_tokens or self.get_max_output_tokens()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = await self._client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )

        return LLMResponse(
            content=response.choices[0].message.content,
            model=response.model,
            provider="openai_compatible",
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            } if response.usage else None,
            finish_reason=response.choices[0].finish_reason
        )

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        max_tokens = max_tokens or self.get_max_output_tokens()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        stream = await self._client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            **kwargs
        )

        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
''')

# ==================== infrastructure/ai/qianwen_provider.py ====================
write_file('app/infrastructure/ai/qianwen_provider.py', '''
"""通义千问提供者 - 使用OpenAI兼容接口"""
from typing import Optional
from app.infrastructure.ai.openai_provider import OpenAIProvider
from app.core.config import get_settings

settings = get_settings()


class QianwenProvider(OpenAIProvider):
    """通义千问提供者 - 基于OpenAI兼容接口"""

    def __init__(self, api_key: str, model_name: str,
                 api_base: Optional[str] = None, **kwargs):
        preset = settings.PRESET_MODELS.get("qianwen", {})
        if not api_base:
            api_base = preset.get("api_base",
                                   "https://dashscope.aliyuncs.com/compatible-mode/v1")
        if not model_name:
            model_name = preset.get("default_model", "qwen-max")
        super().__init__(api_key, model_name, api_base, **kwargs)
''')

# ==================== infrastructure/ai/doubao_provider.py ====================
write_file('app/infrastructure/ai/doubao_provider.py', '''
"""豆包提供者 - 使用OpenAI兼容接口"""
from typing import Optional
from app.infrastructure.ai.openai_provider import OpenAIProvider
from app.core.config import get_settings

settings = get_settings()


class DoubaoProvider(OpenAIProvider):
    """豆包提供者 - 基于OpenAI兼容接口"""

    def __init__(self, api_key: str, model_name: str,
                 api_base: Optional[str] = None, **kwargs):
        preset = settings.PRESET_MODELS.get("doubao", {})
        if not api_base:
            api_base = preset.get("api_base",
                                   "https://ark.cn-beijing.volces.com/api/v3")
        if not model_name:
            model_name = preset.get("default_model", "doubao-pro-4k")
        super().__init__(api_key, model_name, api_base, **kwargs)
''')

# ==================== infrastructure/ai/__init__.py ====================
write_file('app/infrastructure/ai/__init__.py', '''
"""AI基础设施模块"""
from app.infrastructure.ai.llm_manager import get_llm_manager, LLMManager
from app.infrastructure.ai.base_provider import BaseLLMProvider, LLMResponse

__all__ = ["get_llm_manager", "LLMManager", "BaseLLMProvider", "LLMResponse"]
''')

# ==================== infrastructure/repositories/project_repository_impl.py ====================
write_file('app/infrastructure/repositories/project_repository_impl.py', '''
"""项目仓储实现"""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.project import NovelProject, ProjectStatus
from app.core.constants import ProjectConstants


class ProjectRepositoryImpl:
    """项目仓储实现"""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def find_by_id(self, project_id: int) -> Optional[NovelProject]:
        result = await self._db.execute(
            select(NovelProject).where(NovelProject.id == project_id)
        )
        return result.scalar_one_or_none()

    async def find_by_user_id(self, user_id: int) -> List[NovelProject]:
        result = await self._db.execute(
            select(NovelProject)
            .where(NovelProject.user_id == user_id)
            .order_by(NovelProject.updated_at.desc())
        )
        return list(result.scalars().all())

    async def find_by_project_code(
        self, project_code: str
    ) -> Optional[NovelProject]:
        result = await self._db.execute(
            select(NovelProject).where(
                NovelProject.project_code == project_code
            )
        )
        return result.scalar_one_or_none()

    async def save(self, project: NovelProject) -> NovelProject:
        self._db.add(project)
        await self._db.flush()
        await self._db.refresh(project)
        return project

    async def delete(self, project_id: int) -> bool:
        project = await self.find_by_id(project_id)
        if not project:
            return False
        await self._db.delete(project)
        await self._db.flush()
        return True

    async def update_status(
        self, project_id: int, status: str
    ) -> bool:
        project = await self.find_by_id(project_id)
        if not project:
            return False
        project.status = ProjectStatus(status)
        await self._db.flush()
        return True

    async def generate_project_code(self) -> str:
        """生成项目代码"""
        import time
        timestamp = int(time.time()) % 1000000
        return f"{ProjectConstants.PROJECT_CODE_PREFIX}{timestamp:06d}"
''')

# ==================== infrastructure/repositories/chapter_repository_impl.py ====================
write_file('app/infrastructure/repositories/chapter_repository_impl.py', '''
"""章节仓储实现"""
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models.chapter import NovelChapter, ChapterStatus


class ChapterRepositoryImpl:
    """章节仓储实现"""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def find_by_id(self, chapter_id: int) -> Optional[NovelChapter]:
        result = await self._db.execute(
            select(NovelChapter).where(NovelChapter.id == chapter_id)
        )
        return result.scalar_one_or_none()

    async def find_by_project_id(self, project_id: int) -> List[NovelChapter]:
        result = await self._db.execute(
            select(NovelChapter)
            .where(NovelChapter.project_id == project_id)
            .order_by(NovelChapter.chapter_number)
        )
        return list(result.scalars().all())

    async def find_by_project_and_number(
        self, project_id: int, chapter_number: int
    ) -> Optional[NovelChapter]:
        result = await self._db.execute(
            select(NovelChapter).where(
                and_(
                    NovelChapter.project_id == project_id,
                    NovelChapter.chapter_number == chapter_number
                )
            )
        )
        return result.scalar_one_or_none()

    async def save(self, chapter: NovelChapter) -> NovelChapter:
        self._db.add(chapter)
        await self._db.flush()
        await self._db.refresh(chapter)
        return chapter

    async def delete(self, chapter_id: int) -> bool:
        chapter = await self.find_by_id(chapter_id)
        if not chapter:
            return False
        await self._db.delete(chapter)
        await self._db.flush()
        return True

    async def count_completed(self, project_id: int) -> int:
        result = await self._db.execute(
            select(NovelChapter).where(
                and_(
                    NovelChapter.project_id == project_id,
                    NovelChapter.status == ChapterStatus.COMPLETED
                )
            )
        )
        return len(list(result.scalars().all()))
''')

# ==================== infrastructure/repositories/__init__.py ====================
write_file('app/infrastructure/repositories/__init__.py', '''
"""仓储实现模块"""
from app.infrastructure.repositories.project_repository_impl import (
    ProjectRepositoryImpl
)
from app.infrastructure.repositories.chapter_repository_impl import (
    ChapterRepositoryImpl
)

__all__ = ["ProjectRepositoryImpl", "ChapterRepositoryImpl"]
''')

# ==================== infrastructure/external/__init__.py ====================
write_file('app/infrastructure/external/__init__.py', '')
write_file('app/infrastructure/knowledge/__init__.py', '')
write_file('app/infrastructure/__init__.py', '')
write_file('app/infrastructure/ai/prompt_templates/__init__.py', '')

# ==================== schemas/common.py ====================
write_file('app/schemas/common.py', '''
"""通用响应模型"""
from typing import Optional, Any, Generic, TypeVar
from pydantic import BaseModel, Field

T = TypeVar("T")


class ResponseModel(BaseModel, Generic[T]):
    """统一响应模型"""
    success: bool = True
    code: int = 200
    message: str = "success"
    data: Optional[T] = None

    class Config:
        from_attributes = True


class PageModel(BaseModel):
    """分页模型"""
    items: list = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20
    total_pages: int = 0

    def calculate_total_pages(self):
        if self.page_size > 0:
            self.total_pages = (
                (self.total + self.page_size - 1) // self.page_size
            )
''')

# ==================== schemas/project.py ====================
write_file('app/schemas/project.py', '''
"""项目相关Schema"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ProjectCreate(BaseModel):
    """创建项目"""
    title: str = Field(..., max_length=200, description="项目标题")
    content_type: str = Field(
        ..., description="内容类型: novel/series_script/movie_script"
    )
    genre: Optional[str] = Field(None, max_length=50, description="类型标签")
    target_platform: Optional[str] = Field(
        None, max_length=50, description="目标平台"
    )
    outline_content: Optional[str] = Field(None, description="大纲内容")
    generation_config: Optional[Dict[str, Any]] = Field(
        None, description="生成配置"
    )
    novel_config: Optional[Dict[str, Any]] = Field(
        None, description="小说配置"
    )
    series_script_config: Optional[Dict[str, Any]] = Field(
        None, description="剧集剧本配置"
    )
    movie_script_config: Optional[Dict[str, Any]] = Field(
        None, description="电影剧本配置"
    )


class ProjectUpdate(BaseModel):
    """更新项目"""
    title: Optional[str] = Field(None, max_length=200)
    genre: Optional[str] = Field(None, max_length=50)
    target_platform: Optional[str] = Field(None, max_length=50)
    global_outline_content: Optional[str] = None
    unit_summaries: Optional[Dict[str, Any]] = None
    chapter_outlines: Optional[Dict[str, Any]] = None
    episode_outlines: Optional[Dict[str, Any]] = None
    scene_outlines: Optional[Dict[str, Any]] = None
    generation_config: Optional[Dict[str, Any]] = None
    style_config: Optional[Dict[str, Any]] = None


class ProjectResponse(BaseModel):
    """项目响应"""
    id: int
    title: str
    content_type: Optional[str] = None
    genre: Optional[str] = None
    target_platform: Optional[str] = None
    status: str = "init"
    total_chapters: int = 0
    completed_chapters: int = 0
    current_chapter: int = 0
    global_outline_content: Optional[str] = None
    global_outline_status: Optional[str] = None
    unit_summaries: Optional[Dict[str, Any]] = None
    chapter_outlines: Optional[Dict[str, Any]] = None
    project_code: Optional[str] = None
    generation_config: Optional[Dict[str, Any]] = None
    style_config: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProjectListResponse(BaseModel):
    """项目列表响应"""
    items: list[ProjectResponse] = Field(default_factory=list)
    total: int = 0
''')

# ==================== schemas/chapter.py ====================
write_file('app/schemas/chapter.py', '''
"""章节相关Schema"""
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime


class ChapterCreate(BaseModel):
    """创建章节"""
    chapter_number: int = Field(..., ge=1, description="章节序号")
    chapter_title: Optional[str] = Field(None, max_length=200)
    episode_number: Optional[int] = Field(None, description="集数(剧本)")
    scene_number: Optional[int] = Field(None, description="场景编号(剧本)")
    chapter_metadata: Optional[Dict[str, Any]] = None


class ChapterUpdate(BaseModel):
    """更新章节"""
    chapter_title: Optional[str] = Field(None, max_length=200)
    draft_content: Optional[str] = None
    final_content: Optional[str] = None
    status: Optional[str] = None


class ChapterResponse(BaseModel):
    """章节响应"""
    id: int
    project_id: int
    chapter_number: int
    chapter_title: Optional[str] = None
    episode_number: Optional[int] = None
    scene_number: Optional[int] = None
    status: str = "pending"
    word_count: int = 0
    draft_content: Optional[str] = None
    final_content: Optional[str] = None
    content_file: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True
''')

# ==================== schemas/auth.py ====================
write_file('app/schemas/auth.py', '''
"""认证相关Schema"""
from typing import Optional
from pydantic import BaseModel, Field, EmailStr


class UserLogin(BaseModel):
    """用户登录"""
    username: str = Field(..., description="用户名或邮箱")
    password: str = Field(..., min_length=6, description="密码")


class UserRegister(BaseModel):
    """用户注册"""
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., description="邮箱")
    password: str = Field(..., min_length=6, max_length=100)


class TokenResponse(BaseModel):
    """Token响应"""
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 0
    user: Optional[dict] = None
''')

# ==================== schemas/__init__.py ====================
write_file('app/schemas/__init__.py', '''
"""Schema模块统一导出"""
from app.schemas.common import ResponseModel, PageModel
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse
)
from app.schemas.chapter import (
    ChapterCreate, ChapterUpdate, ChapterResponse
)
from app.schemas.auth import UserLogin, UserRegister, TokenResponse

__all__ = [
    "ResponseModel", "PageModel",
    "ProjectCreate", "ProjectUpdate", "ProjectResponse", "ProjectListResponse",
    "ChapterCreate", "ChapterUpdate", "ChapterResponse",
    "UserLogin", "UserRegister", "TokenResponse",
]
''')

# ==================== api/deps.py ====================
write_file('app/api/deps.py', '''
"""API依赖注入"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import jwt

from app.core.database import get_db
from app.core.config import get_settings
from app.core.logger import get_logger
from app.core.security import decode_access_token
from app.models.user import User

security = HTTPBearer(auto_error=False)
settings = get_settings()
logger = get_logger("auth")

_default_user_id: Optional[int] = None


async def get_or_create_default_user(db: AsyncSession) -> User:
    """获取或创建默认用户（兼容无认证模式）"""
    global _default_user_id

    if _default_user_id:
        result = await db.execute(select(User).where(User.id == _default_user_id))
        user = result.scalar_one_or_none()
        if user and user.is_active:
            return user

    result = await db.execute(select(User).where(User.is_admin == True))
    user = result.scalar_one_or_none()

    if not user:
        from app.core.security import get_password_hash
        user = User(
            username="admin",
            email="admin@writer-master.local",
            hashed_password=get_password_hash("admin123"),
            is_active=True,
            is_admin=True
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)

    _default_user_id = user.id
    return user


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> User:
    """获取当前用户（支持JWT认证）"""
    if not credentials:
        return await get_or_create_default_user(db)

    payload = decode_access_token(credentials.credentials)
    if not payload:
        return await get_or_create_default_user(db)

    user_id = payload.get("sub")
    if user_id:
        try:
            user_id = int(user_id)
            result = await db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()
            if user and user.is_active:
                return user
        except (ValueError, Exception) as e:
            logger.warning(f"Token解析失败: {e}")

    return await get_or_create_default_user(db)
''')

# ==================== api/v1/endpoints/projects.py ====================
write_file('app/api/v1/endpoints/projects.py', '''
"""项目管理API端点"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logger import get_logger
from app.core.exceptions import ResourceNotFoundException, ValidationException
from app.api.deps import get_current_user
from app.models.user import User
from app.models.project import NovelProject, ProjectStatus, ProjectType
from app.schemas.common import ResponseModel
from app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, ProjectListResponse
)
from app.infrastructure.repositories.project_repository_impl import (
    ProjectRepositoryImpl
)

router = APIRouter()
logger = get_logger("projects")


def _project_to_response(project: NovelProject) -> ProjectResponse:
    """项目模型转响应模型"""
    return ProjectResponse(
        id=project.id,
        title=project.title,
        content_type=project.content_type,
        genre=project.genre,
        target_platform=project.target_platform,
        status=project.status.value if project.status else "init",
        total_chapters=project.total_chapters or 0,
        completed_chapters=project.completed_chapters or 0,
        current_chapter=project.current_chapter or 0,
        global_outline_content=project.global_outline_content,
        global_outline_status=project.global_outline_status,
        unit_summaries=project.unit_summaries,
        chapter_outlines=project.chapter_outlines,
        project_code=project.project_code,
        generation_config=project.generation_config,
        style_config=project.style_config,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


@router.get("", response_model=ResponseModel[ProjectListResponse])
async def list_projects(
    content_type: Optional[str] = Query(None, description="按内容类型筛选"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取项目列表"""
    repo = ProjectRepositoryImpl(db)
    projects = await repo.find_by_user_id(current_user.id)

    if content_type:
        projects = [p for p in projects if p.content_type == content_type]

    items = [_project_to_response(p) for p in projects]
    return ResponseModel(
        data=ProjectListResponse(items=items, total=len(items))
    )


@router.post("", response_model=ResponseModel[ProjectResponse])
async def create_project(
    data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建项目"""
    project_type = ProjectType.NOVEL
    if data.content_type in ("series_script", "movie_script"):
        project_type = ProjectType.SCRIPT

    project_code = await ProjectRepositoryImpl(db).generate_project_code()

    project = NovelProject(
        user_id=current_user.id,
        title=data.title,
        project_type=project_type,
        content_type=data.content_type,
        genre=data.genre,
        target_platform=data.target_platform,
        outline_content=data.outline_content,
        generation_config=data.generation_config,
        novel_config=data.novel_config,
        series_script_config=data.series_script_config,
        movie_script_config=data.movie_script_config,
        status=ProjectStatus.INIT,
        project_code=project_code,
    )

    repo = ProjectRepositoryImpl(db)
    project = await repo.save(project)
    return ResponseModel(data=_project_to_response(project))


@router.get("/{project_id}", response_model=ResponseModel[ProjectResponse])
async def get_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取项目详情"""
    repo = ProjectRepositoryImpl(db)
    project = await repo.find_by_id(project_id)
    if not project:
        raise ResourceNotFoundException(message="项目不存在")
    return ResponseModel(data=_project_to_response(project))


@router.put("/{project_id}", response_model=ResponseModel[ProjectResponse])
async def update_project(
    project_id: int,
    data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新项目"""
    repo = ProjectRepositoryImpl(db)
    project = await repo.find_by_id(project_id)
    if not project:
        raise ResourceNotFoundException(message="项目不存在")

    update_fields = data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        if hasattr(project, field) and value is not None:
            setattr(project, field, value)

    project = await repo.save(project)
    return ResponseModel(data=_project_to_response(project))


@router.delete("/{project_id}", response_model=ResponseModel)
async def delete_project(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除项目"""
    repo = ProjectRepositoryImpl(db)
    success = await repo.delete(project_id)
    if not success:
        raise ResourceNotFoundException(message="项目不存在")
    return ResponseModel(message="删除成功")
''')

# ==================== api/v1/endpoints/chapters.py ====================
write_file('app/api/v1/endpoints/chapters.py', '''
"""章节管理API端点"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.logger import get_logger
from app.core.exceptions import ResourceNotFoundException
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.common import ResponseModel
from app.schemas.chapter import ChapterCreate, ChapterUpdate, ChapterResponse
from app.infrastructure.repositories.chapter_repository_impl import (
    ChapterRepositoryImpl
)
from app.infrastructure.repositories.project_repository_impl import (
    ProjectRepositoryImpl
)

router = APIRouter()
logger = get_logger("chapters")


def _chapter_to_response(chapter) -> ChapterResponse:
    return ChapterResponse(
        id=chapter.id,
        project_id=chapter.project_id,
        chapter_number=chapter.chapter_number,
        chapter_title=chapter.chapter_title,
        episode_number=chapter.episode_number,
        scene_number=chapter.scene_number,
        status=chapter.status.value if chapter.status else "pending",
        word_count=chapter.word_count or 0,
        draft_content=chapter.draft_content,
        final_content=chapter.final_content,
        content_file=chapter.content_file,
        error_message=chapter.error_message,
        created_at=chapter.created_at,
        updated_at=chapter.updated_at,
    )


@router.get("/project/{project_id}", response_model=ResponseModel[list])
async def list_chapters(
    project_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取项目的章节列表"""
    repo = ChapterRepositoryImpl(db)
    chapters = await repo.find_by_project_id(project_id)
    items = [_chapter_to_response(c) for c in chapters]
    return ResponseModel(data=items)


@router.get("/{chapter_id}", response_model=ResponseModel[ChapterResponse])
async def get_chapter(
    chapter_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取章节详情"""
    repo = ChapterRepositoryImpl(db)
    chapter = await repo.find_by_id(chapter_id)
    if not chapter:
        raise ResourceNotFoundException(message="章节不存在")
    return ResponseModel(data=_chapter_to_response(chapter))


@router.post("/project/{project_id}", response_model=ResponseModel[ChapterResponse])
async def create_chapter(
    project_id: int,
    data: ChapterCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """创建章节"""
    from app.models.chapter import NovelChapter, ChapterStatus

    chapter = NovelChapter(
        project_id=project_id,
        chapter_number=data.chapter_number,
        chapter_title=data.chapter_title,
        episode_number=data.episode_number,
        scene_number=data.scene_number,
        chapter_metadata=data.chapter_metadata,
        status=ChapterStatus.PENDING,
    )

    repo = ChapterRepositoryImpl(db)
    chapter = await repo.save(chapter)
    return ResponseModel(data=_chapter_to_response(chapter))


@router.put("/{chapter_id}", response_model=ResponseModel[ChapterResponse])
async def update_chapter(
    chapter_id: int,
    data: ChapterUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """更新章节"""
    repo = ChapterRepositoryImpl(db)
    chapter = await repo.find_by_id(chapter_id)
    if not chapter:
        raise ResourceNotFoundException(message="章节不存在")

    update_fields = data.model_dump(exclude_unset=True)
    for field, value in update_fields.items():
        if hasattr(chapter, field) and value is not None:
            setattr(chapter, field, value)

    chapter = await repo.save(chapter)
    return ResponseModel(data=_chapter_to_response(chapter))
''')

# ==================== api/v1/endpoints/auth.py ====================
write_file('app/api/v1/endpoints/auth.py', '''
"""认证API端点"""
from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.core.database import get_db
from app.core.config import get_settings
from app.core.security import (
    get_password_hash, verify_password, create_access_token
)
from app.core.logger import get_logger
from app.core.exceptions import AuthenticationException, ValidationException
from app.models.user import User
from app.schemas.common import ResponseModel
from app.schemas.auth import UserLogin, UserRegister, TokenResponse

router = APIRouter()
logger = get_logger("auth")
settings = get_settings()


@router.post("/register", response_model=ResponseModel[TokenResponse])
async def register(
    data: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    """用户注册"""
    result = await db.execute(
        select(User).where(
            or_(User.username == data.username, User.email == data.email)
        )
    )
    if result.scalar_one_or_none():
        raise ValidationException(message="用户名或邮箱已被注册")

    user = User(
        username=data.username,
        email=data.email,
        hashed_password=get_password_hash(data.password),
        is_active=True,
        is_admin=False
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    access_token = create_access_token(subject=user.id)
    return ResponseModel(
        data=TokenResponse(
            access_token=access_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user={"id": user.id, "username": user.username, "email": user.email}
        )
    )


@router.post("/login", response_model=ResponseModel[TokenResponse])
async def login(
    data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    """用户登录"""
    result = await db.execute(
        select(User).where(
            or_(User.username == data.username, User.email == data.username)
        )
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        raise AuthenticationException(message="用户名或密码错误")

    if not user.is_active:
        raise AuthenticationException(message="用户已被禁用")

    access_token = create_access_token(subject=user.id)
    return ResponseModel(
        data=TokenResponse(
            access_token=access_token,
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user={"id": user.id, "username": user.username, "email": user.email}
        )
    )
''')

# ==================== Update api/v1/router.py ====================
write_file('app/api/v1/router.py', '''
"""API路由注册"""
from fastapi import APIRouter

api_router = APIRouter()

from app.api.v1.endpoints.auth import router as auth_router
from app.api.v1.endpoints.projects import router as projects_router
from app.api.v1.endpoints.chapters import router as chapters_router

api_router.include_router(auth_router, prefix="/auth", tags=["认证"])
api_router.include_router(projects_router, prefix="/projects", tags=["项目管理"])
api_router.include_router(chapters_router, prefix="/chapters", tags=["章节管理"])
''')

# ==================== alembic.ini ====================
write_file('alembic.ini', '''
[alembic]
script_location = alembic
sqlalchemy.url = sqlite+aiosqlite:///./data/writer_master.db

[loggers]
keys = root,sqlalchemy,alembic

[handlers]
keys = console

[formatters]
keys = generic

[logger_root]
level = WARN
handlers = console

[logger_sqlalchemy]
level = WARN
handlers =
qualname = sqlalchemy.engine

[logger_alembic]
level = INFO
handlers =
qualname = alembic

[handler_console]
class = StreamHandler
args = (sys.stderr,)
level = NOTSET
formatter = generic

[formatter_generic]
format = %(levelname)-5.5s [%(name)s] %(message)s
datefmt = %H:%M:%S
''')

# ==================== alembic/env.py ====================
write_file('alembic/env.py', '''
"""Alembic环境配置"""
from logging.config import fileConfig
from sqlalchemy import engine_from_config, pool
from alembic import context
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings
from app.core.database import Base
from app.models import User, NovelProject, NovelChapter

config = context.config
settings = get_settings()
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline():
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata,
        literal_binds=True, dialect_opts={"paramstyle": "named"}
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
''')

# ==================== alembic/versions/.gitkeep ====================
write_file('alembic/versions/.gitkeep', '')

# ==================== PRESET_MODELS addition to config.py ====================
# We need to add PRESET_MODELS to config.py
print("\n=== Phase 2 Complete: Infrastructure + API + Schemas ===")
