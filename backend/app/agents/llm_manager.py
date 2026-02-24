"""
LLM 管理器
统一管理 LLM 提供者的创建和调用
"""
from typing import Optional, Dict, Any, AsyncGenerator, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.agents.base_provider import BaseLLMProvider, LLMResponse, LLMProvider
from app.agents.deepseek_provider import DeepSeekProvider
from app.agents.openai_provider import OpenAIProvider
from app.agents.qianwen_provider import QianwenProvider
from app.agents.google_provider import GoogleProvider
from app.agents.doubao_provider import DoubaoProvider
from app.core.config import get_settings, PRESET_MODELS
from app.core.security import api_key_encryption
from app.models import UserAPIKey


class LLMManager:
    """LLM 管理器"""

    # 提供者映射（所有OpenAI兼容API都使用OpenAIProvider）
    PROVIDER_CLASSES = {
        "deepseek": DeepSeekProvider,
        "openai": OpenAIProvider,
        "qianwen": QianwenProvider,
        "google": GoogleProvider,
        "doubao": DoubaoProvider,
        # OpenAI兼容API服务商
        "zhipu": OpenAIProvider,
        "moonshot": OpenAIProvider,
        "baichuan": OpenAIProvider,
        "minimax": OpenAIProvider,
        "yi": OpenAIProvider,
        "siliconflow": OpenAIProvider,
        "modelscope": OpenAIProvider,
        "openrouter": OpenAIProvider,  # OpenRouter聚合平台
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
        """
        创建 LLM 提供者实例

        Args:
            provider_name: 提供者名称
            api_key: API Key
            model_name: 模型名称
            api_base: API 基础地址

        Returns:
            LLM 提供者实例
        """
        provider_name = provider_name.lower()

        if provider_name not in self.PROVIDER_CLASSES:
            raise ValueError(f"不支持的 LLM 提供者: {provider_name}")

        # 获取预置模型配置
        preset = PRESET_MODELS.get(provider_name, {})

        # 使用默认模型
        if not model_name:
            model_name = preset.get("default_model", "")

        # 使用默认 API Base
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
        """
        从数据库获取用户的 LLM 配置

        Args:
            db: 数据库会话
            user_id: 用户ID
            provider_name: 指定提供者（可选，默认使用用户的默认配置）

        Returns:
            LLM 提供者实例
        """
        # 查询用户的 API Key 配置
        query = select(UserAPIKey).where(UserAPIKey.user_id == user_id)

        if provider_name:
            query = query.where(UserAPIKey.provider == provider_name)
        else:
            query = query.where(UserAPIKey.is_default == True)

        result = await db.execute(query)
        api_key_config = result.scalar_one_or_none()

        if not api_key_config:
            # 如果用户没有配置，使用系统预置 API Key
            return await self.get_system_provider(provider_name)

        # 解密 API Key
        decrypted_key = api_key_encryption.decrypt(
            api_key_config.encrypted_key)

        return self.create_provider(
            provider_name=api_key_config.provider,
            api_key=decrypted_key,
            model_name=api_key_config.model_name,
            api_base=api_key_config.api_base
        )

    async def get_system_provider(
        self,
        provider_name: Optional[str] = None
    ) -> BaseLLMProvider:
        """
        获取系统预置的 LLM 提供者

        Args:
            provider_name: 提供者名称（可选，默认使用 DeepSeek）

        Returns:
            LLM 提供者实例
        """
        settings = get_settings()
        provider_name = provider_name or "deepseek"

        # 获取系统预置 API Key
        api_key = getattr(settings, f"{provider_name.upper()}_API_KEY", None)

        if not api_key:
            raise ValueError(f"系统未配置 {provider_name} 的 API Key")

        return self.create_provider(provider_name, api_key)

    def get_preset_models(self) -> Dict[str, Any]:
        """获取所有预置模型信息"""
        return PRESET_MODELS


# 全局 LLM 管理器实例
llm_manager = LLMManager()


def get_llm_manager() -> LLMManager:
    """获取 LLM 管理器实例"""
    return llm_manager
