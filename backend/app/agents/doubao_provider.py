"""
豆包 (Doubao) LLM 提供者
调用字节跳动火山引擎豆包 API
使用 OpenAI 兼容接口
支持多模态内容（文本、图片、视频）

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

from app.agents.base_provider import BaseLLMProvider, LLMResponse
import logging

logger = logging.getLogger(__name__)


# 豆包支持视觉能力的模型（包括多模态模型）
# doubao-seed-2-0-pro 系列支持文字、图片、视频输入
DOUBAO_VISION_MODELS = [
    "doubao-1-5-pro",
    "doubao-1-5-vision",
    "doubao-vision",
    "doubao-seed-2-0-pro",  # 支持文字、图片、视频
    "doubao-seed-2-0",      # 支持文字、图片、视频
    "seed-2-0-pro",         # 简写形式
    "seed-2-0"              # 简写形式
]

# 豆包模型最大输出 token 映射
DOUBAO_MAX_OUTPUT_TOKENS = {
    "doubao-seed-2-0-pro": 32768,
    "doubao-seed-2-0-pro-260215": 32768,
    "seed-2-0-pro": 32768,
    "doubao-1-5-pro": 32768,
    "doubao-pro-32k": 32768,
    "doubao-pro-128k": 32768,
    "deepseek-v3-2": 32768,
    "deepseek-v3-2-251201": 32768,
}


class DoubaoProvider(BaseLLMProvider):
    """豆包 LLM 提供者"""

    # 标记支持多模态
    supports_vision = True

    def __init__(
        self,
        api_key: str,
        model_name: str = "doubao-pro-32k",
        api_base: Optional[str] = "https://ark.cn-beijing.volces.com/api/v3",
        **kwargs
    ):
        super().__init__(api_key, model_name, api_base, **kwargs)
        self._client: Optional[AsyncOpenAI] = None

    @property
    def client(self) -> AsyncOpenAI:
        """获取 OpenAI 兼容客户端（延迟初始化）"""
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.api_key,
                base_url=self.api_base
            )
        return self._client

    def _supports_vision(self) -> bool:
        """检查当前模型是否支持视觉（图片/视频）"""
        model_lower = self.model_name.lower()
        # 精确匹配或包含关键词
        for vm in DOUBAO_VISION_MODELS:
            if vm in model_lower or model_lower == vm:
                return True
        # 额外检查：包含 vision/seed 关键词的模型通常支持视觉
        if "vision" in model_lower or "seed" in model_lower:
            return True
        return False

    def get_max_output_tokens(self) -> int:
        """
        获取当前模型支持的最大输出 token 数

        Returns:
            最大输出 token 数
        """
        model_lower = self.model_name.lower()
        # 精确匹配
        if model_lower in DOUBAO_MAX_OUTPUT_TOKENS:
            return DOUBAO_MAX_OUTPUT_TOKENS[model_lower]
        # 模糊匹配
        for key, value in DOUBAO_MAX_OUTPUT_TOKENS.items():
            if key in model_lower or model_lower in key:
                return value
        # 默认值
        return self.DEFAULT_MAX_OUTPUT_TOKENS

    def _build_content(
        self,
        text: str,
        images: Optional[List[str]] = None,
        videos: Optional[List[str]] = None
    ) -> Union[str, List[Dict[str, Any]]]:
        """
        构建消息内容（支持多模态）

        Args:
            text: 文本内容
            images: 图片URL列表（支持 base64、本地路径、网络URL）
            videos: 视频URL列表（支持 base64、本地路径、网络URL）

        Returns:
            构建的消息内容
        """
        # 如果没有多模态内容或不支持视觉，返回纯文本
        if not self._supports_vision():
            return text

        has_images = images and len(images) > 0
        has_videos = videos and len(videos) > 0

        if not has_images and not has_videos:
            return text

        content = [{"type": "text", "text": text}]

        # 添加图片内容
        if has_images:
            for img_url in images:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": img_url}
                })

        # 添加视频内容
        if has_videos:
            for video_url in videos:
                content.append({
                    "type": "video_url",
                    "video_url": {"url": video_url}
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
        """生成文本（支持多模态：文本、图片、视频）"""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        user_content = self._build_content(prompt, images, videos)
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
            provider="doubao",
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
        """流式生成文本（支持多模态：文本、图片、视频）"""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        user_content = self._build_content(prompt, images, videos)
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
                    logger.warning(f"Doubao流式生成chunk解析异常: {e}")
                    continue

        except APIConnectionError as e:
            logger.error(f"Doubao API连接错误: {e}")
            raise ConnectionError(f"无法连接到豆包API服务: {str(e)}")
        except RateLimitError as e:
            logger.error(f"Doubao API速率限制: {e}")
            raise RuntimeError(f"豆包API请求频率超限，请稍后重试: {str(e)}")
        except APITimeoutError as e:
            logger.error(f"Doubao API超时: {e}")
            raise TimeoutError(f"豆包API请求超时: {str(e)}")
        except InternalServerError as e:
            logger.error(f"Doubao服务器内部错误: {e}")
            raise RuntimeError(f"豆包服务器内部错误: {str(e)}")
        except APIStatusError as e:
            logger.error(f"Doubao API状态错误 [{e.status_code}]: {e.message}")
            raise RuntimeError(f"豆包API错误 [{e.status_code}]: {e.message}")
        except Exception as e:
            logger.exception(f"Doubao流式生成未知异常: {e}")
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
            provider="doubao",
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
                    logger.warning(f"Doubao chat_stream chunk解析异常: {e}")
                    continue

        except APIConnectionError as e:
            logger.error(f"Doubao chat_stream API连接错误: {e}")
            raise ConnectionError(f"无法连接到豆包API服务: {str(e)}")
        except RateLimitError as e:
            logger.error(f"Doubao chat_stream API速率限制: {e}")
            raise RuntimeError(f"豆包API请求频率超限，请稍后重试: {str(e)}")
        except APITimeoutError as e:
            logger.error(f"Doubao chat_stream API超时: {e}")
            raise TimeoutError(f"豆包API请求超时: {str(e)}")
        except InternalServerError as e:
            logger.error(f"Doubao chat_stream 服务器内部错误: {e}")
            raise RuntimeError(f"豆包服务器内部错误: {str(e)}")
        except APIStatusError as e:
            logger.error(
                f"Doubao chat_stream API状态错误 [{e.status_code}]: {e.message}")
            raise RuntimeError(f"豆包API错误 [{e.status_code}]: {e.message}")
        except Exception as e:
            logger.exception(f"Doubao chat_stream 未知异常: {e}")
            raise

    async def close(self) -> None:
        """
        关闭豆包客户端，释放资源

        正确清理 AsyncOpenAI 内部的 httpx 客户端，避免事件循环关闭后的资源泄漏
        """
        if self._client is not None:
            try:
                await self._client.close()
            except Exception as e:
                logger.debug(f"关闭豆包客户端时出错: {e}")
            finally:
                self._client = None
