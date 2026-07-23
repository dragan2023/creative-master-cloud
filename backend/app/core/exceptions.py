"""
统一异常定义模块

提供项目级别的异常层次结构，便于捕获、处理和日志追踪。

@date: 2026-04-02
@version: v3.0.0
@author: 周金磊
@contact: QQ：7527149（添加时请说明来意）
"""
import uuid
from typing import Optional, Any, Dict
from enum import Enum


class ErrorCode(str, Enum):
    """错误代码枚举"""
    # 认证相关
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    AUTH_TOKEN_INVALID = "AUTH_TOKEN_INVALID"
    AUTH_UNAUTHORIZED = "AUTH_UNAUTHORIZED"
    # 授权相关
    PERMISSION_DENIED = "PERMISSION_DENIED"
    INSUFFICIENT_PERMISSIONS = "INSUFFICIENT_PERMISSIONS"
    # 资源相关
    RESOURCE_NOT_FOUND = "RESOURCE_NOT_FOUND"
    RESOURCE_ALREADY_EXISTS = "RESOURCE_ALREADY_EXISTS"
    # 验证相关
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_INPUT = "INVALID_INPUT"
    # 业务相关
    GENERATION_FAILED = "GENERATION_FAILED"
    LLM_SERVICE_ERROR = "LLM_SERVICE_ERROR"
    KNOWLEDGE_BASE_ERROR = "KNOWLEDGE_BASE_ERROR"
    TASK_CANCELLED = "TASK_CANCELLED"
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
    # 外部模型/Provider 相关（携带 retryable 语义）
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_RATE_LIMITED = "PROVIDER_RATE_LIMITED"
    PROVIDER_AUTH_FAILED = "PROVIDER_AUTH_FAILED"
    CONTENT_PARSE_FAILED = "CONTENT_PARSE_FAILED"
    # 系统相关
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


class AppException(Exception):
    """应用基础异常

    retryable 表示该错误是否值得调用方重试（如外部模型超时、限流）。
    默认 False，由具体子类按业务语义显式声明。
    """
    def __init__(
        self,
        error_code: ErrorCode,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        retryable: bool = False
    ):
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.trace_id = trace_id or str(uuid.uuid4())
        self.retryable = retryable
        super().__init__(self.message)


class AuthenticationException(AppException):
    """认证异常（401）"""
    def __init__(self, error_code: ErrorCode = ErrorCode.AUTH_UNAUTHORIZED, message: str = "认证失败", **kwargs):
        super().__init__(error_code=error_code, message=message, status_code=401, **kwargs)


class AuthorizationException(AppException):
    """授权异常（403）"""
    def __init__(self, error_code: ErrorCode = ErrorCode.PERMISSION_DENIED, message: str = "权限不足", **kwargs):
        super().__init__(error_code=error_code, message=message, status_code=403, **kwargs)


class ResourceNotFoundException(AppException):
    """资源不存在异常（404）"""
    def __init__(self, message: str = "资源不存在", **kwargs):
        super().__init__(error_code=ErrorCode.RESOURCE_NOT_FOUND, message=message, status_code=404, **kwargs)


class ValidationException(AppException):
    """验证异常（400/422）"""
    def __init__(self, message: str = "参数验证失败", status_code: int = 400, **kwargs):
        super().__init__(error_code=ErrorCode.VALIDATION_ERROR, message=message, status_code=status_code, **kwargs)


class GenerationException(AppException):
    """生成异常（500）"""
    def __init__(self, message: str = "生成失败", **kwargs):
        super().__init__(error_code=ErrorCode.GENERATION_FAILED, message=message, status_code=500, **kwargs)


class LLMServiceException(AppException):
    """LLM服务异常（503）"""
    def __init__(self, message: str = "LLM服务不可用", **kwargs):
        super().__init__(error_code=ErrorCode.LLM_SERVICE_ERROR, message=message, status_code=503, **kwargs)


class KnowledgeBaseException(AppException):
    """知识库异常（500）"""
    def __init__(self, message: str = "知识库操作失败", **kwargs):
        super().__init__(error_code=ErrorCode.KNOWLEDGE_BASE_ERROR, message=message, status_code=500, **kwargs)


class TaskCancelledException(AppException):
    """任务取消异常"""
    def __init__(self, message: str = "任务已取消", **kwargs):
        super().__init__(error_code=ErrorCode.TASK_CANCELLED, message=message, status_code=499, **kwargs)


class InvalidTaskTransitionException(AppException):
    """非法任务状态迁移异常（409）

    当尝试执行不在允许迁移表中的状态转换时抛出，原状态保持不变。
    """
    def __init__(
        self,
        from_status: str,
        to_status: str,
        message: Optional[str] = None,
        **kwargs
    ):
        self.from_status = from_status
        self.to_status = to_status
        detail_message = message or f"非法任务状态迁移: {from_status} -> {to_status}"
        details = kwargs.pop("details", {}) or {}
        details.update({"from_status": from_status, "to_status": to_status})
        super().__init__(
            error_code=ErrorCode.INVALID_STATE_TRANSITION,
            message=detail_message,
            status_code=409,
            details=details,
            **kwargs
        )


class ProviderTimeoutException(LLMServiceException):
    """外部模型调用超时（可重试）"""
    def __init__(self, message: str = "外部模型响应超时，请稍后重试", **kwargs):
        kwargs.pop("retryable", None)
        super().__init__(message=message, retryable=True, **kwargs)
        self.error_code = ErrorCode.PROVIDER_TIMEOUT


class ProviderRateLimitException(LLMServiceException):
    """外部模型限流（可重试）"""
    def __init__(self, message: str = "外部模型触发限流，请稍后重试", **kwargs):
        kwargs.pop("retryable", None)
        super().__init__(message=message, retryable=True, **kwargs)
        self.error_code = ErrorCode.PROVIDER_RATE_LIMITED


class ProviderAuthException(LLMServiceException):
    """外部模型鉴权失败（不可重试，需人工修正密钥）"""
    def __init__(self, message: str = "外部模型鉴权失败，请检查 API Key 配置", **kwargs):
        kwargs.pop("retryable", None)
        super().__init__(message=message, retryable=False, **kwargs)
        self.error_code = ErrorCode.PROVIDER_AUTH_FAILED
        self.status_code = 502


class ContentParseException(GenerationException):
    """外部模型返回内容解析失败（不可重试）"""
    def __init__(self, message: str = "模型返回内容解析失败", **kwargs):
        kwargs.pop("retryable", None)
        super().__init__(message=message, retryable=False, **kwargs)
        self.error_code = ErrorCode.CONTENT_PARSE_FAILED


# 外部模型错误关键词→领域异常的映射规则（按优先级从上到下匹配）
# 仅用于把第三方 SDK / HTTP 抛出的原始异常翻译成可诊断、可判断重试的领域异常。
_PROVIDER_AUTH_KEYWORDS = ("401", "403", "unauthorized", "forbidden",
                          "invalid api key", "authentication", "api key")
_PROVIDER_RATE_LIMIT_KEYWORDS = ("429", "rate limit", "too many requests",
                                "quota", "throttl")
_PROVIDER_TIMEOUT_KEYWORDS = ("timeout", "timed out", "deadline", "read timed out")
_CONTENT_PARSE_KEYWORDS = ("json", "parse", "decode", "unmarshal", "expecting value")


def classify_provider_error(exc: Exception) -> AppException:
    """将外部模型调用抛出的原始异常映射为携带错误码与 retryable 的领域异常。

    已是 AppException 子类则直接返回；否则按异常类型与消息关键词分类：
    - 超时→ ProviderTimeoutException (retryable)
    - 限流/配额→ ProviderRateLimitException (retryable)
    - 鉴权→ ProviderAuthException (不可重试)
    - 内容解析→ ContentParseException (不可重试)
    - 其他→ LLMServiceException (不可重试，由 API 边界兼底记录 trace id)
    """
    if isinstance(exc, AppException):
        return exc

    import asyncio

    message = str(exc) or exc.__class__.__name__
    lowered = message.lower()

    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) or _match_keyword(lowered, _PROVIDER_TIMEOUT_KEYWORDS):
        return ProviderTimeoutException(details={"origin": exc.__class__.__name__})
    if _match_keyword(lowered, _PROVIDER_RATE_LIMIT_KEYWORDS):
        return ProviderRateLimitException(details={"origin": exc.__class__.__name__})
    if _match_keyword(lowered, _PROVIDER_AUTH_KEYWORDS):
        return ProviderAuthException(details={"origin": exc.__class__.__name__})
    if isinstance(exc, (ValueError, KeyError)) or _match_keyword(lowered, _CONTENT_PARSE_KEYWORDS):
        return ContentParseException(details={"origin": exc.__class__.__name__})
    return LLMServiceException(
        message="外部模型调用失败",
        details={"origin": exc.__class__.__name__, "reason": message},
    )


def _match_keyword(lowered_message: str, keywords: tuple) -> bool:
    """判断小写错误消息是否包含任一关键词"""
    return any(keyword in lowered_message for keyword in keywords)
