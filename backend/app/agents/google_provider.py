"""
Google Gemini LLM 提供者
调用 Google Generative AI API
原生支持多模态内容（文本、图片、视频）

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import AsyncGenerator, Optional, Dict, List, Any
from google import genai
from google.genai import types
import os
import logging

from app.agents.base_provider import BaseLLMProvider, LLMResponse
from app.core.config import get_settings

logger = logging.getLogger(__name__)


# Google Gemini 模型最大输出 token 映射
GOOGLE_MAX_OUTPUT_TOKENS = {
    "gemini-3.1-pro-preview": 65536,
    "gemini-3.1-pro": 65536,
    "gemini-3-pro": 65536,
    "gemini-2.5-pro": 65536,
    "gemini-2.5-flash": 65536,
    "gemini-2.0-flash": 32768,
    "gemini-pro": 32768,
    "gemini-pro-vision": 32768,
}


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

    def get_max_output_tokens(self) -> int:
        """
        获取当前模型支持的最大输出 token 数

        Returns:
            最大输出 token 数
        """
        model_lower = self.model_name.lower()
        # 去除可能的前缀
        model_id = model_lower.split(
            "/")[-1] if "/" in model_lower else model_lower

        # 精确匹配
        if model_id in GOOGLE_MAX_OUTPUT_TOKENS:
            return GOOGLE_MAX_OUTPUT_TOKENS[model_id]
        # 模糊匹配
        for key, value in GOOGLE_MAX_OUTPUT_TOKENS.items():
            if key in model_id or model_id in key:
                return value
        # 默认值
        return self.DEFAULT_MAX_OUTPUT_TOKENS

    def _build_multimodal_content(
        self,
        text: str,
        images: Optional[List[str]] = None,
        files: Optional[List[str]] = None,
        videos: Optional[List[str]] = None
    ) -> List[types.Part]:
        """
        构建多模态内容

        Args:
            text: 文本内容
            images: 图片URL列表
            files: 文件URL列表
            videos: 视频URL列表

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

        # 添加视频（Google Gemini 支持视频理解）
        if videos:
            for video_url in videos:
                # 检测视频 MIME 类型
                mime_type = self._detect_video_mime_type(video_url)

                if video_url.startswith("data:video"):
                    # Base64 格式视频
                    import base64
                    base64_data = video_url.split(
                        ",")[1] if "," in video_url else video_url
                    video_data = base64.b64decode(base64_data)
                    parts.append(types.Part(
                        inline_data=types.Blob(
                            mime_type=mime_type,
                            data=video_data
                        )
                    ))
                elif "youtube.com" in video_url or "youtu.be" in video_url:
                    # YouTube URL - Gemini 原生支持
                    parts.append(types.Part(
                        file_data=types.FileData(
                            file_uri=video_url,
                            mime_type=mime_type
                        )
                    ))
                else:
                    # 其他视频 URL（需要是 Google Cloud Storage 或已上传到 File API）
                    parts.append(types.Part(
                        file_data=types.FileData(
                            file_uri=video_url,
                            mime_type=mime_type
                        )
                    ))

        # 添加其他文件
        if files:
            for file_url in files:
                mime_type = self._detect_file_mime_type(file_url)
                parts.append(types.Part(
                    file_data=types.FileData(
                        file_uri=file_url,
                        mime_type=mime_type
                    )
                ))

        return parts

    def _detect_video_mime_type(self, url: str) -> str:
        """检测视频 MIME 类型"""
        url_lower = url.lower()
        if ".mp4" in url_lower:
            return "video/mp4"
        elif ".webm" in url_lower:
            return "video/webm"
        elif ".mov" in url_lower:
            return "video/quicktime"
        elif ".avi" in url_lower:
            return "video/x-msvideo"
        elif ".mkv" in url_lower:
            return "video/x-matroska"
        elif ".flv" in url_lower:
            return "video/x-flv"
        elif "youtube.com" in url_lower or "youtu.be" in url_lower:
            return "video/youtube"
        return "video/mp4"  # 默认

    def _detect_file_mime_type(self, url: str) -> str:
        """检测文件 MIME 类型"""
        url_lower = url.lower()
        if ".pdf" in url_lower:
            return "application/pdf"
        elif ".doc" in url_lower:
            return "application/msword"
        elif ".docx" in url_lower:
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif ".txt" in url_lower:
            return "text/plain"
        elif ".mp3" in url_lower:
            return "audio/mpeg"
        elif ".wav" in url_lower:
            return "audio/wav"
        return "application/octet-stream"

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
        """生成文本（支持多模态：文本、图片、视频）"""
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        if system_prompt:
            config.system_instruction = system_prompt

        # 构建多模态内容（Google Gemini 支持视频）
        if images or videos or files:
            contents = self._build_multimodal_content(
                prompt, images, files, videos)
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
        max_tokens: int = 30000,
        images: Optional[List[str]] = None,
        videos: Optional[List[str]] = None,
        files: Optional[List[str]] = None,
        module_name: str = "unknown",
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """流式生成文本（支持多模态：文本、图片、视频）"""
        config = types.GenerateContentConfig(
            temperature=temperature,
            max_output_tokens=max_tokens,
        )

        if system_prompt:
            config.system_instruction = system_prompt

        # 构建多模态内容（Google Gemini 支持视频）
        if images or videos or files:
            contents = self._build_multimodal_content(
                prompt, images, files, videos)
        else:
            contents = prompt

        try:
            stream = await self.client.aio.models.generate_content_stream(
                model=self.model_name,
                contents=contents,
                config=config
            )
            async for chunk in stream:
                try:
                    # 安全检查：确保 chunk 有 text 属性且不为空
                    if hasattr(chunk, 'text') and chunk.text:
                        yield chunk.text
                except (AttributeError, TypeError) as e:
                    # 记录异常但不中断流式生成
                    logger.warning(
                        f"Google generate_stream chunk解析异常: {e}")
                    continue

        except Exception as e:
            logger.exception(f"Google generate_stream 未知异常: {e}")
            raise

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 30000,
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
        max_tokens: int = 30000,
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

        try:
            stream = await self.client.aio.models.generate_content_stream(
                model=self.model_name,
                contents=contents,
                config=config
            )
            async for chunk in stream:
                try:
                    # 安全检查：确保 chunk 有 text 属性且不为空
                    if hasattr(chunk, 'text') and chunk.text:
                        yield chunk.text
                except (AttributeError, TypeError) as e:
                    # 记录异常但不中断流式生成
                    logger.warning(f"Google chat_stream chunk解析异常: {e}")
                    continue

        except Exception as e:
            logger.exception(f"Google chat_stream 未知异常: {e}")
            raise
