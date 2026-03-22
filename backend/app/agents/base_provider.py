"""
LLM 提供者基类
定义统一的 LLM 调用接口
支持多模态内容（文本、图片、文件）
"""
from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional, Dict, Any, List, Union
from pydantic import BaseModel, Field
from enum import Enum
from dataclasses import dataclass


class LLMProvider(str, Enum):
    """LLM 提供商枚举"""
    DEEPSEEK = "deepseek"
    DOUBAO = "doubao"
    QIANWEN = "qianwen"
    OPENAI = "openai"
    GOOGLE = "google"
    CUSTOM = "custom"


@dataclass
class MultimodalContent:
    """多模态内容单元"""
    type: str  # "text" | "image_url" | "file_url"
    text: Optional[str] = None
    url: Optional[str] = None
    media_type: Optional[str] = None  # image/png, image/jpeg, application/pdf


class LLMResponse(BaseModel):
    """LLM 响应模型"""
    content: str
    model: str
    provider: str
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None


class MultimodalMessage(BaseModel):
    """多模态消息模型"""
    role: str = "user"
    content: List[Dict[str, Any]] = Field(default_factory=list)

    @classmethod
    def from_text(cls, text: str, role: str = "user") -> "MultimodalMessage":
        """从纯文本创建消息"""
        return cls(role=role, content=[{"type": "text", "text": text}])

    @classmethod
    def from_text_and_images(
        cls,
        text: str,
        images: List[str],
        role: str = "user"
    ) -> "MultimodalMessage":
        """从文本和图片URL创建多模态消息"""
        content = [{"type": "text", "text": text}]
        for img_url in images:
            content.append({
                "type": "image_url",
                "image_url": {"url": img_url}
            })
        return cls(role=role, content=content)


class BaseLLMProvider(ABC):
    """LLM 提供者基类"""

    # 标记是否支持多模态
    supports_vision: bool = False

    # 默认最大输出 token 数（设置为较大值避免截断）
    DEFAULT_MAX_OUTPUT_TOKENS = 32768

    def __init__(
        self,
        api_key: str,
        model_name: str,
        api_base: Optional[str] = None,
        **kwargs
    ):
        self.api_key = api_key
        self.model_name = model_name
        self.api_base = api_base
        self.kwargs = kwargs

    def get_max_output_tokens(self) -> int:
        """
        获取当前模型支持的最大输出 token 数

        子类可以重写此方法以提供特定模型的能力信息

        Returns:
            最大输出 token 数，默认 4096
        """
        return self.DEFAULT_MAX_OUTPUT_TOKENS

    def build_multimodal_content(
        self,
        text: str,
        images: Optional[List[str]] = None,
        files: Optional[List[str]] = None
    ) -> Union[str, List[Dict[str, Any]]]:
        """
        构建多模态内容

        Args:
            text: 文本内容
            images: 图片URL列表（支持http(s)://和data:image/格式的base64）
            files: 文件URL列表

        Returns:
            如果没有图片/文件，返回纯文本字符串
            如果有图片/文件，返回多模态内容数组
        """
        if not images and not files:
            return text

        content = [{"type": "text", "text": text}]

        # 添加图片
        if images:
            for img_url in images:
                if img_url.startswith("data:image"):
                    # Base64格式
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": img_url}
                    })
                else:
                    # URL格式
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": img_url}
                    })

        # 添加文件（目前主要是PDF等文档）
        if files:
            for file_url in files:
                content.append({
                    "type": "file_url",
                    "file_url": {"url": file_url}
                })

        return content

    @abstractmethod
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
        """
        生成文本（支持多模态）

        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            temperature: 温度参数
            max_tokens: 最大 Token 数
            images: 图片URL列表（支持http(s)://和base64 data:image格式）
            videos: 视频URL列表（支持http(s)://和base64 data:video格式）
            files: 文件URL列表
            **kwargs: 其他参数

        Returns:
            LLM 响应
        """
        pass

    @abstractmethod
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
        """
        流式生成文本（支持多模态）

        Args:
            prompt: 用户提示
            system_prompt: 系统提示
            temperature: 温度参数
            max_tokens: 最大 Token 数
            images: 图片URL列表
            videos: 视频URL列表
            files: 文件URL列表
            **kwargs: 其他参数

        Yields:
            生成的文本片段
        """
        pass

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 30000,
        **kwargs
    ) -> LLMResponse:
        """
        多轮对话（支持多模态消息）

        Args:
            messages: 消息列表，content可以是字符串或多模态内容数组
            temperature: 温度参数
            max_tokens: 最大 Token 数
            **kwargs: 其他参数（可包含images, files）

        Returns:
            LLM 响应
        """
        # 提取最后一条用户消息作为prompt
        last_user_msg = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_msg = msg
                break

        if not last_user_msg:
            raise ValueError("No user message found in messages")

        # 处理content（可能是字符串或多模态数组）
        content = last_user_msg.get("content", "")
        if isinstance(content, str):
            prompt = content
            images = kwargs.pop("images", None)
            files = kwargs.pop("files", None)
        elif isinstance(content, list):
            # 多模态内容数组
            prompt = ""
            images = []
            files = []
            for item in content:
                if item.get("type") == "text":
                    prompt += item.get("text", "")
                elif item.get("type") == "image_url":
                    img_url = item.get("image_url", {}).get("url", "")
                    if img_url:
                        images.append(img_url)
                elif item.get("type") == "file_url":
                    file_url = item.get("file_url", {}).get("url", "")
                    if file_url:
                        files.append(file_url)
        else:
            prompt = str(content)
            images = kwargs.pop("images", None)
            files = kwargs.pop("files", None)

        return await self.generate(
            prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            images=images,
            files=files,
            **kwargs
        )

    async def chat_stream(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 30000,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """
        流式多轮对话（支持多模态消息）

        Args:
            messages: 消息列表，content可以是字符串或多模态内容数组
            temperature: 温度参数
            max_tokens: 最大 Token 数
            **kwargs: 其他参数

        Yields:
            生成的文本片段
        """
        # 提取最后一条用户消息作为prompt
        last_user_msg = None
        for msg in reversed(messages):
            if msg.get("role") == "user":
                last_user_msg = msg
                break

        if not last_user_msg:
            raise ValueError("No user message found in messages")

        # 处理content
        content = last_user_msg.get("content", "")
        if isinstance(content, str):
            prompt = content
            images = kwargs.pop("images", None)
            files = kwargs.pop("files", None)
        elif isinstance(content, list):
            prompt = ""
            images = []
            files = []
            for item in content:
                if item.get("type") == "text":
                    prompt += item.get("text", "")
                elif item.get("type") == "image_url":
                    img_url = item.get("image_url", {}).get("url", "")
                    if img_url:
                        images.append(img_url)
                elif item.get("type") == "file_url":
                    file_url = item.get("file_url", {}).get("url", "")
                    if file_url:
                        files.append(file_url)
        else:
            prompt = str(content)
            images = kwargs.pop("images", None)
            files = kwargs.pop("files", None)

        async for chunk in self.generate_stream(
            prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            images=images,
            files=files,
            **kwargs
        ):
            yield chunk

    def get_model_info(self) -> Dict[str, Any]:
        """获取模型信息"""
        return {
            "provider": self.__class__.__name__.replace("Provider", "").lower(),
            "model": self.model_name,
            "api_base": self.api_base,
            "supports_vision": self.supports_vision,
            "max_output_tokens": self.get_max_output_tokens()
        }
