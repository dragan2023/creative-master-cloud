"""
Google Gemini LLM 提供者
调用 Google Generative AI API
原生支持多模态内容（文本、图片、视频）
"""
from typing import AsyncGenerator, Optional, Dict, List, Any
from google import genai
from google.genai import types
import os

from app.agents.base_provider import BaseLLMProvider, LLMResponse
from app.core.config import get_settings


class GoogleProvider(BaseLLMProvider):
    """Google Gemini LLM 提供者"""

    # 标记支持多模态
    supports_vision = True

    def __init__(
        self,
        api_key: str,
        model_name: str = "gemini-pro",
        api_base: Optional[str] = None,
        **kwargs
    ):
        # Google使用自己的SDK，不需要api_base，但接受参数以保持接口一致性
        super().__init__(api_key, model_name, api_base, **kwargs)
        self._client: Optional[genai.Client] = None

        # 设置代理
        settings = get_settings()
        if settings.HTTPS_PROXY:
            os.environ["HTTPS_PROXY"] = settings.HTTPS_PROXY
        if settings.HTTP_PROXY:
            os.environ["HTTP_PROXY"] = settings.HTTP_PROXY

    @property
    def client(self) -> genai.Client:
        """获取 Gemini 客户端（延迟初始化）"""
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    def _build_multimodal_content(
        self,
        text: str,
        images: Optional[List[str]] = None,
        files: Optional[List[str]] = None
    ) -> List[types.Part]:
        """
        构建多模态内容

        Args:
            text: 文本内容
            images: 图片URL列表
            files: 文件URL列表

        Returns:
            Part对象列表
        """
        parts = [types.Part(text=text)]

        # 添加图片
        if images:
            for img_url in images:
                if img_url.startswith("data:image"):
                    # Base64格式
                    # 解析base64数据
                    import base64
                    from urllib.parse import urlparse
                    parsed = urlparse(img_url)
                    media_type = "image/png"
                    if "image/jpeg" in img_url:
                        media_type = "image/jpeg"
                    elif "image/gif" in img_url:
                        media_type = "image/gif"
                    elif "image/webp" in img_url:
                        media_type = "image/webp"

                    # 提取base64数据
                    base64_data = img_url.split(
                        ",")[1] if "," in img_url else img_url
                    image_data = base64.b64decode(base64_data)

                    parts.append(types.Part(
                        inline_data=types.Blob(
                            mime_type=media_type,
                            data=image_data
                        )
                    ))
                else:
                    # URL格式 - Gemini需要下载后处理
                    parts.append(types.Part(
                        file_data=types.FileData(
                            file_uri=img_url,
                            mime_type="image/png"  # 默认，实际应根据URL判断
                        )
                    ))

        return parts

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
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        if system_prompt:
            config.system_instruction = system_prompt

        # 构建多模态内容
        if images or files:
            contents = self._build_multimodal_content(prompt, images, files)
        else:
            contents = prompt

        response = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=config
        )

        return LLMResponse(
            content=response.text,
            model=self.model_name,
            provider="google",
            usage=None,
            finish_reason=str(
                response.candidates[0].finish_reason) if response.candidates else None
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
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        if system_prompt:
            config.system_instruction = system_prompt

        # 构建多模态内容
        if images or files:
            contents = self._build_multimodal_content(prompt, images, files)
        else:
            contents = prompt

        async for chunk in await self.client.aio.models.generate_content_stream(
            model=self.model_name,
            contents=contents,
            config=config
        ):
            if chunk.text:
                yield chunk.text

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> LLMResponse:
        """多轮对话（支持多模态消息）"""
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        # 构建对话内容
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            content = msg.get("content", "")

            # 处理多模态内容
            if isinstance(content, list):
                parts = []
                for item in content:
                    if item.get("type") == "text":
                        parts.append(types.Part(text=item.get("text", "")))
                    elif item.get("type") == "image_url":
                        img_url = item.get("image_url", {}).get("url", "")
                        parts.append(types.Part(
                            file_data=types.FileData(file_uri=img_url)
                        ))
                contents.append(types.Content(role=role, parts=parts))
            else:
                contents.append(types.Content(role=role, parts=[
                                types.Part(text=str(content))]))

        response = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=contents,
            config=config
        )

        return LLMResponse(
            content=response.text,
            model=self.model_name,
            provider="google",
            usage=None,
            finish_reason=str(
                response.candidates[0].finish_reason) if response.candidates else None
        )

    async def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 4096,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """流式多轮对话（支持多模态消息）"""
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            content = msg.get("content", "")

            if isinstance(content, list):
                parts = []
                for item in content:
                    if item.get("type") == "text":
                        parts.append(types.Part(text=item.get("text", "")))
                    elif item.get("type") == "image_url":
                        img_url = item.get("image_url", {}).get("url", "")
                        parts.append(types.Part(
                            file_data=types.FileData(file_uri=img_url)
                        ))
                contents.append(types.Content(role=role, parts=parts))
            else:
                contents.append(types.Content(role=role, parts=[
                                types.Part(text=str(content))]))

        async for chunk in await self.client.aio.models.generate_content_stream(
            model=self.model_name,
            contents=contents,
            config=config
        ):
            if chunk.text:
                yield chunk.text
