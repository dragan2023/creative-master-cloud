"""
千问 (Qianwen) LLM 提供者
调用阿里云通义千问 API
支持多模态内容（qwen-vl模型）

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import AsyncGenerator, Optional, Dict, List, Any
import dashscope
from dashscope import Generation
from dashscope import MultiModalConversation
import asyncio
import logging

from app.agents.base_provider import BaseLLMProvider, LLMResponse

logger = logging.getLogger(__name__)


async def _safe_call_dashscope(call_func, *args, **kwargs):
    """
    安全调用 dashscope API，处理同步/异步返回值

    Args:
        call_func: 调用函数
        args, kwargs: 传递给函数的参数

    Returns:
        API 响应结果
    """
    result = call_func(*args, **kwargs)
    return result


# 千问支持视觉能力的模型
QIANWEN_VISION_MODELS = [
    "qwen-vl", "qwen-vl-plus", "qwen-vl-max",
    "qwen2-vl", "qwen2.5-vl", "qwen3-vl", "qwen3.5-plus", "qwen3.7"
]

# 必须使用 multimodal-generation 端点的原生多模态模型关键字
# 官方文档：多模态模型（如 qwen3.7-plus、qwen3.5-plus、qwen3-vl-plus）需调用
# /api/v1/services/aigc/multimodal-generation/generation（SDK: MultiModalConversation）
# 用 Generation（text-generation 端点）调用会报 InvalidParameter - url error（已实测验证）
QIANWEN_MULTIMODAL_ONLY_MODELS = [
    "qwen3.7", "qwen3.5-plus", "qwen-vl", "qwen2-vl", "qwen2.5-vl", "qwen3-vl", "qwen-omni"
]

# 千问模型最大输出 token 映射
QIANWEN_MAX_OUTPUT_TOKENS = {
    "qwen3.7-plus": 32768,
    "qwen3.5-plus": 32768,
    "qwen3.5-plus-2026-02-15": 32768,
    "qwen3.5-turbo": 32768,
    "qwen-plus": 32768,
    "qwen-turbo": 32768,
    "qwen-max": 32768,
    "qwen-long": 32768,
    "qwen-vl-plus": 32768,
    "qwen-vl-max": 32768,
    "qwen3": 32768,
    "qwen3-turbo": 32768,
    "qwen3-plus": 32768,
}


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

    def _requires_multimodal_endpoint(self) -> bool:
        """检查当前模型是否必须使用 multimodal-generation 端点"""
        model_lower = self.model_name.lower()
        return any(keyword in model_lower for keyword in QIANWEN_MULTIMODAL_ONLY_MODELS)

    @staticmethod
    def _to_multimodal_content(content: Any) -> Any:
        """将纯文本 content 转为多模态端点要求的列表格式 [{"text": ...}]"""
        if isinstance(content, str):
            return [{"text": content}]
        return content

    @staticmethod
    def _extract_message_text(content: Any) -> str:
        """兼容提取消息文本：Generation 返回 str，MultiModalConversation 返回 list"""
        if isinstance(content, list):
            return "".join(
                part.get("text", "") for part in content if isinstance(part, dict)
            )
        return content or ""

    async def _call_native_api(
        self,
        messages: List[Dict[str, Any]],
        temperature: float,
        max_tokens: int,
        stream: bool = False,
        **kwargs
    ):
        """
        按模型能力路由到正确的 DashScope 原生端点

        - 普通文本模型 -> Generation（text-generation 端点）
        - 原生多模态模型（qwen3.7-plus / VL 系列）-> MultiModalConversation（multimodal-generation 端点）
        """
        call_kwargs: Dict[str, Any] = dict(
            api_key=self.api_key,
            model=self.model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            **kwargs
        )
        if stream:
            call_kwargs["stream"] = True
            call_kwargs["incremental_output"] = True  # 关键：启用增量输出模式

        if self._requires_multimodal_endpoint():
            call_kwargs["messages"] = [
                {**msg, "content": self._to_multimodal_content(msg.get("content"))}
                for msg in messages
            ]
            return await _safe_call_dashscope(MultiModalConversation.call, **call_kwargs)

        call_kwargs["messages"] = messages
        call_kwargs["result_format"] = 'message'
        return await _safe_call_dashscope(Generation.call, **call_kwargs)

    def get_max_output_tokens(self) -> int:
        """
        获取当前模型支持的最大输出 token 数

        Returns:
            最大输出 token 数
        """
        model_lower = self.model_name.lower()
        # 精确匹配
        if model_lower in QIANWEN_MAX_OUTPUT_TOKENS:
            return QIANWEN_MAX_OUTPUT_TOKENS[model_lower]
        # 模糊匹配
        for key, value in QIANWEN_MAX_OUTPUT_TOKENS.items():
            if key in model_lower or model_lower in key:
                return value
        # 默认值
        return self.DEFAULT_MAX_OUTPUT_TOKENS

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

        # 弹出 module_name 避免透传到 DashScope SDK
        kwargs.pop("module_name", None)

        # 如果有图片且模型支持视觉，使用多模态API（千问不支持视频）
        if images and self._supports_vision():
            return await self._generate_multimodal(prompt, images, system_prompt, temperature, max_tokens, **kwargs)

        # 否则使用普通文本生成
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        response = await self._call_native_api(
            messages, temperature, max_tokens, **kwargs)

        if response.status_code != 200:
            raise Exception(
                f"千问 API 调用失败: {response.code} - {response.message}")

        return LLMResponse(
            content=self._extract_message_text(
                response.output.choices[0].message.content),
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
        max_tokens: int = 30000,
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

        response = await _safe_call_dashscope(
            MultiModalConversation.call,
            api_key=self.api_key,
            model=self.model_name,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            top_k=kwargs.get('top_k', 50),
        )

        if response.status_code != 200:
            raise Exception(
                f"千问多模态 API 调用失败: {response.code} - {response.message}")

        return LLMResponse(
            content=self._extract_message_text(
                response.output.choices[0].message.content),
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
        max_tokens: int = 30000,
        images: Optional[List[str]] = None,
        videos: Optional[List[str]] = None,
        files: Optional[List[str]] = None,
        module_name: str = "unknown",
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """流式生成文本（支持多模态：文本、图片）"""

        # 弹出 module_name 避免透传到 DashScope SDK
        kwargs.pop("module_name", None)

        # 构建消息（纯文本或文本+图片）
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        if images and self._supports_vision():
            # 构建多模态消息：文本 + 图片（base64 data URL 或 http URL）
            # MultiModalConversation API 原生支持流式 (stream=True + incremental_output=True)
            content = [{"text": prompt}]
            for img_url in images:
                content.append({"image": img_url})
            messages.append({"role": "user", "content": content})
        else:
            messages.append({"role": "user", "content": prompt})

        responses = await self._call_native_api(
            messages, temperature, max_tokens, stream=True, **kwargs)

        for response in responses:
            try:
                if response.status_code == 200:
                    # 安全检查：确保 output.choices 存在且不为空
                    if hasattr(response, 'output') and response.output:
                        if hasattr(response.output, 'choices') and response.output.choices:
                            choice = response.output.choices[0]
                            if hasattr(choice, 'message') and choice.message:
                                content = self._extract_message_text(
                                    choice.message.content)
                                if content:
                                    yield content
            except (AttributeError, IndexError, TypeError) as e:
                # 记录异常但不中断流式生成
                logger.warning(
                    f"Qianwen generate_stream chunk解析异常: {e}")
                continue

    async def chat(
        self,
        messages: List[Dict[str, Any]],
        temperature: float = 0.7,
        max_tokens: int = 30000,
        **kwargs
    ) -> LLMResponse:
        """多轮对话（支持多模态消息）"""
        response = await self._call_native_api(
            messages, temperature, max_tokens, **kwargs)

        if response.status_code != 200:
            raise Exception(
                f"千问 API 调用失败: {response.code} - {response.message}")

        return LLMResponse(
            content=self._extract_message_text(
                response.output.choices[0].message.content),
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
        max_tokens: int = 30000,
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """流式多轮对话（支持多模态消息）"""
        try:
            responses = await self._call_native_api(
                messages, temperature, max_tokens, stream=True, **kwargs)

            for response in responses:
                try:
                    if response.status_code == 200:
                        # 安全检查：确保 output.choices 存在且不为空
                        if hasattr(response, 'output') and response.output:
                            if hasattr(response.output, 'choices') and response.output.choices:
                                choice = response.output.choices[0]
                                if hasattr(choice, 'message') and choice.message:
                                    content = self._extract_message_text(
                                        choice.message.content)
                                    if content:
                                        yield content
                except (AttributeError, IndexError, TypeError) as e:
                    # 记录异常但不中断流式生成
                    logger.warning(f"Qianwen chat_stream chunk解析异常: {e}")
                    continue

        except Exception as e:
            logger.exception(f"Qianwen chat_stream 未知异常: {e}")
            raise
