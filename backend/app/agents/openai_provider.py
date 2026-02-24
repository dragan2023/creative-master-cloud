"""
OpenAI LLM 提供者
调用 OpenAI GPT 系列 API
支持多模态内容（文本、图片）
"""
from typing import AsyncGenerator, Optional, Dict, List, Any, Union
from openai import AsyncOpenAI

from app.agents.base_provider import BaseLLMProvider, LLMResponse
from app.core.config import get_settings


# 支持视觉能力的模型列表
OPENAI_VISION_MODELS = [
    "gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-4-vision",
    "gpt-5.2", "gpt-5.2-pro", "gpt-5-mini"
]


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
                client_kwargs["default_headers"] = {
                    "HTTP-Referer": settings.APP_BASE_URL,
                    "X-Title": settings.APP_NAME
                }

            self._client = AsyncOpenAI(**client_kwargs)
        return self._client

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
        max_tokens: int = 4096,
        images: Optional[List[str]] = None,
        files: Optional[List[str]] = None,
        **kwargs
    ) -> LLMResponse:
        """生成文本（支持多模态）"""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 构建多模态内容
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
        max_tokens: int = 4096,
        images: Optional[List[str]] = None,
        files: Optional[List[str]] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """流式生成文本（支持多模态）"""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # 构建多模态内容
        user_content = self._build_content(prompt, images)
        messages.append({"role": "user", "content": user_content})

        stream = await self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            **kwargs
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
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
        max_tokens: int = 4096,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """流式多轮对话（支持多模态消息）"""
        stream = await self.client.chat.completions.create(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            stream=True,
            **kwargs
        )

        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content
