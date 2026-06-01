"""
OpenAI LLM 提供者
调用 OpenAI GPT 系列 API
支持多模态内容（文本、图片）

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import AsyncGenerator, Optional, Dict, List, Any, Union
from openai import AsyncOpenAI
from openai import (
    APIConnectionError, RateLimitError, APIStatusError,
    InternalServerError, APITimeoutError
)
import urllib.parse

from app.agents.base_provider import BaseLLMProvider, LLMResponse
from app.core.config import get_settings
import logging

logger = logging.getLogger(__name__)


# 支持视觉能力的模型列表
OPENAI_VISION_MODELS = [
    "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4-vision",
    "gpt-5.2", "gpt-5.2-pro", "gpt-5-mini"
]

# OpenAI 模型最大输出 token 映射（也适用于 OpenRouter 和其他兼容平台）
OPENAI_MAX_OUTPUT_TOKENS = {
    # OpenAI GPT 系列
    "gpt-5.2-pro": 32768,
    "gpt-5.2-thinking": 16384,
    "gpt-5.2": 16384,
    "gpt-5-mini": 16384,
    "gpt-4o": 16384,
    "gpt-4o-mini": 16384,
    "gpt-4-turbo": 4096,
    "gpt-4": 4096,
    "gpt-3.5-turbo": 4096,
    # Google Gemini（通过 OpenRouter）
    "gemini-3.1-pro-preview": 65536,
    "gemini-3.1-pro": 65536,
    "gemini-2.5-pro": 65536,
    "gemini-2.0-flash": 8192,
    # Anthropic Claude（通过 OpenRouter）
    "claude-opus-4-5-20251101": 16384,
    "claude-sonnet-4": 16384,
    "claude-3-opus": 4096,
    "claude-3-sonnet": 4096,
    # 其他模型
    "glm-5": 8192,
}


class OpenAIProvider(BaseLLMProvider):
    """OpenAI LLM 提供者"""

    # 标记支持多模态
    supports_vision = True

    def __init__(
        self,
        api_key: str,
        model_name: str = "gpt-3.5-turbo",
        api_base: Optional[str] = "https://api.openai.com/v1",
        **kwargs
    ):
        super().__init__(api_key, model_name, api_base, **kwargs)
        self._client: Optional[AsyncOpenAI] = None
        self._is_openrouter = api_base and "openrouter.ai" in api_base

    @property
    def client(self) -> AsyncOpenAI:
        """获取 OpenAI 客户端（延迟初始化）"""
        if self._client is None:
            client_kwargs = {"api_key": self.api_key}
            if self.api_base:
                client_kwargs["base_url"] = self.api_base

            # OpenRouter 需要额外的请求头
            if self._is_openrouter:
                settings = get_settings()
                # 对 APP_NAME 进行 URL 编码以支持中文字符
                app_name = settings.APP_NAME
                try:
                    # 尝试编码为 ASCII，如果失败则进行 URL 编码
                    app_name.encode('ascii')
                except UnicodeEncodeError:
                    # 中文名称进行 URL 编码
                    app_name = urllib.parse.quote(app_name)

                client_kwargs["default_headers"] = {
                    "HTTP-Referer": settings.APP_BASE_URL,
                    "X-Title": app_name
                }

            self._client = AsyncOpenAI(**client_kwargs)
        return self._client

    def get_max_output_tokens(self) -> int:
        """
        获取当前模型支持的最大输出 token 数

        Returns:
            最大输出 token 数
        """
        model_lower = self.model_name.lower()
        # 去除可能的前缀（如 openrouter 上的 "openai/" 或 "google/"）
        model_id = model_lower.split(
            "/")[-1] if "/" in model_lower else model_lower

        # 精确匹配
        if model_id in OPENAI_MAX_OUTPUT_TOKENS:
            return OPENAI_MAX_OUTPUT_TOKENS[model_id]
        # 模糊匹配
        for key, value in OPENAI_MAX_OUTPUT_TOKENS.items():
            if key in model_id or model_id in key:
                return value
        # 默认值
        return self.DEFAULT_MAX_OUTPUT_TOKENS

    def _supports_vision(self) -> bool:
        """检查当前模型是否支持视觉"""
        return any(vm in self.model_name.lower() for vm in OPENAI_VISION_MODELS)

    def _build_content(
        self,
        text: str,
        images: Optional[List[str]] = None
    ) -> Union[str, List[Dict[str, Any]]]:
        """
        构建消息内容

        Args:
            text: 文本内容
            images: 图片URL列表

        Returns:
            如果没有图片或模型不支持视觉，返回纯文本
            否则返回多模态内容数组
        """
        if not images or not self._supports_vision():
            return text

        content = [{"type": "text", "text": text}]

        for img_url in images:
            content.append({
                "type": "image_url",
                "image_url": {"url": img_url}
            })

        return content

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 30000,
        images: Optional[List[str]] = None,
        videos: Optional[List[str]] = None,
        files: Optional[List[str]] = None,
        module_name: str = "unknown",
        **kwargs
    ) -> LLMResponse:
        """生成文本（支持多模态：文本、图片）"""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 构建多模态内容（OpenAI 不支持视频，忽略 videos 参数）
        user_content = self._build_content(prompt, images)
        messages.append({"role": "user", "content": user_content})

        # 弹出 module_name 避免透传到 OpenAI SDK
        kwargs.pop("module_name", None)

        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )

        return LLMResponse(
            content=response.choices[0].message.content,
            model=response.model,
            provider="openai",
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            } if response.usage else None,
            finish_reason=response.choices[0].finish_reason
        )

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 30000,
        images: Optional[List[str]] = None,
        videos: Optional[List[str]] = None,
        files: Optional[List[str]] = None,
        module_name: str = "unknown",
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """流式生成文本（支持多模态：文本、图片）"""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 构建多模态内容（OpenAI 不支持视频，忽略 videos 参数）
        user_content = self._build_content(prompt, images)
        messages.append({"role": "user", "content": user_content})

        # 弹出 module_name 避免透传到 OpenAI SDK
        kwargs.pop("module_name", None)

        try:
            stream = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **kwargs
            )

            async for chunk in stream:
                try:
                    # 安全检查：确保 choices 列表不为空且 delta 存在
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if delta and hasattr(delta, 'content') and delta.content:
                            yield delta.content
                except (AttributeError, IndexError, TypeError) as e:
                    # 记录异常但不中断流式生成
                    logger.warning(f"OpenAI流式生成chunk解析异常: {e}")
                    continue

        except APIConnectionError as e:
            logger.error(f"OpenAI API连接错误: {e}")
            raise ConnectionError(f"无法连接到OpenAI API服务: {str(e)}")
        except RateLimitError as e:
            logger.error(f"OpenAI API速率限制: {e}")
            raise RuntimeError(f"OpenAI API请求频率超限，请稍后重试: {str(e)}")
        except APITimeoutError as e:
            logger.error(f"OpenAI API超时: {e}")
            raise TimeoutError(f"OpenAI API请求超时: {str(e)}")
        except InternalServerError as e:
            logger.error(f"OpenAI服务器内部错误: {e}")
            raise RuntimeError(f"OpenAI服务器内部错误: {str(e)}")
        except APIStatusError as e:
            logger.error(f"OpenAI API状态错误 [{e.status_code}]: {e.message}")
            raise RuntimeError(f"OpenAI API错误 [{e.status_code}]: {e.message}")
        except Exception as e:
            logger.exception(f"OpenAI流式生成未知异常: {e}")
            raise

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 30000,
        **kwargs
    ) -> LLMResponse:
        """多轮对话（支持多模态消息）"""
        response = await self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )

        return LLMResponse(
            content=response.choices[0].message.content,
            model=response.model,
            provider="openai",
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            } if response.usage else None,
            finish_reason=response.choices[0].finish_reason
        )

    async def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 30000,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """流式多轮对话（支持多模态消息）"""
        try:
            stream = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True,
                **kwargs
            )

            async for chunk in stream:
                try:
                    # 安全检查：确保 choices 列表不为空且 delta 存在
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        if delta and hasattr(delta, 'content') and delta.content:
                            yield delta.content
                except (AttributeError, IndexError, TypeError) as e:
                    # 记录异常但不中断流式生成
                    logger.warning(f"OpenAI chat_stream chunk解析异常: {e}")
                    continue

        except APIConnectionError as e:
            logger.error(f"OpenAI chat_stream API连接错误: {e}")
            raise ConnectionError(f"无法连接到OpenAI API服务: {str(e)}")
        except RateLimitError as e:
            logger.error(f"OpenAI chat_stream API速率限制: {e}")
            raise RuntimeError(f"OpenAI API请求频率超限，请稍后重试: {str(e)}")
        except APITimeoutError as e:
            logger.error(f"OpenAI chat_stream API超时: {e}")
            raise TimeoutError(f"OpenAI API请求超时: {str(e)}")
        except InternalServerError as e:
            logger.error(f"OpenAI chat_stream 服务器内部错误: {e}")
            raise RuntimeError(f"OpenAI服务器内部错误: {str(e)}")
        except APIStatusError as e:
            logger.error(
                f"OpenAI chat_stream API状态错误 [{e.status_code}]: {e.message}")
            raise RuntimeError(f"OpenAI API错误 [{e.status_code}]: {e.message}")
        except Exception as e:
            logger.exception(f"OpenAI chat_stream 未知异常: {e}")
            raise

    async def close(self) -> None:
        """
        关闭 OpenAI 客户端，释放资源

        正确清理 AsyncOpenAI 内部的 httpx 客户端，避免事件循环关闭后的资源泄漏
        """
        if self._client is not None:
            try:
                await self._client.close()
            except Exception as e:
                logger.debug(f"关闭 OpenAI 客户端时出错: {e}")
            finally:
                self._client = None
