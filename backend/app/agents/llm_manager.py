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
    # 2026年最新配置：只保留通义千问、豆包、硅基流动、OpenRouter、贞贞AI工坊
    PROVIDER_CLASSES = {
        # 通义千问（文本模型）
        "qianwen": QianwenProvider,
        "qianwen-image": OpenAIProvider,  # 图像生成模型使用OpenAI兼容接口
        # 豆包（火山引擎）
        "doubao": DoubaoProvider,
        "doubao-image": DoubaoProvider,  # 图像生成模型
        # 硅基流动
        "siliconflow": OpenAIProvider,
        # OpenRouter
        "openrouter": OpenAIProvider,
        "openrouter-image": OpenAIProvider,  # 图像生成模型
        # 贞贞AI工坊（OpenAI兼容）
        "t8star": OpenAIProvider,
        "t8star-image": OpenAIProvider,
        "t8star-video": OpenAIProvider,
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

        # 尝试解密 API Key
        try:
            decrypted_key = api_key_encryption.decrypt(
                api_key_config.encrypted_key)
        except Exception:
            # 解密失败（可能是 SECRET_KEY 变更），标记为无效并使用系统预置
            api_key_config.is_valid = False
            await db.commit()
            # 尝试使用系统预置 API Key
            return await self.get_system_provider(provider_name or api_key_config.provider)

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
            provider_name: 提供者名称（可选，默认使用 qianwen）

        Returns:
            LLM 提供者实例
        """
        settings = get_settings()
        provider_name = provider_name or "qianwen"

        # 获取系统预置 API Key
        api_key = getattr(
            settings, f"{provider_name.upper().replace('-', '_')}_API_KEY", None)

        if not api_key:
            raise ValueError(f"系统未配置 {provider_name} 的 API Key")

        return self.create_provider(provider_name, api_key)

    def get_preset_models(self) -> Dict[str, Any]:
        """获取所有预置模型信息"""
        return PRESET_MODELS

    def get_providers_by_type(self, model_type: str = "text") -> Dict[str, Any]:
        """
        按类型获取提供商配置

        Args:
            model_type: 模型类型 (text/image/video)

        Returns:
            符合类型的提供商配置
        """
        return {
            key: value for key, value in PRESET_MODELS.items()
            if any(m.get("type") == model_type for m in value.get("models", []))
        }


# 全局 LLM 管理器实例
llm_manager = LLMManager()


def get_llm_manager() -> LLMManager:
    """获取 LLM 管理器实例"""
    return llm_manager


# 为 LLMManager 添加 get_default_provider 方法（解决方法名不匹配问题）
def _get_default_provider(self, provider_name: str = "qianwen") -> BaseLLMProvider:
    """
    获取默认的 LLM 提供者（同步版本，用于无数据库会话的场景）

    Args:
        provider_name: 提供者名称（默认使用 qianwen）

    Returns:
        LLM 提供者实例

    Raises:
        ValueError: 如果系统未配置该提供者的 API Key
    """
    settings = get_settings()

    # 获取系统预置 API Key
    api_key = getattr(
        settings, f"{provider_name.upper().replace('-', '_')}_API_KEY", None)

    if not api_key:
        raise ValueError(f"系统未配置 {provider_name} 的 API Key")

    return self.create_provider(provider_name, api_key)


# 动态添加方法到 LLMManager 类
LLMManager.get_default_provider = _get_default_provider
