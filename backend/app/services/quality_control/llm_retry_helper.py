"""
质控LLM调用重试工具
提供带429错误重试机制的LLM调用包装函数
"""
import asyncio
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


async def llm_call_with_retry(
    llm_provider: Any,
    prompt: str,
    temperature: float = 0.2,
    timeout: int = 120,
    max_retries: int = 3,
    retry_delay: float = 5.0,
    context: str = "质控LLM调用"
) -> Any:
    """
    带重试机制的LLM调用辅助函数

    特性:
    - 自动检测429错误(请求限流)
    - 指数退避重试策略(5s, 10s, 20s)
    - 详细日志记录
    - 支持自定义上下文标识

    Args:
        llm_provider: LLM提供者实例
        prompt: 提示词
        temperature: 温度参数(0-1)
        timeout: 超时时间(秒)
        max_retries: 最大重试次数(默认3次)
        retry_delay: 初始重试延迟(秒,默认5秒)
        context: 上下文标识(用于日志)

    Returns:
        LLM响应对象

    Raises:
        Exception: 非429错误或重试耗尽后的错误

    Example:
        >>> response = await llm_call_with_retry(
        ...     llm_provider=provider,
        ...     prompt="分析文本质量",
        ...     temperature=0.2,
        ...     context="单元结构分析"
        ... )
    """
    response = None

    for attempt in range(max_retries):
        try:
            response = await llm_provider.generate(
                prompt=prompt,
                temperature=temperature,
                timeout=timeout
            )
            return response  # 成功则返回

        except Exception as e:
            error_str = str(e)

            # 检测429错误(请求限流)
            if '429' in error_str or 'TooManyRequests' in error_str or 'ServerOverloaded' in error_str:
                if attempt < max_retries - 1:
                    # 指数退避: 5s, 10s, 20s
                    wait_time = retry_delay * (2 ** attempt)
                    logger.warning(
                        f"[{context}] LLM返回429错误,第{attempt+1}次重试,"
                        f"等待{wait_time}秒..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        f"[{context}] LLM 429错误,已重试{max_retries}次,放弃"
                    )
                    raise  # 重试耗尽,抛出错误
            else:
                # 其他错误直接抛出
                logger.error(f"[{context}] LLM调用失败: {error_str}")
                raise

    return response
