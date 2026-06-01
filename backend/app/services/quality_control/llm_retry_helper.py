"""质控LLM调用重试工具（P1统一：使用通用llm_retry模块）

提供带重试机制的LLM调用包装函数，统一使用 app.utils.llm_retry
"""
import logging
from typing import Any, Optional

from app.utils.llm_retry import retry_with_backoff, is_rate_limit_error, is_network_error

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
    带重试机制的LLM调用辅助函数（P1统一版）

    特性:
    - 使用统一重试机制(app.utils.llm_retry)
    - 自动检测限流(429)和网络错误
    - 指数退避重试策略
    - 详细日志记录

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
    """
    async def _call():
        return await llm_provider.generate(
            prompt=prompt,
            temperature=temperature,
            timeout=timeout,
            module_name="qc_retry"
        )

    # 使用通用重试机制
    return await retry_with_backoff(
        _call,
        max_retries=max_retries,
        base_delay=retry_delay,
        strategy="exponential",
        retry_condition=lambda e: is_rate_limit_error(e) or is_network_error(e),
        on_retry=lambda attempt, delay, err: logger.warning(
            f"[{context}] 重试 {attempt+1}/{max_retries}, 延迟{delay:.1f}s: {str(err)[:100]}"
        )
    )