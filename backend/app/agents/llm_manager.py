"""
LLM 管理器
统一管理 LLM 提供者的创建和调用

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import Optional, Dict, Any, AsyncGenerator, List
import logging
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
from app.models import UserAPIKey, SystemConfig

logger = logging.getLogger(__name__)


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
        # DeepSeek（官方）
        "deepseek": DeepSeekProvider,
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
        api_base: Optional[str] = None,
        reasoning_effort: Optional[str] = None,  # 思考强度
        enable_thinking: bool = False,  # 是否启用思考模式
        thinking_save_dir: Optional[str] = None,  # 思考过程保存目录
        **kwargs
    ) -> BaseLLMProvider:
        """
        创建 LLM 提供者实例

        Args:
            provider_name: 提供者名称
            api_key: API Key
            model_name: 模型名称
            api_base: API 基础地址
            reasoning_effort: 思考强度（high/max），仅DeepSeek V4系列支持
            enable_thinking: 是否启用思考模式
            thinking_save_dir: 思考过程保存目录

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

        # DeepSeek提供者支持思考模式参数
        if provider_name == "deepseek":
            return provider_class(
                api_key=api_key,
                model_name=model_name,
                api_base=api_base,
                reasoning_effort=reasoning_effort,
                enable_thinking=enable_thinking,
                thinking_save_dir=thinking_save_dir,
                **kwargs
            )
        else:
            return provider_class(
                api_key=api_key,
                model_name=model_name,
                api_base=api_base,
                **kwargs
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

        query = query.limit(1)
        result = await db.execute(query)
        api_key_config = result.scalar_one_or_none()

        if not api_key_config:
            # 如果用户没有配置，使用系统预置 API Key
            return await self.get_system_provider(provider_name)

        # 尝试解密 API Key
        try:
            decrypted_key = api_key_encryption.decrypt(
                api_key_config.encrypted_key)
        except Exception as e:
            # 解密失败（可能是 SECRET_KEY 变更），标记为无效并使用系统预置
            logger.warning(f"API Key解密失败，将使用系统预置: {e!r}")
            api_key_config.is_valid = False
            await db.commit()
            # 尝试使用系统预置 API Key
            return await self.get_system_provider(provider_name or api_key_config.provider)

        # 读取思考模式配置（优先用户级，回退系统级）
        thinking_kwargs = {}
        if api_key_config.provider == "deepseek":
            thinking_kwargs = await self._get_thinking_config(db, user_id, api_key_config.provider)

        return self.create_provider(
            provider_name=api_key_config.provider,
            api_key=decrypted_key,
            model_name=api_key_config.model_name,
            api_base=api_key_config.api_base,
            **thinking_kwargs
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

        # API Key 名称映射（provider_name -> 配置中的环境变量名）
        # 处理别名映射，因为配置中的名称可能与 provider_name 不同
        api_key_aliases = {
            "qianwen": "DASHSCOPE_API_KEY",  # 通义千问使用 DASHSCOPE_API_KEY
            "qianwen_image": "DASHSCOPE_API_KEY",
            "doubao": "ARK_API_KEY",  # 豆包使用 ARK_API_KEY
            "doubao_image": "ARK_API_KEY",
            "siliconflow": "SILICONFLOW_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "t8star": "T8STAR_API_KEY",
            "t8star_image": "T8STAR_API_KEY",
            "t8star_video": "T8STAR_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "google": "GOOGLE_API_KEY",
            "openai": "OPENAI_API_KEY",
        }

        # 获取系统预置 API Key
        env_key_name = api_key_aliases.get(provider_name)
        if env_key_name:
            # 使用映射的名称
            api_key = getattr(settings, env_key_name, None)
        else:
            # 回退到默认命名规则
            api_key = getattr(
                settings, f"{provider_name.upper().replace('-', '_')}_API_KEY", None)

        if not api_key:
            # 尝试遍历所有可能的 API Key 作为最后的回退
            fallback_keys = ["DASHSCOPE_API_KEY", "T8STAR_API_KEY", "ARK_API_KEY",
                             "SILICONFLOW_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY"]
            for key in fallback_keys:
                api_key = getattr(settings, key, None)
                if api_key:
                    logger.info(f"使用回退 API Key: {key}")
                    break

        if not api_key:
            raise ValueError(
                f"系统未配置 {provider_name} 的 API Key，请在 .env 文件中配置 DASHSCOPE_API_KEY、"
                f"T8STAR_API_KEY、ARK_API_KEY 或其他 LLM 服务的 API Key"
            )

        # 读取思考模式配置（系统级设置）
        settings = get_settings()
        thinking_kwargs = {}
        if provider_name == "deepseek":
            thinking_kwargs = {
                "enable_thinking": settings.DEEPSEEK_ENABLE_THINKING,
                "reasoning_effort": settings.DEEPSEEK_REASONING_EFFORT,
                "thinking_save_dir": settings.DEEPSEEK_THINKING_SAVE_DIR,
            }

        return self.create_provider(provider_name, api_key, **thinking_kwargs)

    def get_preset_models(self) -> Dict[str, Any]:
        """获取所有预置模型信息"""
        return PRESET_MODELS

    async def _get_thinking_config(
        self,
        db: AsyncSession,
        user_id: int,
        provider_name: str
    ) -> dict:
        """
        获取思考模式配置（优先用户级DB配置，回退系统级环境变量）

        Args:
            db: 数据库会话
            user_id: 用户ID
            provider_name: 提供者名称

        Returns:
            思考模式配置字典
        """
        settings = get_settings()
        result = {
            "enable_thinking": settings.DEEPSEEK_ENABLE_THINKING,
            "reasoning_effort": settings.DEEPSEEK_REASONING_EFFORT,
            "thinking_save_dir": settings.DEEPSEEK_THINKING_SAVE_DIR,
        }

        # 尝试从DB读取用户级配置覆盖
        try:
            import json
            config_key = f"user_thinking_mode_config_{user_id}"
            stmt = select(SystemConfig).where(SystemConfig.id == config_key)
            db_result = await db.execute(stmt)
            config = db_result.scalar_one_or_none()
            if config and config.config_value:
                data = json.loads(config.config_value)
                result["enable_thinking"] = data.get("enable_thinking", result["enable_thinking"])
                result["reasoning_effort"] = data.get("reasoning_effort", result["reasoning_effort"])
                result["thinking_save_dir"] = data.get("thinking_save_dir", result["thinking_save_dir"])
        except Exception as e:
            logger.warning(f"读取用户思考模式配置失败，使用系统默认: {e}")

        return result

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

    # API Key 名称映射（provider_name -> 配置中的环境变量名）
    api_key_aliases = {
        "qianwen": "DASHSCOPE_API_KEY",
        "qianwen_image": "DASHSCOPE_API_KEY",
        "doubao": "ARK_API_KEY",
        "doubao_image": "ARK_API_KEY",
        "siliconflow": "SILICONFLOW_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
        "t8star": "T8STAR_API_KEY",
        "t8star_image": "T8STAR_API_KEY",
        "t8star_video": "T8STAR_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "google": "GOOGLE_API_KEY",
        "openai": "OPENAI_API_KEY",
    }

    # 获取系统预置 API Key
    env_key_name = api_key_aliases.get(provider_name)
    if env_key_name:
        api_key = getattr(settings, env_key_name, None)
    else:
        api_key = getattr(
            settings, f"{provider_name.upper().replace('-', '_')}_API_KEY", None)

    if not api_key:
        # 尝试遍历所有可能的 API Key 作为最后的回退
        fallback_keys = ["DASHSCOPE_API_KEY", "T8STAR_API_KEY", "ARK_API_KEY",
                         "SILICONFLOW_API_KEY", "DEEPSEEK_API_KEY", "OPENAI_API_KEY"]
        for key in fallback_keys:
            api_key = getattr(settings, key, None)
            if api_key:
                break

    if not api_key:
        raise ValueError(
            f"系统未配置 {provider_name} 的 API Key，请在 .env 文件中配置 DASHSCOPE_API_KEY、"
            f"T8STAR_API_KEY、ARK_API_KEY 或其他 LLM 服务的 API Key"
        )

    # 读取思考模式配置（系统级设置）
    settings = get_settings()
    thinking_kwargs = {}
    if provider_name == "deepseek":
        thinking_kwargs = {
            "enable_thinking": settings.DEEPSEEK_ENABLE_THINKING,
            "reasoning_effort": settings.DEEPSEEK_REASONING_EFFORT,
            "thinking_save_dir": settings.DEEPSEEK_THINKING_SAVE_DIR,
        }

    return self.create_provider(provider_name, api_key, **thinking_kwargs)


# 动态添加方法到 LLMManager 类
LLMManager.get_default_provider = _get_default_provider
