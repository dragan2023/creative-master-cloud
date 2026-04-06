"""
LLM断联重连机制

提供统一的LLM调用重试机制，处理API限流（429错误）、网络断联等临时故障。

@date: 2026-04-03
@version: v1.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import asyncio
import functools
import time
from typing import Any, Callable, Optional, Tuple, Type, Union
from app.core.logger import get_logger

logger = get_logger("llm_retry")


# ============================================================================
# 错误检测配置
# ============================================================================

# 限流错误关键词（用于检测限流相关错误）
RATE_LIMIT_KEYWORDS = [
    "429",
    "rate limit",
    "rate_limit",
    "ratelimit",
    "too many",
    "too_many",
    "toomany",
    "overload",
    "quota exceeded",
    "quota_exceeded",
    "limit exceeded",
    "limit_exceeded",
    "throttl",
    "capacity",
    "retry after",
    "retry-after",
    "slow down",
    "请求过于频繁",
    "频率限制",
    "限流",
]

# 网络错误关键词（用于检测网络断联）
NETWORK_ERROR_KEYWORDS = [
    "connection",
    "timeout",
    "timed out",
    "network",
    "unreachable",
    "socket",
    "eof",
    "reset",
    "broken pipe",
    "connection refused",
    "connection reset",
    "connection closed",
    "network error",
    "网络错误",
    "连接失败",
    "连接超时",
    "连接断开",
]

# 需要重试的异常类型名
RETRYABLE_EXCEPTION_TYPES = [
    "RateLimitError",
    "TooManyRequests",
    "ConnectionError",
    "TimeoutError",
    "HTTPStatusError",
    "APIConnectionError",
    "APITimeoutError",
    "APIError",
]


def is_rate_limit_error(error: Exception) -> bool:
    """
    检测是否为限流错误

    Args:
        error: 异常对象

    Returns:
        是否为限流错误
    """
    error_type = type(error).__name__
    error_msg = str(error).lower()

    # 检查异常类型
    if error_type in RETRYABLE_EXCEPTION_TYPES:
        if "RateLimit" in error_type or "TooMany" in error_type:
            return True

    # 检查错误消息中的关键词
    for keyword in RATE_LIMIT_KEYWORDS:
        if keyword.lower() in error_msg:
            return True

    # 检查HTTP状态码
    if hasattr(error, "status_code"):
        if error.status_code == 429:
            return True
    if hasattr(error, "response"):
        if hasattr(error.response, "status_code"):
            if error.response.status_code == 429:
                return True

    return False


def is_network_error(error: Exception) -> bool:
    """
    检测是否为网络断联错误

    Args:
        error: 异常对象

    Returns:
        是否为网络错误
    """
    error_type = type(error).__name__
    error_msg = str(error).lower()

    # 检查异常类型
    if error_type in ["ConnectionError", "TimeoutError", "APIConnectionError", "APITimeoutError"]:
        return True

    # 检查错误消息中的关键词
    for keyword in NETWORK_ERROR_KEYWORDS:
        if keyword.lower() in error_msg:
            return True

    return False


def should_retry(error: Exception) -> bool:
    """
    判断是否应该重试

    Args:
        error: 异常对象

    Returns:
        是否应该重试
    """
    return is_rate_limit_error(error) or is_network_error(error)


def calculate_retry_delay(
    attempt: int,
    base_delay: float = 5.0,
    max_delay: float = 60.0,
    strategy: str = "exponential"
) -> float:
    """
    计算重试延迟时间

    Args:
        attempt: 当前尝试次数（从0开始）
        base_delay: 基础延迟时间（秒）
        max_delay: 最大延迟时间（秒）
        strategy: 延迟策略（"exponential"指数退避, "linear"线性增长, "fixed"固定）

    Returns:
        延迟时间（秒）
    """
    if strategy == "exponential":
        # 指数退避：base * 2^attempt，但有上限
        delay = base_delay * (2 ** attempt)
    elif strategy == "linear":
        # 线性增长：base * (attempt + 1)
        delay = base_delay * (attempt + 1)
    else:
        # 固定延迟
        delay = base_delay

    return min(delay, max_delay)


async def retry_with_backoff(
    func: Callable,
    *args,
    max_retries: int = 3,
    base_delay: float = 5.0,
    max_delay: float = 60.0,
    strategy: str = "exponential",
    retry_condition: Optional[Callable[[Exception], bool]] = None,
    on_retry: Optional[Callable[[int, float, Exception], None]] = None,
    **kwargs
) -> Any:
    """
    带退避策略的异步重试包装器

    Args:
        func: 要执行的异步函数
        *args: 函数参数
        max_retries: 最大重试次数
        base_delay: 基础延迟时间（秒）
        max_delay: 最大延迟时间（秒）
        strategy: 延迟策略（"exponential", "linear", "fixed"）
        retry_condition: 自定义重试条件函数，接收异常返回是否重试
        on_retry: 重试回调函数，接收(尝试次数, 延迟时间, 异常)
        **kwargs: 函数关键字参数

    Returns:
        函数执行结果

    Raises:
        Exception: 达到最大重试次数后抛出最后一次异常
    """
    last_error = None

    for attempt in range(max_retries + 1):  # +1 因为第一次不算重试
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_error = e

            # 判断是否应该重试
            should_retry_flag = False
            if retry_condition:
                should_retry_flag = retry_condition(e)
            else:
                should_retry_flag = should_retry(e)

            # 如果不应该重试或已达到最大重试次数，抛出异常
            if not should_retry_flag or attempt >= max_retries:
                raise

            # 计算延迟时间
            delay = calculate_retry_delay(
                attempt, base_delay, max_delay, strategy)

            # 判断错误类型
            error_type = "限流" if is_rate_limit_error(
                e) else "网络断联" if is_network_error(e) else "未知"

            # 记录日志
            logger.warning(
                f"LLM调用失败({error_type})，{delay:.1f}秒后重试... "
                f"(尝试 {attempt + 1}/{max_retries + 1}): {str(e)[:200]}"
            )

            # 执行重试回调
            if on_retry:
                on_retry(attempt, delay, e)

            # 等待后重试
            await asyncio.sleep(delay)

    # 不应该到达这里，但以防万一
    raise last_error


def sync_retry_with_backoff(
    func: Callable,
    *args,
    max_retries: int = 3,
    base_delay: float = 5.0,
    max_delay: float = 60.0,
    strategy: str = "exponential",
    retry_condition: Optional[Callable[[Exception], bool]] = None,
    on_retry: Optional[Callable[[int, float, Exception], None]] = None,
    **kwargs
) -> Any:
    """
    带退避策略的同步重试包装器

    Args:
        func: 要执行的同步函数
        *args: 函数参数
        max_retries: 最大重试次数
        base_delay: 基础延迟时间（秒）
        max_delay: 最大延迟时间（秒）
        strategy: 延迟策略
        retry_condition: 自定义重试条件函数
        on_retry: 重试回调函数
        **kwargs: 函数关键字参数

    Returns:
        函数执行结果

    Raises:
        Exception: 达到最大重试次数后抛出最后一次异常
    """
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            last_error = e

            should_retry_flag = False
            if retry_condition:
                should_retry_flag = retry_condition(e)
            else:
                should_retry_flag = should_retry(e)

            if not should_retry_flag or attempt >= max_retries:
                raise

            delay = calculate_retry_delay(
                attempt, base_delay, max_delay, strategy)
            error_type = "限流" if is_rate_limit_error(
                e) else "网络断联" if is_network_error(e) else "未知"

            logger.warning(
                f"LLM调用失败({error_type})，{delay:.1f}秒后重试... "
                f"(尝试 {attempt + 1}/{max_retries + 1}): {str(e)[:200]}"
            )

            if on_retry:
                on_retry(attempt, delay, e)

            time.sleep(delay)

    raise last_error


class LLMRetryConfig:
    """LLM重试配置"""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 5.0,
        max_delay: float = 60.0,
        strategy: str = "exponential"
    ):
        """
        初始化重试配置

        Args:
            max_retries: 最大重试次数（默认3次）
            base_delay: 基础延迟时间（默认5秒）
            max_delay: 最大延迟时间（默认60秒）
            strategy: 延迟策略（默认指数退避）
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.strategy = strategy

    def calculate_delay(self, attempt: int) -> float:
        """计算指定尝试次数的延迟时间"""
        return calculate_retry_delay(
            attempt, self.base_delay, self.max_delay, self.strategy
        )


# 默认配置实例
DEFAULT_RETRY_CONFIG = LLMRetryConfig()


def with_retry(
    max_retries: int = 3,
    base_delay: float = 5.0,
    max_delay: float = 60.0,
    strategy: str = "exponential"
):
    """
    重试装饰器（用于异步函数）

    用法:
        @with_retry(max_retries=3, base_delay=5.0)
        async def my_llm_call(prompt: str):
            return await llm.generate(prompt)

    Args:
        max_retries: 最大重试次数
        base_delay: 基础延迟时间
        max_delay: 最大延迟时间
        strategy: 延迟策略
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            return await retry_with_backoff(
                func,
                *args,
                max_retries=max_retries,
                base_delay=base_delay,
                max_delay=max_delay,
                strategy=strategy,
                **kwargs
            )
        return wrapper
    return decorator
