"""
DeepSeek LLM 提供者
使用 OpenAI 兼容接口调用 DeepSeek API
支持多模态内容（DeepSeek-VL模型）
"""
from typing import AsyncGenerator, Optional, Dict, List, Any, Union
from openai import AsyncOpenAI

from app.agents.base_provider import BaseLLMProvider, LLMResponse


# DeepSeek支持视觉的模型
DEEPSEEK_VISION_MODELS = [
    "deepseek-vl", "deepseek-vl2"
]


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
        max_tokens: int = 4096,
        images: Optional[List[str]] = None,
        files: Optional[List[str]] = None,
        **kwargs
    ) -> LLMResponse:
        """生成文本（支持多模态）"""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

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
        max_tokens: int = 4096,
        images: Optional[List[str]] = None,
        files: Optional[List[str]] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """流式生成文本（支持多模态）"""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

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
