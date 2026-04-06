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
    # 系统相关
    INTERNAL_ERROR = "INTERNAL_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


class AppException(Exception):
    """应用基础异常"""
    def __init__(
        self,
        error_code: ErrorCode,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None
    ):
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        self.trace_id = trace_id or str(uuid.uuid4())
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
