"""
DeepSeek LLM 提供者
使用 OpenAI 兼容接口调用 DeepSeek API
支持多模态内容（DeepSeek-VL模型）
支持思考模式（reasoning_effort参数）

@date: 2026-04-02
@version: v3.1.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
from typing import AsyncGenerator, Optional, Dict, List, Any, Union
from openai import AsyncOpenAI
from openai import (
    APIConnectionError, RateLimitError, APIStatusError,
    InternalServerError, APITimeoutError
)
import os
import logging
from datetime import datetime
from pathlib import Path

from app.agents.base_provider import BaseLLMProvider, LLMResponse
import logging

logger = logging.getLogger(__name__)


# DeepSeek支持视觉的模型
DEEPSEEK_VISION_MODELS = [
    "deepseek-vl", "deepseek-vl2"
]

# DeepSeek支持思考模式的模型
DEEPSEEK_THINKING_MODELS = [
    "deepseek-v4-pro",
    "deepseek-v4-flash",
    "deepseek-reasoner",  # 旧版兼容
]

# DeepSeek模型最大输出 token 映射
DEEPSEEK_MAX_OUTPUT_TOKENS = {
    # V4 系列（最新）
    "deepseek-v4-pro": 32768,
    "deepseek-v4-flash": 32768,
    # 旧版兼容（2026/07/24弃用）
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
        model_name: str = "deepseek-v4-flash",
        api_base: Optional[str] = "https://api.deepseek.com",
        reasoning_effort: Optional[str] = None,  # 思考强度：high/max
        enable_thinking: bool = False,  # 是否启用思考模式
        thinking_save_dir: Optional[str] = None,  # 思考过程保存目录
        **kwargs
    ):
        super().__init__(api_key, model_name, api_base, **kwargs)
        self._client: Optional[AsyncOpenAI] = None
        self.reasoning_effort = reasoning_effort
        self.enable_thinking = enable_thinking
        self.thinking_save_dir = thinking_save_dir or "./data/thinking_logs"
        
        # 确保思考日志目录存在
        if self.enable_thinking:
            Path(self.thinking_save_dir).mkdir(parents=True, exist_ok=True)

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

    def _supports_thinking(self) -> bool:
        """检查当前模型是否支持思考模式"""
        return any(tm in self.model_name.lower() for tm in DEEPSEEK_THINKING_MODELS)

    def _save_thinking_content(self, thinking_content: str, module_name: str = "unknown"):
        """
        保存思考过程到文件
        
        Args:
            thinking_content: 思考过程内容
            module_name: 调用模块名称
        """
        if not thinking_content or not self.enable_thinking:
            return
        
        try:
            # 创建文件名：模块名_时间戳.txt
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{module_name}_{timestamp}.txt"
            filepath = os.path.join(self.thinking_save_dir, filename)
            
            # 写入思考过程
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"=== DeepSeek 思考过程记录 ===\n")
                f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"模型: {self.model_name}\n")
                f.write(f"模块: {module_name}\n")
                f.write(f"思考强度: {self.reasoning_effort or 'high'}\n")
                f.write(f"{'='*50}\n\n")
                f.write(thinking_content)
            
            logger.info(f"思考过程已保存: {filepath}")
        except Exception as e:
            logger.error(f"保存思考过程失败: {e}")

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
        module_name: str = "unknown",  # 调用模块名称，用于保存思考过程
        **kwargs
    ) -> LLMResponse:
        """生成文本（支持多模态：文本、图片、思考模式）"""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # DeepSeek 不支持视频，忽略 videos 参数
        user_content = self._build_content(prompt, images)
        messages.append({"role": "user", "content": user_content})

        # 构建API调用参数
        api_kwargs = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        
        # 思考模式配置（根据官方文档，思考模式不支持temperature等参数）
        if self.enable_thinking and self._supports_thinking():
            api_kwargs["reasoning_effort"] = self.reasoning_effort or "high"
            api_kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
            # 思考模式下不使用temperature等参数
            logger.info(f"启用思考模式 - 模型: {self.model_name}, 思考强度: {api_kwargs['reasoning_effort']}")
        else:
            # 非思考模式才使用temperature
            api_kwargs["temperature"] = temperature
        
        # 合并其他kwargs
        api_kwargs.update(kwargs)

        response = await self.client.chat.completions.create(**api_kwargs)

        # 提取思考过程内容
        reasoning_content = None
        if hasattr(response.choices[0].message, 'reasoning_content'):
            reasoning_content = response.choices[0].message.reasoning_content
            
            # 保存思考过程到文件
            if reasoning_content:
                self._save_thinking_content(reasoning_content, module_name)

        return LLMResponse(
            content=response.choices[0].message.content,
            model=response.model,
            provider="deepseek",
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            } if response.usage else None,
            finish_reason=response.choices[0].finish_reason,
            reasoning_content=reasoning_content
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
        module_name: str = "unknown",  # 调用模块名称，用于保存思考过程
        **kwargs
    ) -> AsyncGenerator[str, None]:
        """流式生成文本（支持多模态：文本、图片、思考模式）"""
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # DeepSeek 不支持视频，忽略 videos 参数
        user_content = self._build_content(prompt, images)
        messages.append({"role": "user", "content": user_content})

        # 构建API调用参数
        api_kwargs = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
            "stream": True,
        }
        
        # 思考模式配置
        if self.enable_thinking and self._supports_thinking():
            api_kwargs["reasoning_effort"] = self.reasoning_effort or "high"
            api_kwargs["extra_body"] = {"thinking": {"type": "enabled"}}
            logger.info(f"启用思考模式（流式） - 模型: {self.model_name}, 思考强度: {api_kwargs['reasoning_effort']}")
        else:
            api_kwargs["temperature"] = temperature
        
        # 合并其他kwargs
        api_kwargs.update(kwargs)

        try:
            stream = await self.client.chat.completions.create(**api_kwargs)

            # 用于收集思考过程（流式）
            reasoning_content_parts = []
            is_reasoning = False

            async for chunk in stream:
                try:
                    # 安全检查：确保 choices 列表不为空且 delta 存在
                    if chunk.choices and len(chunk.choices) > 0:
                        delta = chunk.choices[0].delta
                        
                        # 检查是否有思考过程内容
                        if hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                            reasoning_content_parts.append(delta.reasoning_content)
                            is_reasoning = True
                            continue  # 思考过程不输出给前端
                        
                        # 输出正式内容
                        if delta and hasattr(delta, 'content') and delta.content:
                            yield delta.content
                            
                except (AttributeError, IndexError, TypeError) as e:
                    # 记录异常但不中断流式生成
                    logger.warning(f"DeepSeek流式生成chunk解析异常: {e}")
                    continue
            
            # 流式生成完成后，保存思考过程
            if reasoning_content_parts:
                full_reasoning = "".join(reasoning_content_parts)
                self._save_thinking_content(full_reasoning, module_name)
                logger.info(f"流式思考过程已收集，共 {len(reasoning_content_parts)} 个片段")

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
