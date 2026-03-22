"""
DeepSeek LLM 提供者
使用 OpenAI 兼容接口调用 DeepSeek API
支持多模态内容（DeepSeek-VL模型）
"""
from typing import AsyncGenerator, Optional, Dict, List, Any, Union
from openai import AsyncOpenAI
from openai import (
    APIConnectionError, RateLimitError, APIStatusError,
    InternalServerError, APITimeoutError
)

from app.agents.base_provider import BaseLLMProvider, LLMResponse
import logging

logger = logging.getLogger(__name__)


# DeepSeek支持视觉的模型
DEEPSEEK_VISION_MODELS = [
    "deepseek-vl", "deepseek-vl2"
]

# DeepSeek模型最大输出 token 映射
DEEPSEEK_MAX_OUTPUT_TOKENS = {
    "deepseek-chat": 32768,
    "deepseek-coder": 32768,
    "deepseek-reasoner": 32768,
    "deepseek-v3": 32768,
    "deepseek-v3-2": 32768,
    "deepseek-ai/deepseek-v3.2": 32768,
}


class DeepSeekProvider(BaseLLMProvider):
    """DeepSeek LLM 提供者"""

    # 标记支持多模态
    supports_vision = True

    def __init__(
        self,
        api_key: str,
        model_name: str = "deepseek-chat",
        api_base: Optional[str] = "https://api.deepseek.com/v1",
        **kwargs
    ):
        super().__init__(api_key, model_name, api_base, **kwargs)
        self._client: Optional[AsyncOpenAI] = None

    @property
    def client(self) -> AsyncOpenAI:
        """获取 OpenAI 客户端（延迟初始化）"""
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.api_base
            )
        return self._client

    def get_max_output_tokens(self) -> int:
        """
        获取当前模型支持的最大输出 token 数

        Returns:
            最大输出 token 数
        """
        model_lower = self.model_name.lower()
        # 精确匹配
        if model_lower in DEEPSEEK_MAX_OUTPUT_TOKENS:
            return DEEPSEEK_MAX_OUTPUT_TOKENS[model_lower]
        # 模糊匹配
        for key, value in DEEPSEEK_MAX_OUTPUT_TOKENS.items():
            if key in model_lower or model_lower in key:
                return value
        # 默认值
        return self.DEFAULT_MAX_OUTPUT_TOKENS

    def _supports_vision(self) -> bool:
        """检查当前模型是否支持视觉"""
        return any(vm in self.model_name.lower() for vm in DEEPSEEK_VISION_MODELS)

    def _build_content(
        self,
        text: str,
        images: Optional[List[str]] = None
    ) -> Union[str, List[Dict[str, Any]]]:
        """构建消息内容（支持多模态）"""
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
        **kwargs
    ) -> LLMResponse:
        """生成文本（支持多模态：文本、图片）"""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # DeepSeek 不支持视频，忽略 videos 参数
        user_content = self._build_content(prompt, images)
        messages.append({"role": "user", "content": user_content})

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
            provider="deepseek",
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
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """流式生成文本（支持多模态：文本、图片）"""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # DeepSeek 不支持视频，忽略 videos 参数
        user_content = self._build_content(prompt, images)
        messages.append({"role": "user", "content": user_content})

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
                    logger.warning(f"DeepSeek流式生成chunk解析异常: {e}")
                    continue

        except APIConnectionError as e:
            logger.error(f"DeepSeek API连接错误: {e}")
            raise ConnectionError(f"无法连接到DeepSeek API服务: {str(e)}")
        except RateLimitError as e:
            logger.error(f"DeepSeek API速率限制: {e}")
            raise RuntimeError(f"DeepSeek API请求频率超限，请稍后重试: {str(e)}")
        except APITimeoutError as e:
            logger.error(f"DeepSeek API超时: {e}")
            raise TimeoutError(f"DeepSeek API请求超时: {str(e)}")
        except InternalServerError as e:
            logger.error(f"DeepSeek服务器内部错误: {e}")
            raise RuntimeError(f"DeepSeek服务器内部错误: {str(e)}")
        except APIStatusError as e:
            logger.error(f"DeepSeek API状态错误 [{e.status_code}]: {e.message}")
            raise RuntimeError(
                f"DeepSeek API错误 [{e.status_code}]: {e.message}")
        except Exception as e:
            logger.exception(f"DeepSeek流式生成未知异常: {e}")
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
            provider="deepseek",
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
                    logger.warning(f"DeepSeek chat_stream chunk解析异常: {e}")
                    continue

        except APIConnectionError as e:
            logger.error(f"DeepSeek chat_stream API连接错误: {e}")
            raise ConnectionError(f"无法连接到DeepSeek API服务: {str(e)}")
        except RateLimitError as e:
            logger.error(f"DeepSeek chat_stream API速率限制: {e}")
            raise RuntimeError(f"DeepSeek API请求频率超限，请稍后重试: {str(e)}")
        except APITimeoutError as e:
            logger.error(f"DeepSeek chat_stream API超时: {e}")
            raise TimeoutError(f"DeepSeek API请求超时: {str(e)}")
        except InternalServerError as e:
            logger.error(f"DeepSeek chat_stream 服务器内部错误: {e}")
            raise RuntimeError(f"DeepSeek服务器内部错误: {str(e)}")
        except APIStatusError as e:
            logger.error(
                f"DeepSeek chat_stream API状态错误 [{e.status_code}]: {e.message}")
            raise RuntimeError(
                f"DeepSeek API错误 [{e.status_code}]: {e.message}")
        except Exception as e:
            logger.exception(f"DeepSeek chat_stream 未知异常: {e}")
            raise
