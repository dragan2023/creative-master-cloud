"""
Agent基类 - LLM调用模块

包含 LLM调用相关的所有方法。

@date: 2026-04-24
@version: v1.0.0
"""
import asyncio
import time
from typing import Any, Dict, List, Optional

from app.core.logger import get_logger
from app.core.config import PRESET_MODELS, get_settings
from app.utils.llm_retry import should_retry, is_rate_limit_error, is_network_error, calculate_retry_delay
from app.agents.llm_manager import get_llm_manager
from app.agents.base_provider import BaseLLMProvider, LLMResponse
from ._types import AgentRole
from app.core.config import get_settings

logger = get_logger("agent.base.llm")


class AgentLLMMixin:
    """Agent LLM调用 Mixin"""

    def _get_llm_manager(self):
        """获取LLM管理器实例（懒加载）"""
        if self._llm_manager is None:
            self._llm_manager = get_llm_manager()
        return self._llm_manager

    def _resolve_model_config(self, model: Optional[str], temperature: Optional[float]) -> tuple:
        """解析模型配置，返回 (provider_name, model_id, temperature, max_tokens, api_base, api_key)"""
        config_api_base = None
        config_api_key = None

        if self.config:
            model_config = self.config.get_config(self.agent_role)
            config_model = model_config.model_id if model_config else None
            config_provider = model_config.provider if model_config else None
            config_temperature = model_config.temperature if model_config else None
            config_max_tokens = model_config.max_tokens if model_config else 32000
            config_api_base = model_config.api_base if model_config else None
            config_api_key = model_config.api_key if model_config else None
        else:
            config_model = None
            config_provider = None
            config_temperature = None
            config_max_tokens = 32000

        final_model = model or config_model
        final_temperature = temperature if temperature is not None else config_temperature
        final_max_tokens = config_max_tokens

        if not final_model:
            raise ValueError(
                f"Agent '{self.agent_role.value}' 未配置模型，请在写作工作台中为该Agent配置模型")

        provider_name = config_provider
        if not provider_name:
            provider_name = self._infer_provider_from_model(final_model)

        return provider_name, final_model, final_temperature, final_max_tokens, config_api_base, config_api_key

    def _infer_provider_from_model(self, model_id: str) -> str:
        """根据模型ID推断provider名称"""
        model_id_lower = model_id.lower()

        for provider_name, provider_config in PRESET_MODELS.items():
            models = provider_config.get("models", [])
            for model_info in models:
                if model_info.get("id", "").lower() == model_id_lower:
                    return provider_name
                if model_id_lower in model_info.get("id", "").lower():
                    return provider_name

        if "gpt" in model_id_lower or "claude" in model_id_lower or "glm" in model_id_lower:
            return "t8star"
        elif "deepseek" in model_id_lower:
            return "deepseek"
        elif "qwen" in model_id_lower:
            return "qianwen"
        elif "doubao" in model_id_lower:
            return "doubao"
        elif "gemini" in model_id_lower:
            return "openrouter"

        return "deepseek"

    async def _read_thinking_config(self, user_id: int = 0) -> dict:
        """读取DeepSeek思考模式配置

        优先级：用户级DB配置 > 系统级环境变量
        参照 llm_manager._get_thinking_config 的实现模式。

        Args:
            user_id: 用户ID，为0时仅读取环境变量配置

        Returns:
            包含 enable_thinking, reasoning_effort, thinking_save_dir 的字典
        """
        settings = get_settings()
        result = {
            "enable_thinking": settings.DEEPSEEK_ENABLE_THINKING,
            "reasoning_effort": settings.DEEPSEEK_REASONING_EFFORT,
            "thinking_save_dir": settings.DEEPSEEK_THINKING_SAVE_DIR,
        }

        # 如果有user_id，尝试从DB读取用户级配置覆盖
        if user_id > 0:
            try:
                import json
                from app.core.database import get_db
                from app.models.system_config import SystemConfig
                from sqlalchemy import select

                config_key = f"user_thinking_mode_config_{user_id}"
                async for session in get_db():
                    stmt = select(SystemConfig).where(SystemConfig.id == config_key)
                    db_result = await session.execute(stmt)
                    config = db_result.scalar_one_or_none()
                    if config and config.config_value:
                        data = json.loads(config.config_value)
                        result["enable_thinking"] = data.get("enable_thinking", result["enable_thinking"])
                        result["reasoning_effort"] = data.get("reasoning_effort", result["reasoning_effort"])
                        result["thinking_save_dir"] = data.get("thinking_save_dir", result["thinking_save_dir"])
                    break
            except Exception as e:
                logger.warning(f"读取用户思考模式配置失败，使用系统默认: {e}")

        return result

    async def _get_provider(self, provider_name: str, model_id: str,
                            api_base: Optional[str] = None, api_key: Optional[str] = None,
                            user_id: int = 0) -> BaseLLMProvider:
        """获取LLM Provider实例

        Args:
            provider_name: 提供者名称
            model_id: 模型ID
            api_base: 自定义API端点
            api_key: 自定义API密钥
            user_id: 用户ID（用于读取思考模式DB配置）
        """
        llm_manager = self._get_llm_manager()

        # 🔧 修复：读取思考模式配置（用户级DB > 系统级env）
        thinking_kwargs = {}
        if provider_name == "deepseek":
            thinking_kwargs = await self._read_thinking_config(user_id)
            if thinking_kwargs.get("enable_thinking"):
                logger.info(
                    f"思考模式已启用 - provider={provider_name}, "
                    f"effort={thinking_kwargs.get('reasoning_effort')}, "
                    f"save_dir={thinking_kwargs.get('thinking_save_dir')}")

        if api_key:
            final_api_base = api_base
            if not final_api_base:
                preset = PRESET_MODELS.get(provider_name, {})
                final_api_base = preset.get("api_base")
            self.logger.info(
                f"使用自定义API配置创建provider: provider={provider_name}, api_base={final_api_base}")
            return llm_manager.create_provider(
                provider_name=provider_name, api_key=api_key,
                model_name=model_id, api_base=final_api_base,
                **thinking_kwargs)

        if api_base:
            db_api_key = await self._get_api_key_from_db(provider_name)
            if db_api_key:
                self.logger.info(
                    f"使用自定义api_base + DB中的api_key: provider={provider_name}, api_base={api_base}")
                return llm_manager.create_provider(
                    provider_name=provider_name, api_key=db_api_key,
                    model_name=model_id, api_base=api_base,
                    **thinking_kwargs)

            settings = get_settings()
            env_key_name = f"{provider_name.upper().replace('-', '_')}_API_KEY"
            env_api_key = getattr(settings, env_key_name, None)
            if env_api_key:
                self.logger.info(
                    f"使用自定义api_base + 环境变量api_key: provider={provider_name}, api_base={api_base}")
                return llm_manager.create_provider(
                    provider_name=provider_name, api_key=env_api_key,
                    model_name=model_id, api_base=api_base,
                    **thinking_kwargs)
            raise ValueError(f"未配置 {provider_name} 的 API Key")

        try:
            provider = llm_manager.get_default_provider(provider_name)
            provider.model_name = model_id
            return provider
        except ValueError:
            settings = get_settings()
            preset = PRESET_MODELS.get(provider_name, {})
            env_key_name = f"{provider_name.upper().replace('-', '_')}_API_KEY"
            api_key = getattr(settings, env_key_name, None)
            if not api_key:
                db_api_key = await self._get_api_key_from_db(provider_name)
                if db_api_key:
                    api_key = db_api_key
                else:
                    raise ValueError(
                        f"未配置 {provider_name} 的 API Key，请在环境变量中设置")
            return llm_manager.create_provider(
                provider_name=provider_name, api_key=api_key,
                model_name=model_id, api_base=preset.get("api_base"),
                **thinking_kwargs)

    async def _get_api_key_from_db(self, provider_name: str) -> Optional[str]:
        """从数据库获取API Key"""
        try:
            from app.core.database import get_db
            from app.models.api_key import UserAPIKey
            from app.core.security import api_key_encryption
            from sqlalchemy import select
        
            async for session in get_db():
                stmt = select(UserAPIKey).where(
                    UserAPIKey.provider == provider_name,
                    UserAPIKey.is_valid == True
                ).order_by(UserAPIKey.created_at.desc()).limit(1)
                result = await session.execute(stmt)
                api_key_record = result.scalar_one_or_none()
                if api_key_record:
                    return api_key_encryption.decrypt(api_key_record.encrypted_key)
                break
        except Exception as e:
            self.logger.warning(f"从数据库获取API Key失败: provider={provider_name}, error={e}")
        return None

    async def call_llm(
        self, messages: List[Dict[str, str]],
        model: Optional[str] = None, temperature: Optional[float] = None,
        max_tokens: Optional[int] = None, task_id: Optional[str] = None,
        scene_id: Optional[str] = None, max_retries: int = 3,
        retry_delay: float = 5.0, user_id: int = 0
    ) -> Dict[str, Any]:
        """统一LLM调用接口（通过StatsInterceptor包装）

        Args:
            user_id: 用户ID，用于读取思考模式DB配置（默认0=仅使用环境变量）
        """
        if not self.requires_llm:
            raise RuntimeError(
                f"Agent '{self.agent_name}' (role={self.agent_role.value}) 不需要LLM调用。")

        start_time = time.time()
        retry_count = 0
        provider_name, model_id, resolved_temp, resolved_max_tokens, api_base, api_key = self._resolve_model_config(
            model, temperature)
        final_max_tokens = max_tokens or resolved_max_tokens

        self.logger.info(
            f"LLM调用开始 - Agent: {self.agent_name}, Model: {model_id}, "
            f"Provider: {provider_name}, Temperature: {resolved_temp}, MaxTokens: {final_max_tokens}")

        last_error = None
        for attempt in range(max_retries + 1):
            try:
                provider = await self._get_provider(provider_name, model_id, api_base, api_key, user_id)
                system_prompt = None
                user_prompt = ""
                for msg in messages:
                    if msg.get("role") == "system":
                        system_prompt = msg.get("content", "")
                    elif msg.get("role") == "user":
                        user_prompt = msg.get("content", "")

                response: LLMResponse = await provider.generate(
                    prompt=user_prompt, system_prompt=system_prompt,
                    temperature=resolved_temp, max_tokens=final_max_tokens)

                duration_sec = time.time() - start_time
                duration_ms = int(duration_sec * 1000)
                usage = response.usage or {}
                input_tokens = usage.get("prompt_tokens", 0)
                output_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", input_tokens + output_tokens)

                if self._stats_interceptor and task_id:
                    await self._stats_interceptor.record(
                        agent_name=self.agent_name, model_id=model_id,
                        input_tokens=input_tokens, output_tokens=output_tokens,
                        duration_sec=duration_sec, scene_id=scene_id)

                if retry_count > 0:
                    self.logger.info(
                        f"LLM调用成功（重连后） - Agent: {self.agent_name}, "
                        f"Tokens: {total_tokens}, 重试次数: {retry_count}")
                else:
                    self.logger.info(
                        f"LLM调用成功 - Agent: {self.agent_name}, "
                        f"Tokens: {total_tokens} (in: {input_tokens}, out: {output_tokens})")

                return {
                    "content": response.content,
                    "input_tokens": input_tokens, "output_tokens": output_tokens,
                    "total_tokens": total_tokens, "model": response.model,
                    "provider": response.provider, "duration_ms": duration_ms,
                    "retries": retry_count}

            except Exception as e:
                last_error = e
                error_type = type(e).__name__
                error_msg = str(e)[:200]

                if should_retry(e) and attempt < max_retries:
                    delay = calculate_retry_delay(attempt, retry_delay, max_delay=60.0, strategy="exponential")
                    if is_rate_limit_error(e):
                        error_desc = "API限流(429)"
                    elif is_network_error(e):
                        error_desc = "网络断联"
                    else:
                        error_desc = "临时故障"
                    retry_count += 1
                    self.logger.warning(
                        f"LLM调用失败({error_desc})，{delay:.1f}秒后重试... "
                        f"(尝试 {attempt + 1}/{max_retries + 1}): {error_type}: {error_msg}")
                    await asyncio.sleep(delay)
                    continue
                else:
                    duration_ms = int((time.time() - start_time) * 1000)
                    self.logger.error(
                        f"LLM调用失败 - Agent: {self.agent_name}, "
                        f"Error: {error_type}: {error_msg}, Duration: {duration_ms}ms, 重试次数: {retry_count}")
                    raise

        if last_error:
            raise last_error
        raise RuntimeError("LLM调用失败：未知错误")

    async def call_llm_stream(
        self, messages: List[Dict[str, str]],
        model: Optional[str] = None, temperature: Optional[float] = None,
        max_tokens: Optional[int] = None, task_id: Optional[str] = None,
        scene_id: Optional[str] = None, max_retries: int = 3,
        retry_delay: float = 5.0, user_id: int = 0
    ):
        """统一LLM流式调用接口

        Args:
            user_id: 用户ID，用于读取思考模式DB配置（默认0=仅使用环境变量）
        """
        if not self.requires_llm:
            raise RuntimeError(
                f"Agent '{self.agent_name}' (role={self.agent_role.value}) 不需要LLM流式调用。")

        start_time = time.time()
        content_chunks = []
        retry_count = 0
        last_error = None

        provider_name, model_id, resolved_temp, resolved_max_tokens, api_base, api_key = self._resolve_model_config(
            model, temperature)
        final_max_tokens = max_tokens or resolved_max_tokens

        self.logger.info(
            f"LLM流式调用开始 - Agent: {self.agent_name}, Model: {model_id}, "
            f"Provider: {provider_name}")

        for attempt in range(max_retries + 1):
            try:
                provider = await self._get_provider(provider_name, model_id, api_base, api_key, user_id)
                system_prompt = None
                user_prompt = ""
                for msg in messages:
                    if msg.get("role") == "system":
                        system_prompt = msg.get("content", "")
                    elif msg.get("role") == "user":
                        user_prompt = msg.get("content", "")

                async for chunk in provider.generate_stream(
                    prompt=user_prompt, system_prompt=system_prompt,
                    temperature=resolved_temp, max_tokens=final_max_tokens
                ):
                    content_chunks.append(chunk)
                    yield chunk

                duration_sec = time.time() - start_time
                full_content = "".join(content_chunks)
                estimated_output_tokens = len(full_content) // 2

                if self._stats_interceptor and task_id:
                    await self._stats_interceptor.record(
                        agent_name=self.agent_name, model_id=model_id,
                        input_tokens=0, output_tokens=estimated_output_tokens,
                        duration_sec=duration_sec, scene_id=scene_id)

                if retry_count > 0:
                    self.logger.info(
                        f"LLM流式调用成功（重连后） - Agent: {self.agent_name}, "
                        f"重试次数: {retry_count}")
                else:
                    self.logger.info(
                        f"LLM流式调用完成 - Agent: {self.agent_name}, "
                        f"Est. Tokens: {estimated_output_tokens}")
                return

            except Exception as e:
                last_error = e
                error_type = type(e).__name__
                error_msg = str(e)[:200]

                if should_retry(e) and attempt < max_retries:
                    delay = calculate_retry_delay(attempt, retry_delay, max_delay=60.0, strategy="exponential")
                    if is_rate_limit_error(e):
                        error_desc = "API限流(429)"
                    elif is_network_error(e):
                        error_desc = "网络断联"
                    else:
                        error_desc = "临时故障"
                    retry_count += 1
                    self.logger.warning(
                        f"LLM流式调用失败({error_desc})，{delay:.1f}秒后重试... "
                        f"(尝试 {attempt + 1}/{max_retries + 1}): {error_type}: {error_msg}")
                    await asyncio.sleep(delay)
                    continue
                else:
                    self.logger.error(
                        f"LLM流式调用失败 - Agent: {self.agent_name}, "
                        f"Error: {error_type}: {error_msg}, 重试次数: {retry_count}")
                    raise

        if last_error:
            raise last_error
