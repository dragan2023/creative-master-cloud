"""
千问 (Qianwen) LLM 提供者
调用阿里云通义千问 API
支持多模态内容（qwen-vl模型）
"""
from typing import AsyncGenerator, Optional, Dict, List, Any
import dashscope
from dashscope import Generation
from dashscope import MultiModalConversation

from app.agents.base_provider import BaseLLMProvider, LLMResponse


# 千问支持视觉能力的模型
QIANWEN_VISION_MODELS = [
    "qwen-vl", "qwen-vl-plus", "qwen-vl-max",
    "qwen2-vl", "qwen2.5-vl", "qwen3-vl"
]


class QianwenProvider(BaseLLMProvider):
    """千问 LLM 提供者"""

    # 标记支持多模态
    supports_vision = True

    def __init__(
        self,
        api_key: str,
        model_name: str = "qwen-plus",
        api_base: Optional[str] = None,
        **kwargs
    ):
        # 通义千问使用dashscope SDK，不需要api_base，但接受参数以保持接口一致性
        super().__init__(api_key, model_name, api_base, **kwargs)
        dashscope.api_key = api_key

    def _supports_vision(self) -> bool:
        """检查当前模型是否支持视觉"""
        return any(vm in self.model_name.lower() for vm in QIANWEN_VISION_MODELS)

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        images: Optional[List[str]] = None,
        videos: Optional[List[str]] = None,
        files: Optional[List[str]] = None,
        **kwargs
    ) -> LLMResponse:
        """生成文本（支持多模态：文本、图片）"""

        # 如果有图片且模型支持视觉，使用多模态API（千问不支持视频）
        if images and self._supports_vision():
            return await self._generate_multimodal(prompt, images, system_prompt, temperature, max_tokens, **kwargs)

        # 否则使用普通文本生成
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        response = Generation.call(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            result_format='message',
            **kwargs
        )

        if response.status_code != 200:
            raise Exception(
                f"千问 API 调用失败: {response.code} - {response.message}")

        return LLMResponse(
            content=response.output.choices[0].message.content,
            model=self.model_name,
            provider="qianwen",
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.total_tokens
            } if response.usage else None,
            finish_reason=response.output.choices[0].finish_reason
        )

    async def _generate_multimodal(
        self,
        prompt: str,
        images: List[str],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> LLMResponse:
        """使用多模态API生成"""
        messages = []

        if system_prompt:
            messages.append(
                {"role": "system", "content": [{"text": system_prompt}]})

        # 构建多模态消息内容
        content = [{"text": prompt}]
        for img_url in images:
            content.append({"image": img_url})

        messages.append({"role": "user", "content": content})

        response = MultiModalConversation.call(
            model=self.model_name,
            messages=messages,
            top_k=kwargs.get('top_k', 50),
        )

        if response.status_code != 200:
            raise Exception(
                f"千问多模态 API 调用失败: {response.code} - {response.message}")

        return LLMResponse(
            content=response.output.choices[0].message.content[0].get(
                "text", ""),
            model=self.model_name,
            provider="qianwen",
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.total_tokens
            } if response.usage else None,
            finish_reason=response.output.choices[0].finish_reason if response.output.choices else None
        )

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        images: Optional[List[str]] = None,
        videos: Optional[List[str]] = None,
        files: Optional[List[str]] = None,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """流式生成文本（支持多模态：文本、图片）"""

        # 多模态暂不支持流式，降级为普通模式（千问不支持视频）
        if images and self._supports_vision():
            response = await self._generate_multimodal(prompt, images, system_prompt, temperature, max_tokens, **kwargs)
            yield response.content
            return

        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        responses = Generation.call(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            result_format='message',
            stream=True,
            incremental_output=True,  # 关键：启用增量输出模式
            **kwargs
        )

        for response in responses:
            if response.status_code == 200:
                content = response.output.choices[0].message.content
                if content:
                    yield content

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> LLMResponse:
        """多轮对话（支持多模态消息）"""
        response = Generation.call(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            result_format='message',
            **kwargs
        )

        if response.status_code != 200:
            raise Exception(
                f"千问 API 调用失败: {response.code} - {response.message}")

        return LLMResponse(
            content=response.output.choices[0].message.content,
            model=self.model_name,
            provider="qianwen",
            usage={
                "prompt_tokens": response.usage.input_tokens,
                "completion_tokens": response.usage.output_tokens,
                "total_tokens": response.usage.total_tokens
            } if response.usage else None,
            finish_reason=response.output.choices[0].finish_reason
        )

    async def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """流式多轮对话（支持多模态消息）"""
        responses = Generation.call(
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            result_format='message',
            stream=True,
            incremental_output=True,  # 关键：启用增量输出模式
            **kwargs
        )

        for response in responses:
            if response.status_code == 200:
                content = response.output.choices[0].message.content
                if content:
                    yield content
