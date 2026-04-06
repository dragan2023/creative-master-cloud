"""统一异常框架测试"""
import pytest
from app.core.exceptions import (
    AppException, ErrorCode,
    AuthenticationException, AuthorizationException,
    ResourceNotFoundException, ValidationException,
    GenerationException, LLMServiceException,
)


class TestExceptions:
    def test_app_exception_defaults(self):
        exc = AppException(ErrorCode.INTERNAL_ERROR, "测试错误")
        assert exc.error_code == ErrorCode.INTERNAL_ERROR
        assert exc.message == "测试错误"
        assert exc.status_code == 500
        assert exc.trace_id is not None
    
    def test_authentication_exception(self):
        exc = AuthenticationException(
            error_code=ErrorCode.AUTH_TOKEN_EXPIRED,
            message="Token已过期"
        )
        assert exc.status_code == 401
        assert exc.error_code == ErrorCode.AUTH_TOKEN_EXPIRED
    
    def test_authorization_exception(self):
        exc = AuthorizationException(
            error_code=ErrorCode.PERMISSION_DENIED,
            message="权限不足"
        )
        assert exc.status_code == 403
        assert exc.error_code == ErrorCode.PERMISSION_DENIED
    
    def test_resource_not_found(self):
        exc = ResourceNotFoundException("资源不存在")
        assert exc.status_code == 404
        assert exc.error_code == ErrorCode.RESOURCE_NOT_FOUND
    
    def test_validation_exception(self):
        exc = ValidationException("参数错误")
        assert exc.status_code == 400
        assert exc.error_code == ErrorCode.VALIDATION_ERROR
    
    def test_generation_exception(self):
        exc = GenerationException("生成失败")
        assert exc.status_code == 500
        assert exc.error_code == ErrorCode.GENERATION_FAILED
    
    def test_llm_service_exception(self):
        exc = LLMServiceException("LLM不可用")
        assert exc.status_code == 503
        assert exc.error_code == ErrorCode.LLM_SERVICE_ERROR
    
    def test_exception_with_details(self):
        exc = AppException(
            ErrorCode.VALIDATION_ERROR,
            "验证失败",
            status_code=400,
            details={"field": "name", "error": "不能为空"}
        )
        assert exc.details["field"] == "name"
        assert exc.details["error"] == "不能为空"
    
    def test_exception_inherits_from_exception(self):
        exc = AppException(ErrorCode.INTERNAL_ERROR, "test")
        assert isinstance(exc, Exception)
    
    def test_exception_attributes(self):
        exc = AppException(
            ErrorCode.VALIDATION_ERROR,
            "验证失败",
            status_code=400,
            details={"field": "name"}
        )
        assert exc.error_code == ErrorCode.VALIDATION_ERROR
        assert exc.message == "验证失败"
        assert exc.status_code == 400
        assert exc.details["field"] == "name"
        assert exc.trace_id is not None
    
    def test_exception_str(self):
        exc = AppException(ErrorCode.INTERNAL_ERROR, "测试错误")
        assert "测试错误" in str(exc)
