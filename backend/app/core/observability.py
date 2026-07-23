"""
结构化可观测契约

提供统一的结构化日志助手，保证任务与模型调用日志：
- 始终携带 request_id / task_id / user_id / module / provider / model / status / duration_ms；
- 只记录"结果类别"，绝不记录 prompt 全文、API Key 或完整用户正文。

@date: 2026-07-23
"""
from enum import Enum
from typing import Optional

from app.core.logger import get_logger
from app.core.request_context import get_request_id, get_task_id


class LLMCallStatus(str, Enum):
    """外部模型调用的结果类别（不含任何内容明文）。"""
    SUCCESS = "success"
    RATE_LIMITED = "rate_limited"
    TIMEOUT = "timeout"
    AUTH_ERROR = "auth_error"
    PROVIDER_ERROR = "provider_error"
    UNKNOWN_ERROR = "unknown_error"


def classify_exception(exc: Optional[BaseException]) -> LLMCallStatus:
    """
    将异常归类为稳定的结果类别，便于仪表盘按失败类别聚合。

    仅依据异常类型与提示文本关键字判断，不解析或记录用户内容。
    """
    if exc is None:
        return LLMCallStatus.SUCCESS

    text = f"{type(exc).__name__} {exc}".lower()
    if "429" in text or "rate limit" in text or "too many requests" in text:
        return LLMCallStatus.RATE_LIMITED
    if "timeout" in text or "timed out" in text:
        return LLMCallStatus.TIMEOUT
    if "401" in text or "403" in text or "unauthorized" in text or "api key" in text:
        return LLMCallStatus.AUTH_ERROR
    if "5" == text[:1] and "error" in text:  # 兜底：5xx
        return LLMCallStatus.PROVIDER_ERROR
    if "status" in text and ("500" in text or "502" in text or "503" in text):
        return LLMCallStatus.PROVIDER_ERROR
    return LLMCallStatus.UNKNOWN_ERROR


def _format_fields(**fields) -> str:
    """将结构化字段拼接为 key=value 形式，缺省字段以占位符补齐。"""
    parts = []
    for key, value in fields.items():
        parts.append(f"{key}={value if value not in (None, '') else '-'}")
    return " ".join(parts)


def log_llm_call(
    provider: str,
    model: str,
    module: str,
    status: LLMCallStatus,
    duration_ms: float,
    token_count: int = 0,
    user_id: str = "system",
    error_type: Optional[str] = None,
) -> None:
    """
    记录一次外部模型调用的结构化日志，并汇入监控聚合。

    Args:
        provider: 提供商标识（如 qianwen/deepseek）
        model: 模型名称
        module: 业务模块标识
        status: 结果类别（LLMCallStatus）
        duration_ms: 调用耗时（毫秒）
        token_count: 消耗 token 数（如可得）
        user_id: 用户标识（用于日志绑定，不含敏感内容）
        error_type: 失败时的异常类型名（不含堆栈或内容明文）
    """
    logger = get_logger(user_id=str(user_id))
    message = _format_fields(
        event="llm_call",
        request_id=get_request_id(),
        task_id=get_task_id(),
        module=module,
        provider=provider,
        model=model,
        status=status.value,
        duration_ms=round(duration_ms, 2),
        token_count=token_count,
        error_type=error_type,
    )

    if status == LLMCallStatus.SUCCESS:
        logger.info(message)
    else:
        logger.error(message)

    # 汇入监控聚合（失败类别 / 耗时 / token）
    try:
        from app.services.monitoring import get_monitoring_service
        get_monitoring_service().record_llm_call(
            provider=provider,
            model=model,
            module=module,
            status=status.value,
            duration_ms=duration_ms,
            token_count=token_count,
        )
    except Exception:
        # 监控失败绝不影响主流程
        pass


def log_request_event(
    event: str,
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    user_id: str = "system",
) -> None:
    """记录一次 HTTP 请求生命周期事件的结构化日志。"""
    logger = get_logger(user_id=str(user_id))
    message = _format_fields(
        event=event,
        request_id=get_request_id(),
        task_id=get_task_id(),
        method=method,
        path=path,
        status=status_code,
        duration_ms=round(duration_ms, 2),
    )
    if status_code >= 500:
        logger.error(message)
    else:
        logger.info(message)
